"""
题材挖掘路由模块 - 从 Ticai 项目集成
"""
import json
import time
from datetime import date, datetime
from flask import Blueprint, jsonify, request
from ticai.theme_fetcher import fetch_hot_themes, fetch_all_themes_with_stocks
from ticai.analyzer import analyze_and_format_stocks
from ticai.emotion_cycle import calculate_theme_emotion, get_stage_color, get_stage_advice
from ticai.theme_quality import evaluate_theme_quality
from ticai.news_fetcher import fetch_cls_news, evaluate_theme_news_factor, get_market_news_summary
from ticai.database import (
    init_ticai_tables, save_report, get_report_by_date, get_recent_reports,
    get_performance_summary, get_stock_history, get_cached_news, get_connection,
)
from ticai.performance_tracker import update_all_performance, get_today_performance_report
# cache.py 在项目根目录
try:
    from cache import get, set, invalidate
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from cache import get, set, invalidate

try:
    import akshare as ak
except ImportError:
    ak = None

# Lazy import inside functions where used


def _get_ak():
    global ak
    if ak is None:
        import akshare as _ak
        ak = _ak
    return ak

ticai_bp = Blueprint('ticai', __name__)

# 初始化题材挖掘数据库表
try:
    init_ticai_tables()
except Exception as e:
    print(f"[WARN] 题材挖掘表初始化失败: {e}")


def get_market_index_change() -> float:
    """获取大盘（上证指数）涨跌幅"""
    try:
        df = _get_ak().stock_zh_index_spot_em()
        if df is not None and not df.empty:
            sh_index = df[df["名称"] == "上证指数"]
            if not sh_index.empty:
                return float(sh_index.iloc[0].get("涨跌幅", 0) or 0)
    except Exception as e:
        print(f"获取大盘数据失败: {e}")
    return 0


@ticai_bp.route('/ticai')
def ticai_page():
    """题材挖掘页面 - Vue 组件直接调用 API，不再使用 iframe"""
    return jsonify({
        'message': '题材挖掘页面由 Vue 组件渲染，请访问 /frontend/ticai',
        'vue_route': '/ticai'
    })


@ticai_bp.route('/api/ticai/themes')
def get_themes():
    """获取热门题材列表（Redis 缓存 60s）"""
    hit = get('ticai/themes')
    if hit is not None:
        return jsonify({"success": True, "data": hit})
    try:
        themes = fetch_hot_themes(10)
        set('ticai/themes', themes, ttl=60)
        return jsonify({"success": True, "data": themes})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ticai_bp.route('/api/ticai/all')
@ticai_bp.route('/api/ticai/all/')
def get_all_data():
    """
    获取所有热门题材及其推荐股票。
    读取顺序：
      1. Redis 缓存（TTL 60s，刷新后自动失效）
      2. MySQL 今日报表（持久存储，次日自动换新）
      3. 完整 pipeline（MySQL 也为空时降级执行）
    """
    hit = get('ticai/all')
    if hit is not None:
        return jsonify({"success": True, "data": hit.get('data', {}), "market_change": hit.get('market_change', 0), "source": "cache"})

    # ── 2. 尝试从 MySQL 读今日报表 ────────────────────────────────
    from datetime import date
    db_report = get_report_by_date(date.today())
    if db_report is not None:
        payload = _build_api_payload_from_db(db_report)
        set('ticai/all', payload, ttl=60)
        return jsonify({"success": True, "data": payload.get('data', {}), "market_change": payload.get('market_change', 0), "source": "mysql"})

    # ── 3. 降级：跑完整 pipeline ─────────────────────────────────
    return _fetch_and_build_all_data()


def _build_api_payload_from_db(db_report: dict) -> dict:
    """
    把 MySQL 读出的报表转成与 get_all_data() 相同的 API payload 格式。
    """
    themes = db_report.get('themes', {})
    market_change = db_report.get('market_change', 0)

    result = {}
    for theme_name, theme_data in themes.items():
        stocks_raw = theme_data.get('stocks', [])

        # 把 DB 行格式转成前端期望的字段（与 format_stock_display 输出对齐）
        formatted_stocks = []
        for s in stocks_raw:
            turnover_str = s.get('turnover_rate', 0)
            try:
                turnover = float(turnover_str) if turnover_str else 0
            except Exception:
                turnover = 0

            front_runner_tags = []
            if s.get('front_runner_tags'):
                try:
                    front_runner_tags = json.loads(s['front_runner_tags'])
                except Exception:
                    pass

            formatted_stocks.append({
                "code": s.get('stock_code', ''),
                "name": s.get('stock_name', ''),
                "price": f"{s.get('recommend_price', 0):.2f}",
                "change_pct": f"{s.get('change_pct', 0):+.2f}%",
                "change_pct_num": s.get('change_pct', 0),
                "market_cap": f"{s.get('market_cap', 0)/100000000:.0f}亿" if s.get('market_cap', 0) > 0 else "-",
                "amount": f"{s.get('amount', 0)/100000000:.2f}亿" if s.get('amount', 0) > 0 else "-",
                "amplitude": "0.00%",
                "turnover_rate": f"{turnover:.1f}%",
                "score": s.get('score', 0),
                "signal": s.get('signal', '观望'),
                "role": s.get('role', ''),
                "role_reason": s.get('role_reason', ''),
                "volume_level": s.get('volume_level', '-'),
                "strength": s.get('strength', '-'),
                "is_weak_to_strong": bool(s.get('is_weak_to_strong')),
                "weak_to_strong_type": s.get('role_reason', ''),
                "is_front_runner": bool(s.get('is_front_runner')),
                "front_runner_tags": front_runner_tags,
                "is_buyable": bool(s.get('is_buyable', 1)),
                "unbuyable_reason": s.get('unbuyable_reason', ''),
                "is_limit_up": s.get('change_pct', 0) >= 9.9,
                "is_first_limit": False,
                "open_strength": "平开",
                "open_change": s.get('open_change', 0),
            })

        result[theme_name] = {
            "info": theme_data.get('info', {}),
            "history": theme_data.get('history', {}),
            "hot_score": theme_data.get('hot_score', 0),
            "market_change": theme_data.get('market_change', market_change),
            "emotion": theme_data.get('emotion', {}),
            "quality": theme_data.get('quality', {}),
            "news": theme_data.get('news', {}),
            "stocks": formatted_stocks,
        }

    sorted_result = dict(
        sorted(result.items(), key=lambda x: x[1].get('hot_score', 0), reverse=True)
    )
    return {"data": sorted_result, "market_change": market_change}


def _fetch_and_build_all_data():
    """
    完整 pipeline：爬虫 → 分析 → 存 MySQL → 设 Redis → 返回。
    """
    try:
        print("\n" + "=" * 60)
        print("📊 MySQL 无今日报表，执行完整 pipeline（爬虫 + 分析）")
        print("=" * 60)

        market_change = get_market_index_change()
        print(f"📈 大盘涨跌: {market_change:+.2f}%")

        theme_data = fetch_all_themes_with_stocks(theme_limit=8)
        news_list = fetch_cls_news(50)

        result = {}
        for theme_name, data in theme_data.items():
            stocks = data.get("stocks", [])
            theme_info = data.get("info", {})
            history = data.get("history", {})
            hot_score = data.get("hot_score", 0)

            theme_change = theme_info.get("change_pct", 0) or 0
            emotion = calculate_theme_emotion(theme_info, stocks)
            formatted_stocks = analyze_and_format_stocks(stocks, market_change, theme_change)

            fund_tags = []
            if history.get("continuous_up", 0) >= 2:
                fund_tags.append(f"连涨{history['continuous_up']}日")
            if history.get("continuous_inflow", 0) >= 2:
                fund_tags.append(f"连续{history['continuous_inflow']}日流入")
            if history.get("total_change_3d", 0) >= 5:
                fund_tags.append(f"3日涨{history['total_change_3d']:.1f}%")

            quality = evaluate_theme_quality(theme_name, theme_info, stocks, history)
            news_factor = evaluate_theme_news_factor(theme_name, news_list, stocks)

            result[theme_name] = {
                "info": {
                    "change_pct": theme_change,
                    "up_count": theme_info.get("up_count", 0),
                    "down_count": theme_info.get("down_count", 0),
                },
                "history": {
                    "continuous_up": history.get("continuous_up", 0),
                    "continuous_inflow": history.get("continuous_inflow", 0),
                    "total_change_3d": round(history.get("total_change_3d", 0), 2),
                    "total_inflow_3d": round(history.get("total_inflow_3d", 0) / 100000000, 2),
                    "is_hot": history.get("is_hot", False),
                    "fund_tags": fund_tags,
                },
                "hot_score": hot_score,
                "market_change": market_change,
                "quality": quality,
                "news": news_factor,
                "emotion": {
                    "stage": emotion["stage"],
                    "stage_desc": emotion["stage_desc"],
                    "score": emotion["emotion_score"],
                    "color": get_stage_color(emotion["stage"]),
                    "advice": get_stage_advice(emotion["stage"]),
                    "metrics": emotion["metrics"],
                },
                "stocks": formatted_stocks,
            }

        sorted_result = dict(
            sorted(result.items(), key=lambda x: x[1].get("hot_score", 0), reverse=True)
        )
        print(f"\n✅ 数据获取完成，共 {len(sorted_result)} 个题材\n")

        # 保存 MySQL（报表持久化）+ Redis（短期缓存）
        try:
            save_report(date.today(), market_change, sorted_result)
        except Exception as save_err:
            print(f"⚠️ 保存报表失败: {save_err}")

        payload = {"data": sorted_result, "market_change": market_change}
        set('ticai/all', payload, ttl=60)
        return jsonify({"success": True, "data": sorted_result, "market_change": market_change, "source": "pipeline"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@ticai_bp.route('/api/ticai/refresh', methods=['POST'])
def force_refresh():
    """
    手动刷新：清除 Redis 缓存 + 删除 MySQL 今日报表，强制重新爬取。
    前端「刷新」按钮调用此接口。
    """
    invalidate('ticai/')
    try:
        report = get_report_by_date(date.today())
        if report:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM ticai_recommended_stocks WHERE report_id = %s', (report['id'],))
                cursor.execute('DELETE FROM ticai_reports WHERE id = %s', (report['id'],))
        print("🗑️ 今日报表已清除，即将重新爬取")
    except Exception as e:
        print(f"⚠️ 删除今日报表失败: {e}")
    return jsonify({"success": True, "message": "已清除缓存，即将重新获取数据"})


@ticai_bp.route('/api/ticai/kline/<stock_code>')
def get_stock_kline(stock_code):
    """获取股票K线数据（复用布林带的数据源）+ 量能画像"""
    days = request.args.get('days', 250, type=int)

    try:
        from utils.ths_crawler import get_stock_kline_sina
        from bollinger_squeeze_strategy import BollingerSqueezeStrategy
        import numpy as np

        df = get_stock_kline_sina(stock_code, days=days)
        if df is None or df.empty:
            return jsonify({"success": False, "error": "无K线数据"}), 404

        # 计算量能画像指标
        strategy = BollingerSqueezeStrategy()
        try:
            df_vp = strategy.calculate_volume_profile(df)
        except Exception:
            df_vp = df  # 降级：不影响K线展示

        result = []
        for idx, row in df_vp.iterrows():
            item = {
                "time": str(row['date']),
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "volume": float(row.get('volume', 0)),
            }
            result.append(item)

        # 量能画像数据
        import pandas as pd
        def safe_list(series):
            return [None if pd.isna(x) else float(x) for x in series]
        def bool_list(series):
            return [bool(x) if pd.notna(x) else False for x in series]

        vp_data = {}
        vp_cols = {
            'vp_obv': safe_list, 'vp_std_vol': safe_list, 'vp_max_vol': safe_list,
            'vp_dbhs': safe_list,
            'vp_color': lambda s: [int(x) if pd.notna(x) else 0 for x in s],
            'vp_lxtp': bool_list, 'vp_lxtp1': bool_list,
            'vp_super_vol': bool_list, 'vp_vol_break_up': bool_list,
            'vp_vol_break_down': bool_list, 'vp_bull_signal': bool_list,
            'vp_bear_signal': bool_list, 'vp_main_buy_signal': bool_list,
            'vp_ma_golden': bool_list, 'vp_cost_break': bool_list,
        }
        for col, fn in vp_cols.items():
            if col in df_vp.columns:
                vp_data[col] = fn(df_vp[col])

        return jsonify({
            "success": True,
            "data": {"code": stock_code, "name": "", "klines": result, "vp": vp_data},
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 历史报表 ====================

@ticai_bp.route('/ticai/history')
def history_page():
    """历史报表页面 - 重定向到 Vue 前端"""
    from flask import redirect
    return redirect('/frontend/ticai/history')


@ticai_bp.route('/api/ticai/reports')
def get_reports():
    """获取历史报表列表"""
    try:
        limit = request.args.get('limit', 30, type=int)
        reports = get_recent_reports(limit)
        # 序列化日期
        for r in reports:
            if 'report_date' in r and hasattr(r['report_date'], 'isoformat'):
                r['report_date'] = r['report_date'].isoformat()
            if 'created_at' in r and hasattr(r['created_at'], 'isoformat'):
                r['created_at'] = r['created_at'].isoformat()
        return jsonify({"success": True, "data": reports})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ticai_bp.route('/api/ticai/reports/<report_date>')
def get_report(report_date):
    """获取指定日期的报表详情"""
    try:
        query_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        report = get_report_by_date(query_date)
        if not report:
            return jsonify({"success": False, "error": "未找到该日期的报表"}), 404

        # 序列化日期
        if hasattr(report.get('report_date'), 'isoformat'):
            report['report_date'] = report['report_date'].isoformat()
        if hasattr(report.get('created_at'), 'isoformat'):
            report['created_at'] = report['created_at'].isoformat()
        for s in report.get('stocks', []):
            if hasattr(s.get('created_at'), 'isoformat'):
                s['created_at'] = s['created_at'].isoformat()

        return jsonify({"success": True, "data": report})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 收益跟踪 ====================

@ticai_bp.route('/ticai/performance')
def performance_page():
    """收益统计页面 - 重定向到 Vue 前端"""
    from flask import redirect
    return redirect('/frontend/ticai/performance')


@ticai_bp.route('/api/ticai/performance/summary')
def get_performance():
    """获取收益统计摘要"""
    try:
        days = request.args.get('days', 30, type=int)
        summary = get_performance_summary(days)
        return jsonify({"success": True, "data": summary})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ticai_bp.route('/api/ticai/performance/today')
def get_today_perf():
    """获取今日收益报告"""
    try:
        report = get_today_performance_report()
        return jsonify({"success": True, "data": report})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ticai_bp.route('/api/ticai/performance/update', methods=['POST'])
def trigger_update():
    """手动触发收益更新"""
    try:
        update_all_performance()
        return jsonify({"success": True, "message": "收益更新完成"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ticai_bp.route('/api/ticai/stock/<stock_code>/history')
def stock_history(stock_code):
    """获取股票的历史推荐记录"""
    try:
        limit = request.args.get('limit', 10, type=int)
        history = get_stock_history(stock_code, limit)
        return jsonify({"success": True, "data": history})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 新闻历史 ====================

@ticai_bp.route('/api/news/history')
def get_news_history():
    """
    查询历史新闻（来自数据库缓存，Redis 缓存 180s）
    days: 查最近几天，默认1天
    """
    try:
        days = request.args.get('days', 1, type=int)
        cache_key = f'news/history/{days}'
        hit = get(cache_key)
        if hit is not None:
            return jsonify({"success": True, "data": hit, "count": len(hit)})
        news = get_cached_news(days=days)
        set(cache_key, news, ttl=180)
        return jsonify({"success": True, "data": news, "count": len(news)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ticai_bp.route('/api/news/refresh', methods=['POST'])
def refresh_news():
    """
    强制刷新新闻（绕过缓存直接抓取并存库），完成后清除所有相关新闻缓存
    """
    try:
        from ticai.news_fetcher import fetch_all_news
        news = fetch_all_news(limit_per_source=30, force=True)
        invalidate('news/')
        invalidate('ticai/')
        return jsonify({"success": True, "count": len(news)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

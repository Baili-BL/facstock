"""
题材挖掘路由模块 - 从 Ticai 项目集成
"""
import time
from datetime import date, datetime
from flask import Blueprint, jsonify, render_template, make_response, request
from ticai.theme_fetcher import fetch_hot_themes, fetch_all_themes_with_stocks
from ticai.analyzer import analyze_and_format_stocks
from ticai.emotion_cycle import calculate_theme_emotion, get_stage_color, get_stage_advice
from ticai.theme_quality import evaluate_theme_quality
from ticai.news_fetcher import fetch_cls_news, evaluate_theme_news_factor, get_market_news_summary
from ticai.database import (
    init_ticai_tables, save_report, get_report_by_date, get_recent_reports,
    get_performance_summary, get_stock_history,
)
from ticai.performance_tracker import update_all_performance, get_today_performance_report

try:
    import akshare as ak
except ImportError:
    ak = None

ticai_bp = Blueprint('ticai', __name__)

# 初始化题材挖掘数据库表
try:
    init_ticai_tables()
except Exception as e:
    print(f"[WARN] 题材挖掘表初始化失败: {e}")


def get_market_index_change() -> float:
    """获取大盘（上证指数）涨跌幅"""
    if ak is None:
        return 0
    try:
        df = ak.stock_zh_index_spot_em()
        if df is not None and not df.empty:
            sh_index = df[df["名称"] == "上证指数"]
            if not sh_index.empty:
                return float(sh_index.iloc[0].get("涨跌幅", 0) or 0)
    except Exception as e:
        print(f"获取大盘数据失败: {e}")
    return 0


@ticai_bp.route('/ticai')
def ticai_page():
    """题材挖掘页面"""
    response = make_response(render_template('ticai.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@ticai_bp.route('/api/ticai/themes')
def get_themes():
    """获取热门题材列表"""
    try:
        themes = fetch_hot_themes(10)
        return jsonify({"success": True, "data": themes})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ticai_bp.route('/api/ticai/all')
def get_all_data():
    """获取所有热门题材及其推荐股票"""
    try:
        print("\n" + "=" * 60)
        print("📊 开始获取热门题材数据...")
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
                "quality": quality,
                "news": news_factor,
                "market_change": market_change,
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

        # 自动保存报表
        try:
            save_report(date.today(), market_change, sorted_result)
        except Exception as save_err:
            print(f"⚠️ 保存报表失败: {save_err}")

        return jsonify({
            "success": True,
            "data": sorted_result,
            "market_change": market_change,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@ticai_bp.route('/api/ticai/kline/<stock_code>')
def get_stock_kline(stock_code):
    """获取股票K线数据（复用布林带的数据源）"""
    days = request.args.get('days', 250, type=int)

    try:
        from utils.ths_crawler import get_stock_kline_sina

        df = get_stock_kline_sina(stock_code, days=days)
        if df is None or df.empty:
            return jsonify({"success": False, "error": "无K线数据"}), 404

        result = []
        for _, row in df.iterrows():
            result.append({
                "time": str(row['date']),
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "volume": float(row.get('volume', 0)),
            })

        return jsonify({
            "success": True,
            "data": {"code": stock_code, "name": "", "klines": result},
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 历史报表 ====================

@ticai_bp.route('/ticai/history')
def history_page():
    """历史报表页面"""
    response = make_response(render_template('ticai_history.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


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
    """收益统计页面"""
    response = make_response(render_template('ticai_performance.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


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

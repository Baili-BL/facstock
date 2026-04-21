#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场数据路由模块
"""

import logging
from datetime import datetime

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)
from a_share_session import get_a_share_session_payload
from market_data import (
    get_market_overview,
    get_money_flow,
    get_limit_up_data,
    get_turnover_rate,
    get_hot_sectors,
    get_hot_concept_sectors,
    get_sector_main_fund_flow,
    get_ai_summary,
    get_market_snapshot,
    peek_market_snapshot_cache,
    compute_macro_sentiment,
    enrich_snapshot_industries,
    snapshot_rankings_need_industry_enrich,
    MARKET_SNAPSHOT_REDIS_KEY,
)
from utils.ths_crawler import get_ths_industry_list
from ticai.news_fetcher import fetch_all_news
from cache import get, set, delete_key

market_bp = Blueprint('market', __name__)

# 与旧版区分：此前 Redis 里可能长期缓存了 industry 为空的快照（key 定义见 market_data.MARKET_SNAPSHOT_REDIS_KEY）
SNAPSHOT_REDIS_KEY = MARKET_SNAPSHOT_REDIS_KEY


@market_bp.route('/')
def index():
    """旧版首页兼容（已保留供外部书签访问）：302 到新版 SPA"""
    from flask import redirect
    return redirect('/frontend/')


@market_bp.route('/api/market/session')
def api_market_session():
    """A 股交易时段状态（北京时间，与上证连续竞价时间一致）；纯计算、可短缓存。"""
    hit = get('market/session')
    if hit is not None:
        return jsonify({'success': True, 'data': hit})
    try:
        data = get_a_share_session_payload()
        set('market/session', data, ttl=10)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logger.exception('market session')
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/api/market/overview')
def api_market_overview():
    """获取大盘指数概览（Redis 缓存 15s）"""
    hit = get('market/overview')
    if hit is not None:
        return jsonify({'success': True, 'data': hit})

    try:
        data = get_market_overview()
        set('market/overview', data, ttl=15)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/api/market/snapshot')
def api_market_snapshot():
    """A 股全市场快照（Redis 缓存 30s）；命中缓存仍会对缺行业的排行做补全。"""
    hit = get(SNAPSHOT_REDIS_KEY)
    if hit is not None:
        # Redis 可能仍是「仅新浪、涨跌家数为 0」；进程内缓存或已被东财后台线程更新，择优返回
        mem = peek_market_snapshot_cache()
        if isinstance(mem, dict):
            r_breadth = int(hit.get('up_count') or 0) + int(hit.get('down_count') or 0)
            m_breadth = int(mem.get('up_count') or 0) + int(mem.get('down_count') or 0)
            if m_breadth > r_breadth:
                hit = mem
                set(SNAPSHOT_REDIS_KEY, hit, ttl=30)
        if snapshot_rankings_need_industry_enrich(hit):
            try:
                enrich_snapshot_industries(hit)
            except Exception as e:
                logger.warning('Redis 快照行业补全失败: %s', e)
            set(SNAPSHOT_REDIS_KEY, hit, ttl=30)
        return jsonify({'success': True, 'data': hit})

    try:
        data = get_market_snapshot()
        set(SNAPSHOT_REDIS_KEY, data, ttl=30)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/api/market/flow')
def api_money_flow():
    """获取资金流向（Redis 缓存 15s）"""
    hit = get('market/flow')
    if hit is not None:
        return jsonify({'success': True, 'data': hit})

    try:
        data = get_money_flow()
        set('market/flow', data, ttl=15)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/api/market/limit')
def api_limit_up():
    """获取涨跌停数据（Redis 缓存 15s）"""
    hit = get('market/limit')
    if hit is not None:
        return jsonify({'success': True, 'data': hit})

    try:
        data = get_limit_up_data()
        set('market/limit', data, ttl=15)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/api/market/turnover')
def api_turnover():
    """获取换手率排行（Redis 缓存 30s）"""
    hit = get('market/turnover')
    if hit is not None:
        return jsonify({'success': True, 'data': hit})

    try:
        data = get_turnover_rate()
        set('market/turnover', data, ttl=30)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/api/market/sectors')
def api_hot_sectors():
    """获取热点行业板块（Redis 缓存 30s）"""
    hit = get('market/sectors')
    if hit is not None:
        return jsonify({'success': True, 'data': hit})

    try:
        data = get_hot_sectors()
        set('market/sectors', data, ttl=30)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/api/market/sectors/concept')
def api_hot_concept_sectors():
    """获取热点概念板块（Redis 缓存 30s）"""
    hit = get('market/sectors/concept')
    if hit is not None:
        return jsonify({'success': True, 'data': hit})

    try:
        data = get_hot_concept_sectors()
        set('market/sectors/concept', data, ttl=30)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/api/market/sectors/main-fund-flow')
def api_sector_main_fund_flow():
    """
    板块主力净流入柱状图数据（亿）。
    Query: kind=industry|concept|region，默认 industry。Redis 缓存 30s。
    """
    kind = (request.args.get('kind') or 'industry').strip().lower()
    if kind not in ('industry', 'concept', 'region'):
        kind = 'industry'
    cache_key = f'market/sectors/main-fund-flow/{kind}'
    hit = get(cache_key)
    if hit is not None:
        return jsonify({'success': True, 'data': hit})

    try:
        data = get_sector_main_fund_flow(kind)
        set(cache_key, data, ttl=30)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/sectors')
def sectors():
    """板块页面 - 重定向到 Vue 前端"""
    from flask import redirect
    return redirect('/frontend/sectors')


@market_bp.route('/api/market/summary')
def api_market_summary():
    """获取市场综合摘要（Redis 缓存 60s）"""
    hit = get('market/summary')
    if hit is not None:
        return jsonify({'success': True, 'data': hit})

    try:
        data = get_ai_summary()
        set('market/summary', data, ttl=60)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/api/news')
def api_news():
    """获取实时财经新闻（Redis 缓存 180s）。?force=1 跳过 Redis 并强制多源重新抓取。"""
    force = request.args.get('force', '').lower() in ('1', 'true', 'yes')
    if force:
        delete_key('news/all')
    if not force:
        hit = get('news/all')
        if hit is not None:
            return jsonify({'success': True, 'data': hit})

    try:
        news = fetch_all_news(limit_per_source=50, force=force)
        set('news/all', news, ttl=180)
        return jsonify({'success': True, 'data': news})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/api/macro/summary')
def api_macro_summary():
    """每日宏观视角：综合评分 + 摘要文字（Redis 缓存 60s）"""
    hit = get('macro/summary')
    if hit is not None:
        return jsonify({'success': True, 'data': hit})

    try:
        data = compute_macro_sentiment()
        set('macro/summary', data, ttl=60)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/api/market/index-mini')
def api_index_mini():
    """
    三大指数近3天分时（5分钟K线）数据，供首页展示真实分时走势。
    若腾讯分时数据获取失败，降级为新浪 overview 数据（当日单点价格/涨跌幅）。
    """
    hit = get('market/index-mini')
    if hit is not None:
        return jsonify({'success': True, 'data': hit})

    try:
        from utils.ths_crawler import get_index_intraday_em

        INDEX_MAP = {
            'SSE:000001': ('000001', '1', '上证指数'),
            'SZSE:399001': ('399001', '0', '深证成指'),
            'SZSE:399006': ('399006', '0', '创业板指'),
        }

        result = {}
        for symbol, (code, market, name) in INDEX_MAP.items():
            klines = get_index_intraday_em(code, market)
            if klines:
                result[symbol] = {
                    'name': name,
                    'times':  [k['time'] for k in klines],
                    'closes': [k['close'] for k in klines],
                    'high':   klines[-1].get('high') or 0,
                    'low':    klines[-1].get('low') or 0,
                }

        if not result:
            overview = get_market_overview() or []
            name_to_symbol = {
                '上证指数': 'SSE:000001',
                '深证成指': 'SZSE:399001',
                '创业板指': 'SZSE:399006',
            }
            today = datetime.now().strftime('%Y-%m-%d')
            for item in overview:
                name = item.get('name', '')
                symbol = name_to_symbol.get(name)
                if not symbol:
                    continue
                price = item.get('price', 0)
                if not price:
                    continue
                result[symbol] = {
                    'name': name,
                    'times':  [f'{today} 00:00'],
                    'closes': [price],
                    'high':   price,
                    'low':    price,
                    'fallback': True,
                }
                logger.info(f'指数分时降级（Sina overview）: {name} = {price}')

        set('market/index-mini', result, ttl=60)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.exception('market index mini kline')
        return jsonify({'success': False, 'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
# 宏观同步快讯 — Editorial Intelligence 数据聚合
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_macro_flash_report(timeout_seconds=15) -> dict:
    """
    聚合所有宏观数据，构造宏观同步快讯所需的完整数据结构。
    该函数会在 API 层统一调度，各子模块尽量复用已有缓存数据。
    """
    import akshare as ak
    from datetime import datetime
    from ticai.news_fetcher import fetch_all_news, analyze_news_sentiment

    # ── 1. 国内市场数据（复用已有缓存函数） ───────────────────────────────
    overview = get_market_overview() or []
    snapshot = get_market_snapshot() or {}
    flow = get_money_flow() or {}
    limit = get_limit_up_data() or {}
    sectors = get_hot_sectors() or []
    macro_sentiment = compute_macro_sentiment() or {}

    # ── 2. 国际宏观数据（AKShare 优先，失败则由 Qwen 补充） ───────────────────
    intl = []
    try:
        # 10年期美债收益率
        try:
            df_bond = ak.bond_zh_us_rate()
            if df_bond is not None and len(df_bond) >= 2:
                latest = df_bond.iloc[-1]
                prev = df_bond.iloc[-2]
                val = float(latest.iloc[1]) if pd_notna(latest.iloc[1]) else None
                prev_val = float(prev.iloc[1]) if pd_notna(prev.iloc[1]) else val
                if val is not None:
                    chg = val - prev_val
                    intl.append({
                        'label': '10Y 美债收益率',
                        'value': f'{val:.2f}%',
                        'change': f'{"+" if chg >= 0 else ""}{chg:.1f}bp',
                    })
        except Exception:
            pass

        # 美元指数 DXY（离岸人民币 + 美元指数代理）
        try:
            df_dxy = ak.currency_consolidated_index(symbol="美国", name="美元指数")
            if df_dxy is not None and len(df_dxy) >= 1:
                row = df_dxy.iloc[-1]
                val = _safe_float(row, '最新价') or _safe_float(row, 1)
                intl.append({'label': '美元指数 (DXY)', 'value': f'{val:.1f}' if val else '--', 'change': '持平'})
        except Exception:
            pass

        # CPI 预期（美国）
        try:
            cpi_data = ak.economic_calendar_ov(start_date=datetime.now().strftime('%Y-%m-%d'),
                                               end_date=datetime.now().strftime('%Y-%m-%d'),
                                               country="美国", indicator="CPI")
            if cpi_data is not None and len(cpi_data) > 0:
                row = cpi_data.iloc[0]
                val_str = str(row.get('actual', row.get('forecast', '--')))
                intl.append({'label': 'CPI 预期 (YoY)', 'value': val_str, 'change': ''})
        except Exception:
            pass

        # 布伦特原油
        try:
            df_oil = ak.futures_foreign_price(symbol="布伦特原油")
            if df_oil is not None and len(df_oil) >= 2:
                latest = df_oil.iloc[-1]
                prev = df_oil.iloc[-2]
                val = _safe_float(latest, '收盘') or _safe_float(latest, 1)
                prev_val = _safe_float(prev, '收盘') or _safe_float(prev, 1)
                if val and prev_val:
                    chg_pct = (val - prev_val) / prev_val * 100
                    intl.append({
                        'label': '布伦特原油',
                        'value': f'${val:.1f}',
                        'change': f'{"+" if chg_pct >= 0 else ""}{chg_pct:.1f}%',
                    })
        except Exception:
            pass

        # 黄金
        try:
            df_gold = ak.futures_foreign_price(symbol="伦敦金")
            if df_gold is not None and len(df_gold) >= 2:
                latest = df_gold.iloc[-1]
                prev = df_gold.iloc[-2]
                val = _safe_float(latest, '收盘') or _safe_float(latest, 1)
                prev_val = _safe_float(prev, '收盘') or _safe_float(prev, 1)
                if val and prev_val:
                    chg_pct = (val - prev_val) / prev_val * 100
                    intl.append({
                        'label': '现货黄金 (XAU)',
                        'value': f'${val:.0f}',
                        'change': f'{"+" if chg_pct >= 0 else ""}{chg_pct:.1f}%',
                    })
        except Exception:
            pass

    except Exception:
        pass

    # AKShare 未获取到数据时，由 Qwen 补充国际宏观数据
    intl_labels = {'10Y 美债收益率', '美元指数 (DXY)', 'CPI 预期 (YoY)', '布伦特原油', '现货黄金 (XAU)'}
    existing_labels = {x['label'] for x in intl}
    missing_labels = intl_labels - existing_labels

    if missing_labels:
        try:
            from utils.llm import get_client
            client = get_client()
            today_str = datetime.now().strftime('%Y-%m-%d')
            prompt = (
                f"今天是 {today_str}，请以 JSON 格式返回以下国际宏观经济指标的当前数据（无需解释，只返回 JSON）：\n"
                f"指标列表：10Y 美债收益率、美元指数(DXY)、CPI预期(YoY,美国)、布伦特原油价格、现货黄金(XAU)价格。\n"
                f"返回格式必须是合法 JSON，示例：\n"
                f'{{"10Y 美债收益率": {{"value": "4.52%", "change": "-2.3bp"}}, "美元指数 (DXY)": {{"value": "104.2", "change": "+0.1"}}, '
                f'"CPI 预期 (YoY)": {{"value": "2.8%", "change": ""}}, '
                f'"布伦特原油": {{"value": "$82.5", "change": "+1.2%"}}, '
                f'"现货黄金 (XAU)": {{"value": "$2340", "change": "+0.8%"}}}}。\n'
                f"如果某项数据无法获取，value 填 '--'，change 填 '暂无数据'。"
            )
            resp = client.call(prompt=prompt, system="你是一个专业的宏观经济数据助手。请只返回 JSON，不要添加任何额外文字。")
            if resp.success and resp.content:
                import json as _json
                try:
                    qwen_data = _json.loads(resp.content.strip())
                    for label in missing_labels:
                        item = qwen_data.get(label, {})
                        val = item.get('value', '--')
                        chg = item.get('change', '暂无数据')
                        if val and val != '--':
                            intl.append({'label': label, 'value': val, 'change': chg if chg else '暂无数据'})
                        else:
                            intl.append({'label': label, 'value': '--', 'change': '暂无数据'})
                except Exception:
                    for label in missing_labels:
                        intl.append({'label': label, 'value': '--', 'change': '暂无数据'})
            else:
                for label in missing_labels:
                    intl.append({'label': label, 'value': '--', 'change': '暂无数据'})
        except Exception:
            for label in missing_labels:
                intl.append({'label': label, 'value': '--', 'change': '暂无数据'})
    else:
        # AKShare 已获取到全部数据，也补充变动描述（如果缺失）
        for item in intl:
            if item.get('change') in (None, '', '暂无数据') or item['value'] == '--':
                item['change'] = '暂无数据'

    # ── 3. 国内宏观指标 ───────────────────────────────────────────────────
    sh = next((x for x in overview if x.get('name') == '上证指数'), {})
    sh_change = float(sh.get('change') or 0)
    sh_pct = sh_change * 100

    sentiment_score = macro_sentiment.get('sentiment_score', 50)
    risk_level = macro_sentiment.get('risk_level', 'MEDIUM')

    domestic = [
        {
            'label': f'上证指数 ({sh_change:+.2f}%)',
            'value': f'{sh.get("price", "--")}',
            'pct': min(100, max(0, 50 + sh_pct * 5)),
        },
        {
            'label': '涨停家数',
            'value': str(limit.get('limit_up_count', 0)),
            'pct': min(100, int(limit.get('limit_up_count', 0)) * 2),
        },
    ]

    if len(domestic) < 2:
        domestic.append({'label': '风险等级', 'value': risk_level, 'pct': int(sentiment_score)})

    domestic_quote_map = {
        'MEDIUM': '内需修复斜率放缓，货币政策空间依然充裕，关注后续财政落地力度。',
        'MEDIUM-HIGH': '市场情绪偏谨慎，建议保持防御性仓位，密切关注北向资金流向。',
        'ELEVATED': '风险偏好回落，建议控制仓位，避免追高，关注高股息防御品种。',
    }
    domestic_quote = domestic_quote_map.get(risk_level, domestic_quote_map['MEDIUM'])

    # ── 4. 市场新闻 → 大事件提取 ──────────────────────────────────────────
    events = []
    try:
        news = fetch_all_news(limit_per_source=30, force=False)
        if news:
            for item in news[:5]:
                title = item.get('title', '')
                content = item.get('content', '') or ''
                if not title:
                    continue
                sentiment = item.get('sentiment', 'neutral')
                time_ago = item.get('publish_time', '')
                # 简单关键词判断潜在影响
                tags = []
                lower_text = (title + content).lower()
                if any(k in lower_text for k in ['美联储', '降息', '加息', '利率']):
                    if '降息' in lower_text:
                        tags.append({'text': '潜在影响：利好美债 / 成长股', 'cls': 'bullish'})
                    else:
                        tags.append({'text': '潜在影响：利空美债', 'cls': 'bearish'})
                if any(k in lower_text for k in ['地缘', '中东', '俄乌', '战争']):
                    tags.append({'text': '潜在影响：利好黄金', 'cls': 'bullish'})
                    tags.append({'text': '潜在影响：扰动油价', 'cls': 'bearish'})
                if any(k in lower_text for k in ['欧洲央行', 'ECB', '欧元区']):
                    tags.append({'text': '潜在影响：欧元震荡', 'cls': 'neutral'})
                if not tags:
                    tags.append({'text': f'情感：{sentiment}', 'cls': 'neutral'})
                events.append({
                    'title': title[:60],
                    'time': time_ago[:10] if time_ago else '刚刚',
                    'desc': content[:100] if content else title[:80],
                    'tags': tags,
                })
    except Exception:
        pass

    # 如果没有新闻，填充示例
    if not events:
        events = [
            {'title': '市场情绪综合评估', 'time': '实时', 'desc': '基于最新市场数据综合判断。',
             'tags': [{'text': '情感：中性', 'cls': 'neutral'}]},
        ]

    # ── 5. 智能体评估 ────────────────────────────────────────────────────
    agents = [
        {
            'name': '宏观经济学派',
            'sub': 'Alpha-V9 智能体',
            'avatarText': 'M',
            'avatarIcon': None,
            'colorKey': 'primary',
            'stance': '看多 (Bullish)',
            'stanceKey': 'bullish',
            'comment': '当前通胀下行趋势明确，降息预期将重塑估值体系，中小盘成长股具备高弹性机会。',
        },
        {
            'name': '地缘政治专家',
            'sub': 'Geo-Strategic 智能体',
            'avatarText': '',
            'avatarIcon': 'language',
            'colorKey': 'secondary',
            'stance': '中性 (Neutral)',
            'stanceKey': 'neutral',
            'comment': '主要大选临近，贸易政策不确定性溢价上升。建议保持黄金仓位对冲潜在的政策波动性。',
        },
        {
            'name': '流动性策略师',
            'sub': 'Flow-Master 智能体',
            'avatarText': 'L',
            'avatarIcon': None,
            'colorKey': 'error',
            'stance': '看空 (Bearish)',
            'stanceKey': 'bearish',
            'comment': '短期流动性缺口正在扩大，机构仓位已至高位，谨防获利回吐带来的技术性回调风险。',
        },
        {
            'name': '量化技术派',
            'sub': 'Quant-Tech 智能体',
            'avatarText': 'Q',
            'avatarIcon': None,
            'colorKey': 'tertiary',
            'stance': '中性 (Neutral)',
            'stanceKey': 'neutral',
            'comment': '全球供应链正在经历结构性重组，尽管短期面临成本压力，长期生产率提升将支撑经济韧性。',
        },
    ]

    # ── 6. 板块预测 ──────────────────────────────────────────────────────
    top_sectors = [s for s in sectors if s.get('change', 0) > 0][:2] if sectors else []
    sector_cards = []
    if top_sectors:
        for i, s in enumerate(top_sectors):
            sector_cards.append({
                'name': s.get('name', f'板块{i+1}'),
                'desc': f'主力净流入 {s.get("change", 0):.2f}%，具备板块轮动机会。',
                'trend': 'up',
                'chips': ['成长驱动', '资金关注'],
                'img': f'https://picsum.photos/seed/sector{i}/80/120',
            })
    if len(sector_cards) < 2:
        sector_cards.append({
            'name': '能源板块 (Energy)',
            'desc': '供需偏紧状态持续，叠加库存周期见底，共识预期其具备强防御属性。',
            'trend': 'up',
            'chips': ['防御性高', '高分红'],
            'img': 'https://picsum.photos/seed/energy/80/120',
        })
        sector_cards.append({
            'name': '半导体与科技 (Tech)',
            'desc': 'AI 算力基建进入业绩兑现期，核心逻辑由叙事转向盈利，维持增配建议。',
            'trend': 'up',
            'chips': ['成长驱动', '核心资产'],
            'img': 'https://picsum.photos/seed/tech/80/120',
        })

    # ── 7. 综合建议（Qwen 生成） ───────────────────────────────────────────
    north_net = flow.get('north_money', {}).get('north_net_inflow', 0)
    north_str = f'北向资金净流入 {north_net/1e8:.1f}亿' if north_net >= 0 else f'北向资金净流出 {abs(north_net)/1e8:.1f}亿'
    synthesis_core = ''
    synthesis_actions = []
    try:
        from utils.llm import get_client
        client = get_client()
        today_str = datetime.now().strftime('%Y-%m-%d')

        intl_summary = '、'.join([f"{x['label']}:{x['value']}" for x in intl if x.get('value') and x['value'] != '--']) or '暂无数据'
        tone_map = {'MEDIUM': '温和乐观', 'MEDIUM-HIGH': '中性偏谨慎', 'ELEVATED': '谨慎防御'}
        tone = tone_map.get(risk_level, '中性')
        sh_desc = f"上证指数 {sh.get('price', '--')} ({sh_change:+.2f}%)" if sh.get('price') else '上证指数暂无数据'
        limit_up = limit.get('limit_up_count', 0)
        top_news = events[0]['title'] if events else '暂无重要新闻'

        prompt = (
            f"【今日日期】{today_str}\n"
            f"【市场数据】{sh_desc}，涨停 {limit_up} 家，{north_str}\n"
            f"【国际宏观】{intl_summary}\n"
            f"【今日重要新闻】{top_news}\n"
            f"【情绪评分】{sentiment_score}/100，风险等级 {risk_level}，情绪倾向 {tone}\n\n"
            f"请以 JSON 格式返回今日 A 股宏观综合研判（只返回 JSON，不要任何额外文字）：\n"
            f'{{"core": "一段 50-80 字的中文综合研判，结合今日市场数据给出有针对性的分析", '
            f'"actions": ["建议1", "建议2", "建议3", "建议4"]}}'
        )
        resp = client.call(prompt=prompt, system="你是一个专业的A股宏观分析师。请只返回 JSON，不要添加任何额外文字或解释。")
        if resp.success and resp.content:
            import json as _json
            try:
                synthesis_data = _json.loads(resp.content.strip())
                synthesis_core = synthesis_data.get('core', '')
                actions = synthesis_data.get('actions', [])
                if isinstance(actions, list):
                    synthesis_actions = [str(a) for a in actions[:4]]
            except Exception:
                pass
    except Exception:
        pass

    if not synthesis_core:
        synthesis_core = (
            f'当前宏观情绪表现为"{tone}"（{sentiment_score}/100），'
            f'市场处于结构性分化阶段，建议关注高股息与科技成长主线，密切跟踪北向资金与政策信号。'
        )
    if not synthesis_actions:
        synthesis_actions = [
            f'维持 {int(min(90, max(30, sentiment_score * 0.8)))}% 权益仓位',
            '重点配置高股息蓝筹与科技成长主线',
            f'{north_str}，关注外资持续性',
            '关注大宗商品中的黄金与能源机会',
        ]

    # ── 8. 组装完整报告 ──────────────────────────────────────────────────
    return {
        'title': '宏观同步快讯',
        'subtitle': '实时追踪全球资本市场与宏观经济的微小扰动',
        'syncStatus': '系统同步中',
        'international': intl,
        'domestic': domestic,
        'domesticQuote': domestic_quote,
        'events': events,
        'agentModelCount': len(agents),
        'agents': agents,
        'sectors': sector_cards,
        'synthesis': {
            'core': synthesis_core,
            'actions': synthesis_actions,
        },
        '_raw': {
            'sentiment_score': sentiment_score,
            'risk_level': risk_level,
            'macro_sentiment': macro_sentiment,
        },
    }


def _safe_float(series_or_dict, key) -> float | None:
    """安全提取数值"""
    try:
        import pandas as pd
        import numpy as np
        if isinstance(series_or_dict, pd.Series):
            val = series_or_dict.iloc[key] if isinstance(key, int) else series_or_dict.get(key)
        else:
            val = series_or_dict.get(key)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return None
        return float(val)
    except Exception:
        return None


def pd_notna(val) -> bool:
    """检查值是否为非 NA（兼容 numpy / pandas）"""
    import pandas as pd
    import numpy as np
    try:
        return not (pd.isna(val) or (isinstance(val, float) and np.isnan(val)))
    except Exception:
        return val is not None


@market_bp.route('/api/macro/flash-report')
def api_macro_flash_report():
    """
    宏观同步快讯 — Editorial Intelligence 专用数据接口（Redis 缓存 60s）。
    返回: title, subtitle, international[], domestic[], events[], agents[], sectors[], synthesis{}
    """
    hit = get('macro/flash-report')
    if hit is not None:
        return jsonify({'success': True, 'data': hit})

    # Thread-based timeout: if data fetch takes > 15s, return fallback immediately
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
    fallback_data = {
        'title': '宏观同步快讯',
        'subtitle': '实时追踪全球资本市场与宏观经济的微小扰动',
        'syncStatus': '数据获取超时，已返回缓存',
        'international': [
            {'label': '10Y 美债收益率', 'value': '--', 'change': '暂无数据'},
            {'label': '美元指数 (DXY)', 'value': '--', 'change': '暂无数据'},
            {'label': '布伦特原油', 'value': '--', 'change': '暂无数据'},
            {'label': '现货黄金 (XAU)', 'value': '--', 'change': '暂无数据'},
        ],
        'domestic': [{'label': '上证指数', 'value': '--', 'pct': 50}],
        'domesticQuote': '数据获取超时，请稍后刷新',
        'events': [{'title': '暂无数据', 'time': '—', 'desc': '数据获取超时', 'tags': []}],
        'agentModelCount': 4,
        'agents': [
            {'name': '宏观经济学派', 'sub': 'Alpha-V9 智能体', 'avatarText': 'M', 'avatarIcon': None, 'colorKey': 'primary', 'stance': '加载中...', 'stanceKey': 'neutral', 'comment': '数据获取中，请稍后查看。'},
            {'name': '地缘政治专家', 'sub': 'Geo-Strategic 智能体', 'avatarText': '', 'avatarIcon': 'language', 'colorKey': 'secondary', 'stance': '加载中...', 'stanceKey': 'neutral', 'comment': '数据获取中，请稍后查看。'},
            {'name': '流动性策略师', 'sub': 'Flow-Master 智能体', 'avatarText': 'L', 'avatarIcon': None, 'colorKey': 'error', 'stance': '加载中...', 'stanceKey': 'neutral', 'comment': '数据获取中，请稍后查看。'},
            {'name': '量化技术派', 'sub': 'Quant-Tech 智能体', 'avatarText': 'Q', 'avatarIcon': None, 'colorKey': 'tertiary', 'stance': '加载中...', 'stanceKey': 'neutral', 'comment': '数据获取中，请稍后查看。'},
        ],
        'sectors': [],
        'synthesis': {'core': '数据获取超时，请稍后刷新页面', 'actions': ['等待数据加载']},
    }

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_fetch_macro_flash_report)
            try:
                data = future.result(timeout=15)
            except FuturesTimeoutError:
                logger.warning('macro flash report timed out after 15s, returning fallback')
                data = fallback_data
    except Exception as e:
        logger.exception('macro flash report')
        data = fallback_data

    try:
        set('macro/flash-report', data, ttl=60)
    except Exception:
        pass
    return jsonify({'success': True, 'data': data})

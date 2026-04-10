#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场数据路由模块
"""

import logging

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
    返回每个指数的时间序列收盘价。
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

        set('market/index-mini', result, ttl=60)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.exception('market index mini kline')
        return jsonify({'success': False, 'error': str(e)}), 500

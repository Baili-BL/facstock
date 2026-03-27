#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场数据路由模块
"""

import logging

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)
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
    compute_macro_sentiment,
    enrich_snapshot_industries,
    snapshot_rankings_need_industry_enrich,
)
from utils.ths_crawler import get_ths_industry_list
from ticai.news_fetcher import fetch_all_news
from cache import get, set

market_bp = Blueprint('market', __name__)

# 与旧版区分：此前 Redis 里可能长期缓存了 industry 为空的快照
SNAPSHOT_REDIS_KEY = 'market/snapshot/v2'


@market_bp.route('/')
def index():
    """首页 - 重定向到 Vue 前端"""
    from flask import redirect
    return redirect('/frontend/')


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
    """获取实时财经新闻（Redis 缓存 180s）"""
    hit = get('news/all')
    if hit is not None:
        return jsonify({'success': True, 'data': hit})

    try:
        news = fetch_all_news(limit_per_source=50)
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

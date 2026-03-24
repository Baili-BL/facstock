#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场数据路由模块
"""

from flask import Blueprint, jsonify, request
from market_data import (
    get_market_overview,
    get_money_flow,
    get_limit_up_data,
    get_turnover_rate,
    get_hot_sectors,
    get_ai_summary,
)
from utils.ths_crawler import get_ths_industry_list
from ticai.news_fetcher import fetch_all_news

market_bp = Blueprint('market', __name__)


@market_bp.route('/')
def index():
    """首页 - 重定向到 Vue 前端"""
    from flask import redirect
    return redirect('/frontend/')


@market_bp.route('/api/market/overview')
def api_market_overview():
    """获取大盘指数概览"""
    try:
        data = get_market_overview()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/api/market/flow')
def api_money_flow():
    """获取资金流向"""
    try:
        data = get_money_flow()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/api/market/limit')
def api_limit_up():
    """获取涨跌停数据"""
    try:
        data = get_limit_up_data()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/api/market/turnover')
def api_turnover():
    """获取换手率排行"""
    try:
        data = get_turnover_rate()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/api/market/sectors')
def api_hot_sectors():
    """获取热点板块"""
    try:
        data = get_hot_sectors()
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
    """获取市场综合摘要"""
    try:
        data = get_ai_summary()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/api/news')
def api_news():
    """获取实时财经新闻（最多保留最近3天）"""
    try:
        news = fetch_all_news(limit_per_source=50)
        return jsonify({'success': True, 'data': news})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

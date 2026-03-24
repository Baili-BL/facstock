#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大盘数据模块 - 提供市场概览、资金流向、涨跌停等数据

数据源策略：
- 东方财富 eastmoney.com（部分接口可能需要代理）
- 同花顺 q.10jqka.com.cn（行业板块）
- 沪深港通数据（北向资金）
- 涨跌停池数据
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# 缓存相关
_cache = {}
_cache_timeout = 300  # 5分钟缓存


def _get_cached(key: str) -> Optional[any]:
    """获取缓存数据"""
    if key in _cache:
        data, timestamp = _cache[key]
        if datetime.now().timestamp() - timestamp < _cache_timeout:
            return data
    return None


def _set_cached(key: str, data: any):
    """设置缓存数据"""
    _cache[key] = (data, datetime.now().timestamp())


def _safe_float(val, default: float = 0.0) -> float:
    """安全转换为浮点数"""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def get_market_overview() -> List[Dict]:
    """
    获取大盘指数概览（上证、深证、创业板、科创板等）
    使用 stock_zh_index_spot_sina 获取实时指数数据（新浪，数据源稳定）
    """
    cached = _get_cached('market_overview')
    if isinstance(cached, list):
        return cached

    result = []
    try:
        df = ak.stock_zh_index_spot_sina()
        if df is None or df.empty:
            return []

        # 需要的主要指数代码（新浪格式：sh/sz前缀）
        needed = {
            'sh000001': '上证指数',
            'sz399001': '深证成指',
            'sz399006': '创业板指',
            'sh000688': '科创50',
            'sh000300': '沪深300',
            'sh000016': '上证50',
            'sh000905': '中证500',
        }

        for code, name in needed.items():
            rows = df[df['代码'] == code]
            if rows.empty:
                continue
            r = rows.iloc[0]
            result.append({
                'name': name,
                'code': code,
                'price': _safe_float(r.get('最新价')),
                'change': _safe_float(r.get('涨跌幅')),
                'change_amount': _safe_float(r.get('涨跌额')),
                'volume': _safe_float(r.get('成交量')),
                'amount': _safe_float(r.get('成交额')),
                'high': _safe_float(r.get('最高')),
                'low': _safe_float(r.get('最低')),
                'open': _safe_float(r.get('今开')),
                'prev_close': _safe_float(r.get('昨收')),
            })

    except Exception as e:
        logger.warning(f"获取大盘指数失败: {e}")

    _set_cached('market_overview', result)
    return result


def get_money_flow() -> Dict:
    """
    获取市场资金流向（北向资金、主力净流入等）
    使用沪深港通资金流向数据
    """
    cached = _get_cached('money_flow')
    if cached:
        return cached

    result = {
        'north_money': {},
        'sector_flow': [],
        'time': datetime.now().strftime('%H:%M'),
    }

    try:
        df = ak.stock_hsgt_fund_flow_summary_em()
        if df is not None and not df.empty:
            north_total = 0.0
            for _, row in df.iterrows():
                if row.get('资金方向') == '北向' and row.get('板块') in ('沪股通', '深股通'):
                    net_inflow = _safe_float(row.get('成交净买额'))
                    north_total += net_inflow
            result['north_money'] = {
                'north_net_inflow': round(north_total, 2),
                'north_net_buy': round(north_total, 2),
                'date': str(df.iloc[-1].get('交易日', '')),
            }
    except Exception as e:
        logger.warning(f"北向资金获取失败: {e}")

    _set_cached('money_flow', result)
    return result


def get_limit_up_data() -> Dict:
    """
    获取涨跌停数据
    涨停池: stock_zt_pool_em
    跌停池: stock_zt_pool_dtgc_em（大跌股，含跌停）
    """
    cached = _get_cached('limit_up')
    if cached:
        return cached

    today = datetime.now().strftime('%Y%m%d')
    result = {
        'limit_up_count': 0,
        'limit_down_count': 0,
        'limit_up_stocks': [],
        'time': datetime.now().strftime('%H:%M'),
    }

    try:
        up_df = ak.stock_zt_pool_em(date=today)
        if up_df is not None and not up_df.empty:
            result['limit_up_count'] = len(up_df)
            for _, row in up_df.head(10).iterrows():
                result['limit_up_stocks'].append({
                    'name': str(row.get('名称', '')),
                    'code': str(row.get('代码', '')),
                    'change': _safe_float(row.get('涨跌幅')),
                    'reason': str(row.get('涨停统计', '')),
                })
    except Exception as e:
        logger.warning(f"涨停池获取失败: {e}")

    try:
        down_df = ak.stock_zt_pool_dtgc_em(date=today)
        if down_df is not None and not down_df.empty:
            # 大跌股中过滤出跌停（涨跌幅 <= -9.9）
            limit_down = down_df[down_df['涨跌幅'] <= -9.9]
            result['limit_down_count'] = len(limit_down)
    except Exception as e:
        logger.warning(f"大跌股池获取失败: {e}")

    _set_cached('limit_up', result)
    return result


def get_turnover_rate() -> List:
    """
    获取换手率排行榜（活跃股票）
    使用 stock_zt_pool_strong_em（强势股池），包含换手率数据
    """
    cached = _get_cached('turnover_rate')
    if isinstance(cached, list):
        return cached

    result = []
    today = datetime.now().strftime('%Y%m%d')
    try:
        df = ak.stock_zt_pool_strong_em(date=today)
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                code = str(row.get('代码', ''))
                name = str(row.get('名称', ''))
                if not code or code == 'None' or not name or name == 'None':
                    continue
                turnover = _safe_float(row.get('换手率', 0))
                if turnover <= 0:
                    continue
                result.append({
                    'name': name,
                    'code': code,
                    'turnover_rate': round(turnover, 2),
                    'price': _safe_float(row.get('最新价')),
                    'change': _safe_float(row.get('涨跌幅')),
                })
        result.sort(key=lambda x: x['turnover_rate'], reverse=True)
        result = result[:20]
    except Exception as e:
        logger.warning(f"换手率获取失败: {e}")

    _set_cached('turnover_rate', result)
    return result


def get_hot_sectors() -> List:
    """
    获取热点板块（同花顺数据源，已内置降级到东方财富）
    """
    cached = _get_cached('hot_sectors')
    if cached:
        return cached

    from utils.ths_crawler import get_ths_industry_list

    try:
        df = get_ths_industry_list()
        if df is None or df.empty:
            return []

        result = []
        for _, row in df.head(20).iterrows():
            result.append({
                'name': row['板块'],
                'code': row.get('代码', ''),
                'change': _safe_float(row['涨跌幅']),
                'leader': row.get('领涨股', ''),
                'leader_change': _safe_float(row.get('领涨股-涨跌幅', 0)),
            })

        _set_cached('hot_sectors', result)
        return result

    except Exception as e:
        logger.error(f"获取热点板块失败: {e}")
        return []


def get_ai_summary() -> Dict:
    """
    获取 AI 市场简报数据（为 AI 分析准备数据）
    """
    overview = get_market_overview()
    flow = get_money_flow()
    limit = get_limit_up_data()
    sectors = get_hot_sectors()

    summary = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'market_status': '交易中' if 9 <= datetime.now().hour < 15 else '已休市',
        'overview': overview,
        'summary': {
            'shanghai': overview[0] if overview else {},
            'limit_up': limit['limit_up_count'],
            'limit_down': limit['limit_down_count'],
            'north_money': flow.get('north_money', {}),
        },
        'top_sectors': sectors[:10] if sectors else [],
        'hot_sectors': [s for s in sectors if s['change'] > 0][:10] if sectors else [],
    }

    return summary

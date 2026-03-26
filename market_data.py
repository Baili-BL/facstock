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

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


def _get_ak():
    """Lazy import of akshare to avoid py_mini_racer crash on import."""
    import akshare as _ak
    return _ak

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
    if isinstance(cached, list) and len(cached) > 0:
        return cached

    result = []
    try:
        df = _get_ak().stock_zh_index_spot_sina()
        if df is None or df.empty:
            return []

        needed = {
            'sh000001': '上证指数',
            'sz399001': '深证成指',
            'sz399006': '创业板指',
            'sh000688': '科创50',
            'sh000300': '沪深300',
            'sh000016': '上证50',
            'sh000905': '中证500',
            'sh000852': '中证1000',
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

        # 获取上涨/下跌家数（从东方财富市场概况）
        try:
            df_em = _get_ak().stock_zh_a_spot_em()
            if df_em is not None and not df_em.empty:
                total = len(df_em)
                up = int((df_em['涨跌幅'] > 0).sum())
                down = int((df_em['涨跌幅'] < 0).sum())
                flat = total - up - down
                sh = next((x for x in result if x['name'] == '上证指数'), None)
                if sh:
                    sh['up_count'] = up
                    sh['down_count'] = down
                    sh['flat_count'] = flat
        except Exception:
            pass

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
        df = _get_ak().stock_hsgt_fund_flow_summary_em()
        if df is not None and not df.empty:
            hgt_net = 0.0
            sgt_net = 0.0
            north_total = 0.0
            for _, row in df.iterrows():
                net_inflow = _safe_float(row.get('成交净买额'))
                if row.get('板块') == '沪股通':
                    hgt_net += net_inflow
                    north_total += net_inflow
                elif row.get('板块') == '深股通':
                    sgt_net += net_inflow
                    north_total += net_inflow
            result['hgt_net_inflow'] = round(hgt_net, 2)
            result['sgt_net_inflow'] = round(sgt_net, 2)
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
        up_df = _get_ak().stock_zt_pool_em(date=today)
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
        down_df = _get_ak().stock_zt_pool_dtgc_em(date=today)
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
        df = _get_ak().stock_zt_pool_strong_em(date=today)
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


def get_market_snapshot() -> Dict:
    """
    A 股全市场快照：涨跌家数、总成交额、涨幅/跌幅/成交额/涨速榜（含行业）。
    与大盘页「涨跌分布」「股票排行」等同花顺模块对应，单独缓存避免拖慢指数接口。
    """
    cached = _get_cached('market_snapshot')
    if isinstance(cached, dict):
        return cached

    out: Dict = {
        'up_count': 0,
        'down_count': 0,
        'flat_count': 0,
        'total_amount': 0.0,
        'top_gainers': [],
        'top_losers': [],
        'top_by_amount': [],
        'fast_gainers': [],
        'time': datetime.now().strftime('%H:%M'),
    }
    try:
        df = _get_ak().stock_zh_a_spot_em()
        if df is None or df.empty:
            _set_cached('market_snapshot', out)
            return out

        ch_col = '涨跌幅' if '涨跌幅' in df.columns else None
        amt_col = '成交额' if '成交额' in df.columns else None
        spd_col = '涨速' if '涨速' in df.columns else ch_col
        ind_col = '所属行业' if '所属行业' in df.columns else (
            '行业' if '行业' in df.columns else None
        )
        code_col = '代码' if '代码' in df.columns else None
        name_col = '名称' if '名称' in df.columns else None
        price_col = '最新价' if '最新价' in df.columns else None

        if ch_col:
            s = df[ch_col].astype(float)
            out['up_count'] = int((s > 0).sum())
            out['down_count'] = int((s < 0).sum())
            out['flat_count'] = int((s == 0).sum())

        if amt_col:
            out['total_amount'] = float(df[amt_col].astype(float).sum())

        def _pick(row) -> Dict:
            return {
                'code': str(row.get(code_col, '')) if code_col else '',
                'name': str(row.get(name_col, '')) if name_col else '',
                'price': _safe_float(row.get(price_col)) if price_col else 0.0,
                'change': _safe_float(row.get(ch_col)) if ch_col else 0.0,
                'industry': str(row.get(ind_col, '') or '') if ind_col else '',
                'speed': _safe_float(row.get(spd_col)) if spd_col else 0.0,
            }

        if ch_col:
            for _, row in df.nlargest(20, ch_col).iterrows():
                out['top_gainers'].append(_pick(row))
            for _, row in df.nsmallest(15, ch_col).iterrows():
                out['top_losers'].append(_pick(row))
        if amt_col:
            for _, row in df.nlargest(15, amt_col).iterrows():
                out['top_by_amount'].append(_pick(row))
        if spd_col and spd_col in df.columns and spd_col != ch_col:
            for _, row in df.nlargest(15, spd_col).iterrows():
                out['fast_gainers'].append(_pick(row))
    except Exception as e:
        logger.warning(f"市场快照获取失败: {e}")

    _set_cached('market_snapshot', out)
    return out


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
                'heat_display': '--',
            })

        _set_cached('hot_sectors', result)
        return result

    except Exception as e:
        logger.error(f"获取热点板块失败: {e}")
        return []


def get_hot_concept_sectors() -> List[Dict]:
    """
    东方财富概念板块排行（与行业板块结构对齐，便于前端同表展示）
    """
    cached = _get_cached('hot_concept_sectors')
    if isinstance(cached, list):
        return cached

    result: List[Dict] = []
    try:
        df = _get_ak().stock_board_concept_name_em()
        if df is None or df.empty:
            _set_cached('hot_concept_sectors', result)
            return result

        name_c = '板块名称' if '板块名称' in df.columns else '名称'
        code_c = '板块代码' if '板块代码' in df.columns else '代码'
        if '涨跌幅' in df.columns:
            df = df.sort_values(by='涨跌幅', ascending=False)

        for _, row in df.head(40).iterrows():
            heat_raw = 0.0
            for hk in ('成交额', '总市值', '换手率', '成交量'):
                if hk in df.columns:
                    heat_raw = _safe_float(row.get(hk))
                    break
            if heat_raw >= 1e8:
                heat_display = f"{heat_raw / 1e8:.2f}亿"
            elif heat_raw >= 1e4:
                heat_display = f"{heat_raw / 1e4:.2f}万"
            elif heat_raw > 0:
                heat_display = f"{heat_raw:.2f}"
            else:
                heat_display = '--'

            result.append({
                'name': str(row.get(name_c, '') or ''),
                'code': str(row.get(code_c, '') or ''),
                'change': _safe_float(row.get('涨跌幅')),
                'leader': str(row.get('领涨股票', '') or row.get('领涨股', '') or ''),
                'leader_change': _safe_float(row.get('领涨股票-涨跌幅', row.get('领涨股-涨跌幅', 0))),
                'heat_display': heat_display,
            })
    except Exception as e:
        logger.warning(f"概念板块获取失败: {e}")

    _set_cached('hot_concept_sectors', result)
    return result


def get_sector_main_fund_flow(sector_kind: str) -> List[Dict]:
    """
    板块主力净流入（单位：亿），东方财富 stock_sector_fund_flow_rank。
    sector_kind: industry | concept | region → 行业资金流 / 概念资金流 / 地域资金流
    返回 6 条：净流入前三 + 净流出前三（柱状图用）。
    """
    sector_type_map = {
        'industry': '行业资金流',
        'concept': '概念资金流',
        'region': '地域资金流',
    }
    sk = (sector_kind or 'industry').lower()
    st = sector_type_map.get(sk, '行业资金流')
    cache_key = f'sector_main_fund_{sk}'
    cached = _get_cached(cache_key)
    if isinstance(cached, list):
        return cached

    result: List[Dict] = []
    try:
        df = _get_ak().stock_sector_fund_flow_rank(indicator='今日', sector_type=st)
        if df is None or df.empty:
            _set_cached(cache_key, result)
            return result

        col = '今日主力净流入-净额'
        nm = '名称'
        ch = '今日涨跌幅'
        if col not in df.columns:
            logger.warning('板块资金流缺少列: %s', col)
            _set_cached(cache_key, result)
            return result

        df = df.copy()
        df['_net'] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['_net']).sort_values('_net', ascending=False).reset_index(drop=True)
        n = len(df)
        if n == 0:
            _set_cached(cache_key, result)
            return result

        def _row(r) -> Dict:
            net_yuan = float(r['_net'])
            return {
                'name': str(r.get(nm, '') or ''),
                'net_yi': round(net_yuan / 1e8, 2),
                'change': _safe_float(r.get(ch, 0)),
            }

        if n <= 6:
            for _, r in df.iterrows():
                result.append(_row(r))
        else:
            for _, r in df.head(3).iterrows():
                result.append(_row(r))
            for _, r in df.tail(3).sort_values('_net', ascending=False).iterrows():
                result.append(_row(r))
    except Exception as e:
        logger.warning(f'板块主力净流入获取失败: {e}')

    _set_cached(cache_key, result)
    return result


def compute_macro_sentiment() -> Dict:
    """
    综合市场量化指标 + 新闻情感，计算宏观情绪评分（0-100）。
    公式：
      SENTIMENT_SCORE = 50
        + (上涨% - 0.5) × 40
        + (涨停数 - 跌停数) / 10
        + (北向净流入 > 0 ? +8 : -8)
        + (新闻情感分 - 50) / 5
    上限 92，下限 38。
    RISK_LEVEL: ≥62→MEDIUM, 48-61→MEDIUM-HIGH, <48→ELEVATED
    """
    try:
        snapshot = get_market_snapshot()
        flow = get_money_flow()
        limit = get_limit_up_data()
        overview = get_market_overview()

        # ── 1. 涨跌家数 ────────────────────────────────────────────────
        up   = int(snapshot.get('up_count', 0)   or 0)
        down = int(snapshot.get('down_count', 0) or 0)
        flat = int(snapshot.get('flat_count', 0)  or 0)
        total = max(1, up + down + flat)
        up_pct   = up   / total
        down_pct = down / total

        # ── 2. 涨跌停 ────────────────────────────────────────────────
        limit_up   = int(limit.get('limit_up_count', 0)   or 0)
        limit_down = int(limit.get('limit_down_count', 0) or 0)
        limit_diff = limit_up - limit_down

        # ── 3. 北向资金 ──────────────────────────────────────────────
        north_net = float(
            flow.get('north_money', {})
               .get('north_net_inflow', 0)
        )
        north_bonus = 8 if north_net >= 0 else -8

        # ── 4. 新闻情感 ───────────────────────────────────────────────
        try:
            from ticai.news_fetcher import get_market_news_summary
            news_summary = get_market_news_summary()
            news_score = float(news_summary.get('sentiment_score', 50))
        except Exception:
            news_score = 50.0
        news_bonus = (news_score - 50) / 5

        # ── 5. 综合评分 ──────────────────────────────────────────────
        raw = 50 \
            + (up_pct - 0.5) * 40 \
            + limit_diff / 10 \
            + north_bonus \
            + news_bonus
        raw = max(38, min(92, raw))
        score = round(raw)

        # ── 6. 风险等级 ──────────────────────────────────────────────
        if score >= 62:
            risk_level = 'MEDIUM'
        elif score >= 48:
            risk_level = 'MEDIUM-HIGH'
        else:
            risk_level = 'ELEVATED'

        # ── 7. 市场广度描述 ──────────────────────────────────────────
        breadth_desc = (
            '市场普涨，赚钱效应较强'
            if up_pct > 0.6
            else '市场普跌，赚钱效应较弱'
            if down_pct > 0.6
            else '多空分化，结构性行情'
        )

        # ── 8. 资金面简述 ────────────────────────────────────────────
        if north_net >= 5e8:
            money_desc = '北向资金大幅净流入，外资积极'
        elif north_net >= 0:
            money_desc = '北向资金小幅净流入'
        elif north_net >= -5e8:
            money_desc = '北向资金小幅净流出'
        else:
            money_desc = '北向资金大幅净流出，外资偏谨慎'

        # ── 9. 生成摘要段落 ──────────────────────────────────────────
        tone_words = {
            'MEDIUM':       '中性偏多',
            'MEDIUM-HIGH':  '偏谨慎',
            'ELEVATED':     '谨慎防御',
        }
        tone = tone_words[risk_level]

        if up_pct > 0.55 and limit_up > 50:
            market_desc = '市场情绪高涨，涨停家数较多，短线做多氛围浓'
        elif down_pct > 0.55:
            market_desc = '市场情绪偏弱，赚钱效应不足，注意控制仓位'
        else:
            market_desc = breadth_desc + '，' + money_desc

        summary_text = (
            f'今日{tone}。'
            f'上涨 {up} 家 / 下跌 {down} 家（涨停 {limit_up} / 跌停 {limit_down}）。'
            f'{market_desc}。'
            f'建议关注高股息蓝筹与业绩确定性品种。'
        )

        # ── 10. 上证指数涨跌（用于对比参考） ─────────────────────────
        sh = next((x for x in overview if x.get('name') == '上证指数'), {})
        sh_change = sh.get('change', 0)
        sh_desc = (
            f'上证指数涨 {_fmt(sh_change)}%，'
            if sh_change > 0.05
            else f'上证指数跌 {abs(_fmt(sh_change))}%，'
            if sh_change < -0.05
            else '上证指数基本持平，'
        ) if sh else ''

        return {
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'sentiment_score': score,
            'risk_level': risk_level,
            'summary_text': sh_desc + summary_text,
            'breadth': {
                'up': up, 'down': down, 'flat': flat,
                'up_pct': round(up_pct * 100, 1),
                'down_pct': round(down_pct * 100, 1),
            },
            'limit': {
                'up': limit_up,
                'down': limit_down,
                'diff': limit_diff,
            },
            'north_money': {
                'net': round(north_net, 2),
                'bonus': north_bonus,
            },
            'news_score': round(news_score, 1),
            'raw_score': round(raw, 2),
        }
    except Exception as e:
        logger.error(f'compute_macro_sentiment failed: {e}')
        return {
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'sentiment_score': 50,
            'risk_level': 'MEDIUM',
            'summary_text': '数据加载中，请稍后刷新',
            'breadth': {'up': 0, 'down': 0, 'flat': 0, 'up_pct': 0, 'down_pct': 0},
            'limit': {'up': 0, 'down': 0, 'diff': 0},
            'north_money': {'net': 0, 'bonus': 0},
            'news_score': 50,
            'raw_score': 50,
        }


def _fmt(v) -> str:
    if v is None:
        return '--'
    return f'{v:.2f}'


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

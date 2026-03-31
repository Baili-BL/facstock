#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自选股票技术指标策略（优先 TA-Lib，缺失时用 pandas/numpy 等价实现）。

仅对 watchlist 中的代码拉 K 线并计算信号，供 /api/watchlist/strategy/* 使用。
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    import talib

    HAS_TALIB = True
except ImportError:
    talib = None  # type: ignore
    HAS_TALIB = False


def talib_status() -> Dict[str, Any]:
    return {'available': HAS_TALIB, 'library': 'TA-Lib' if HAS_TALIB else 'pandas/numpy'}


def _rsi_wilder(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder RSI（pandas）；连涨时 avg_loss 为 0 时 RSI 视为 100。"""
    s = pd.Series(close.astype(float), dtype=float)
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    ag = avg_gain.to_numpy(dtype=float)
    al = avg_loss.to_numpy(dtype=float)
    rs = np.divide(ag, al, out=np.full_like(ag, np.nan), where=(al > 0))
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = np.where((al == 0) & (ag > 0), 100.0, rsi)
    rsi = np.where((ag == 0) & (al > 0), 0.0, rsi)
    return rsi.astype(float)


def _sma(arr: np.ndarray, period: int) -> np.ndarray:
    if HAS_TALIB:
        return talib.SMA(arr.astype(float), timeperiod=period)
    return pd.Series(arr, dtype=float).rolling(period, min_periods=period).mean().to_numpy()


def _ema(arr: np.ndarray, period: int) -> np.ndarray:
    if HAS_TALIB:
        return talib.EMA(arr.astype(float), timeperiod=period)
    return pd.Series(arr, dtype=float).ewm(span=period, adjust=False).mean().to_numpy()


def _macd(close: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    if HAS_TALIB:
        macd, signal, hist = talib.MACD(close.astype(float), fastperiod=12, slowperiod=26, signalperiod=9)
        return macd, signal, hist
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    macd = ema12 - ema26
    sig = pd.Series(macd).ewm(span=9, adjust=False).mean().to_numpy()
    hist = macd - sig
    return macd, sig, hist


def _bbands(close: np.ndarray, period: int = 20, nbdev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    if HAS_TALIB:
        u, m, l = talib.BBANDS(close.astype(float), timeperiod=period, nbdevup=nbdev, nbdevdn=nbdev, matype=0)
        return u, m, l
    mid = pd.Series(close, dtype=float).rolling(period, min_periods=period).mean()
    std = pd.Series(close, dtype=float).rolling(period, min_periods=period).std()
    upper = (mid + nbdev * std).to_numpy()
    lower = (mid - nbdev * std).to_numpy()
    return upper, mid.to_numpy(), lower


def strategy_rsi_extreme(df: pd.DataFrame) -> Dict[str, Any]:
    c = df['close'].values.astype(float)
    if len(c) < 20:
        return {'signal': 'unknown', 'label_zh': '数据不足', 'detail': 'K 线少于 20 根'}
    rsi = talib.RSI(c, timeperiod=14) if HAS_TALIB else _rsi_wilder(c, 14)
    last = None
    for v in reversed(rsi):
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            try:
                last = float(v)
                break
            except (TypeError, ValueError):
                continue
    if last is None:
        return {'signal': 'unknown', 'label_zh': '计算失败', 'detail': 'RSI 无效'}
    if last >= 70:
        return {'signal': 'overbought', 'label_zh': '超买区', 'detail': f'RSI={last:.1f}（≥70）'}
    if last <= 30:
        return {'signal': 'oversold', 'label_zh': '超卖区', 'detail': f'RSI={last:.1f}（≤30）'}
    return {'signal': 'neutral', 'label_zh': '中性', 'detail': f'RSI={last:.1f}'}


def strategy_ma_cross(df: pd.DataFrame) -> Dict[str, Any]:
    c = df['close'].values.astype(float)
    if len(c) < 25:
        return {'signal': 'unknown', 'label_zh': '数据不足', 'detail': 'K 线少于 25 根'}
    ma5 = _sma(c, 5)
    ma20 = _sma(c, 20)
    if np.isnan(ma5[-1]) or np.isnan(ma20[-1]):
        return {'signal': 'unknown', 'label_zh': '计算失败', 'detail': '均线无效'}
    # 上一根与当前根比较，检测交叉
    a0, a1 = float(ma5[-2]), float(ma5[-1])
    b0, b1 = float(ma20[-2]), float(ma20[-1])
    if a0 <= b0 and a1 > b1:
        return {'signal': 'golden_cross', 'label_zh': '金叉', 'detail': 'MA5 上穿 MA20'}
    if a0 >= b0 and a1 < b1:
        return {'signal': 'death_cross', 'label_zh': '死叉', 'detail': 'MA5 下穿 MA20'}
    if a1 > b1:
        return {'signal': 'bull_align', 'label_zh': '多头排列', 'detail': 'MA5 在 MA20 上方'}
    return {'signal': 'bear_align', 'label_zh': '空头排列', 'detail': 'MA5 在 MA20 下方'}


def strategy_breakout_20(df: pd.DataFrame) -> Dict[str, Any]:
    h = df['high'].values.astype(float)
    l = df['low'].values.astype(float)
    c = df['close'].values.astype(float)
    if len(c) < 22:
        return {'signal': 'unknown', 'label_zh': '数据不足', 'detail': 'K 线少于 22 根'}
    prev_high = np.nanmax(h[-22:-1])
    prev_low = np.nanmin(l[-22:-1])
    last = float(c[-1])
    if last >= prev_high:
        return {'signal': 'break_high', 'label_zh': '突破前高', 'detail': f'收盘突破近20日高 {prev_high:.2f}'}
    if last <= prev_low:
        return {'signal': 'break_low', 'label_zh': '跌破前低', 'detail': f'收盘跌破近20日低 {prev_low:.2f}'}
    return {'signal': 'inside', 'label_zh': '区间内', 'detail': '未触及20日极值'}


def strategy_macd_turn(df: pd.DataFrame) -> Dict[str, Any]:
    c = df['close'].values.astype(float)
    if len(c) < 40:
        return {'signal': 'unknown', 'label_zh': '数据不足', 'detail': 'K 线少于 40 根'}
    _, _, hist = _macd(c)
    if len(hist) < 3 or np.isnan(hist[-1]):
        return {'signal': 'unknown', 'label_zh': '计算失败', 'detail': 'MACD 无效'}
    h0, h1 = float(hist[-2]), float(hist[-1])
    if h0 < 0 <= h1:
        return {'signal': 'macd_bull', 'label_zh': '柱翻红', 'detail': 'MACD 柱状线由负转正'}
    if h0 > 0 >= h1:
        return {'signal': 'macd_bear', 'label_zh': '柱翻绿', 'detail': 'MACD 柱状线由正转负'}
    if h1 > 0:
        return {'signal': 'macd_pos', 'label_zh': '多头柱', 'detail': f'Hist={h1:.4f}'}
    return {'signal': 'macd_neg', 'label_zh': '空头柱', 'detail': f'Hist={h1:.4f}'}


def strategy_bollinger_position(df: pd.DataFrame) -> Dict[str, Any]:
    c = df['close'].values.astype(float)
    if len(c) < 22:
        return {'signal': 'unknown', 'label_zh': '数据不足', 'detail': 'K 线少于 22 根'}
    upper, mid, lower = _bbands(c, 20, 2.0)
    last = float(c[-1])
    u, m, lo = float(upper[-1]), float(mid[-1]), float(lower[-1])
    if np.isnan(u) or np.isnan(lo):
        return {'signal': 'unknown', 'label_zh': '计算失败', 'detail': '布林带无效'}
    if last <= lo * 1.002:
        return {'signal': 'near_lower', 'label_zh': '贴近下轨', 'detail': f'收盘接近下轨 {lo:.2f}'}
    if last >= u * 0.998:
        return {'signal': 'near_upper', 'label_zh': '贴近上轨', 'detail': f'收盘接近上轨 {u:.2f}'}
    return {'signal': 'mid_band', 'label_zh': '中轨附近', 'detail': f'中轨 {m:.2f}'}


StrategyFn = Callable[[pd.DataFrame], Dict[str, Any]]

STRATEGY_CATALOG: List[Dict[str, str]] = [
    {
        'id': 'rsi_extreme',
        'name': 'RSI 超买超卖',
        'description': 'RSI(14)：>70 超买，<30 超卖（与告警开关对应）',
    },
    {
        'id': 'ma_cross',
        'name': '均线金叉 / 死叉',
        'description': 'MA5 与 MA20 位置与交叉',
    },
    {
        'id': 'breakout_20',
        'name': '20 日区间突破',
        'description': '收盘价相对近 20 日（不含当日）高低点',
    },
    {
        'id': 'macd_turn',
        'name': 'MACD 柱状拐点',
        'description': 'MACD 柱状线由负转正 / 由正转负',
    },
    {
        'id': 'bollinger_position',
        'name': '布林带位置',
        'description': '收盘价相对布林上下轨（20,2）',
    },
]

STRATEGY_RUNNERS: Dict[str, StrategyFn] = {
    'rsi_extreme': strategy_rsi_extreme,
    'ma_cross': strategy_ma_cross,
    'breakout_20': strategy_breakout_20,
    'macd_turn': strategy_macd_turn,
    'bollinger_position': strategy_bollinger_position,
}


def get_catalog() -> List[Dict[str, str]]:
    return list(STRATEGY_CATALOG)


def run_strategy_for_code(
    code: str,
    name: str,
    strategy_id: str,
    df: Optional[pd.DataFrame],
) -> Dict[str, Any]:
    base = {
        'code': code,
        'name': name or code,
        'strategy_id': strategy_id,
    }
    fn = STRATEGY_RUNNERS.get(strategy_id)
    if fn is None:
        return {**base, 'error': '未知策略', 'signal': 'error', 'label_zh': '错误', 'detail': strategy_id}
    if df is None or df.empty or len(df) < 15:
        return {
            **base,
            'error': '无K线',
            'signal': 'no_data',
            'label_zh': '无数据',
            'detail': '无法获取日线或数据过短',
        }
    try:
        out = fn(df)
        return {**base, **out, 'last_close': float(df['close'].iloc[-1])}
    except Exception as e:
        logger.warning('watchlist strategy %s %s: %s', strategy_id, code, e)
        return {**base, 'error': str(e), 'signal': 'error', 'label_zh': '异常', 'detail': str(e)}


def run_strategy_on_watchlist(
    strategy_id: str,
    stocks: List[Dict],
    fetch_df: Callable[[str], Optional[pd.DataFrame]],
) -> Dict[str, Any]:
    if strategy_id not in STRATEGY_RUNNERS:
        return {'error': f'未知策略: {strategy_id}'}

    items: List[Dict[str, Any]] = []
    for s in stocks:
        code = str(s.get('stock_code') or s.get('code') or '').strip()
        if not code or len(code) != 6:
            continue
        nm = str(s.get('stock_name') or s.get('name') or '')
        df = fetch_df(code)
        items.append(run_strategy_for_code(code, nm, strategy_id, df))

    meta = talib_status()
    title = next((x['name'] for x in STRATEGY_CATALOG if x['id'] == strategy_id), strategy_id)
    return {
        'strategy_id': strategy_id,
        'strategy_name': title,
        'talib': meta,
        'count': len(items),
        'items': items,
    }


def _strategy_display_name(strategy_id: str) -> str:
    return next((x['name'] for x in STRATEGY_CATALOG if x['id'] == strategy_id), strategy_id)


def run_multi_strategies_on_watchlist(
    strategy_ids: List[str],
    stocks: List[Dict],
    fetch_df: Callable[[str], Optional[pd.DataFrame]],
) -> Dict[str, Any]:
    """同一批 K 线对多策略分别计算，按股票合并为 hits 列表。"""
    uniq: List[str] = []
    seen = set()
    for sid in strategy_ids:
        s = str(sid or '').strip()
        if not s or s in seen:
            continue
        if s not in STRATEGY_RUNNERS:
            return {'error': f'未知策略: {s}'}
        seen.add(s)
        uniq.append(s)

    if not uniq:
        return {'error': '未选择有效策略'}

    items: List[Dict[str, Any]] = []
    for s in stocks:
        code = str(s.get('stock_code') or s.get('code') or '').strip()
        if not code or len(code) != 6:
            continue
        nm = str(s.get('stock_name') or s.get('name') or '')
        df = fetch_df(code)
        hits: List[Dict[str, Any]] = []
        for sid in uniq:
            row = run_strategy_for_code(code, nm, sid, df)
            hits.append(
                {
                    'strategy_id': sid,
                    'strategy_name': _strategy_display_name(sid),
                    'signal': row.get('signal'),
                    'label_zh': row.get('label_zh'),
                    'detail': row.get('detail'),
                    'error': row.get('error'),
                }
            )
        items.append({'code': code, 'name': nm, 'hits': hits})

    meta = talib_status()
    names = '、'.join(_strategy_display_name(s) for s in uniq)
    return {
        'strategy_ids': uniq,
        'strategy_id': uniq[0],
        'strategy_name': names,
        'talib': meta,
        'count': len(items),
        'items': items,
    }

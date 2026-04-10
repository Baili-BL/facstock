#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化回测引擎
- 后端：talib 指标计算（pandas 降级）
- 前端：回测结果经 /api/backtest 接口返回，用 lightweight-charts 在浏览器端可视化
  （权益曲线、回撤曲线、买卖点标注 K 线）
- 不持久化数据，每次请求独立拉取 K 线、计算、回测、返回
"""

from __future__ import annotations

import datetime
import logging
import math
import time as _time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import warnings
warnings.filterwarnings('ignore', category=FutureWarning, module='pandas')

logger = logging.getLogger(__name__)

try:
    import backtrader as bt

    HAS_BT = True
except ImportError:
    bt = None  # type: ignore
    HAS_BT = False

try:
    import talib

    HAS_TALIB = True
except ImportError:
    talib = None  # type: ignore
    HAS_TALIB = False


# ═══════════════════════════════════════════════════════════════════════════════
# 指标函数（talib 优先，pandas 降级）
# ═══════════════════════════════════════════════════════════════════════════════

def _ema(arr: np.ndarray, period: int) -> np.ndarray:
    if HAS_TALIB and arr.dtype.kind in ('f', 'i'):
        return talib.EMA(arr.astype(float), timeperiod=period)
    return pd.Series(arr, dtype=float).ewm(span=period, adjust=False).mean().to_numpy()


def _sma(arr: np.ndarray, period: int) -> np.ndarray:
    if HAS_TALIB and arr.dtype.kind in ('f', 'i'):
        return talib.SMA(arr.astype(float), timeperiod=period)
    return pd.Series(arr, dtype=float).rolling(period, min_periods=period).mean().to_numpy()


def _rsi(arr: np.ndarray, period: int = 14) -> np.ndarray:
    if HAS_TALIB and arr.dtype.kind in ('f', 'i'):
        return talib.RSI(arr.astype(float), timeperiod=period)
    delta = pd.Series(arr).diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    al = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg / al.where(al != 0, other=np.nan)
    return (100 - 100 / (1 + rs)).fillna(50).infer_objects(copy=False).to_numpy()


def _macd(
    close: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    if HAS_TALIB:
        m, s, h = talib.MACD(
            close.astype(float), fastperiod=12, slowperiod=26, signalperiod=9
        )
        return m, s, h
    e12 = _ema(close, 12)
    e26 = _ema(close, 26)
    macd = e12 - e26
    sig = pd.Series(macd).ewm(span=9, adjust=False).mean().to_numpy()
    return macd, sig, macd - sig


def _bbands(
    close: np.ndarray, period: int = 20, nbdev: float = 2.0
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    if HAS_TALIB:
        u, m, l = talib.BBANDS(
            close.astype(float),
            timeperiod=period,
            nbdevup=nbdev,
            nbdevdn=nbdev,
            matype=0,
        )
        return u, m, l
    mid = pd.Series(close).rolling(period).mean()
    std = pd.Series(close).rolling(period).std()
    return (
        (mid + nbdev * std).to_numpy(),
        mid.to_numpy(),
        (mid - nbdev * std).to_numpy(),
    )


def _atr(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
) -> np.ndarray:
    if HAS_TALIB:
        return talib.ATR(high.astype(float), low.astype(float), close.astype(float), timeperiod=period)
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1]),
        ),
    )
    # prepend 0 so length matches high/low/close arrays
    padded = np.concatenate([[0.0], tr])
    rolling = pd.Series(padded).rolling(period, min_periods=period).mean().fillna(0)
    return rolling.to_numpy()


def _kdjk(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 9
) -> Tuple[np.ndarray, np.ndarray]:
    if HAS_TALIB:
        k, d = talib.STOCH(
            high.astype(float),
            low.astype(float),
            close.astype(float),
            fastk_period=period,
            slowk_period=3,
            slowk_matype=0,
            slowd_period=3,
            slowd_matype=0,
        )
        return k, d
    n = period
    hv = pd.Series(high).rolling(n).max()
    lv = pd.Series(low).rolling(n).min()
    rsv = ((close - lv) / (hv - lv) * 100).fillna(50).infer_objects(copy=False)
    k = rsv.ewm(alpha=1.0 / 3, adjust=False).mean().to_numpy()
    d = pd.Series(k).ewm(alpha=1.0 / 3, adjust=False).mean().to_numpy()
    return k, d


# ═══════════════════════════════════════════════════════════════════════════════
# 内置策略模板（每个返回 (long_condition, short_condition) 布尔 Series）
# ═══════════════════════════════════════════════════════════════════════════════

TEMPLATE_CATALOG: List[Dict[str, Any]] = [
    {
        'id': 'ma_cross',
        'name': '均线交叉',
        'description': 'MA5 上穿 MA20 买入，下穿卖出',
        'params': [
            {'id': 'fast_ma', 'name': '快速均线', 'type': 'int', 'default': 5, 'min': 2, 'max': 60},
            {'id': 'slow_ma', 'name': '慢速均线', 'type': 'int', 'default': 20, 'min': 5, 'max': 250},
        ],
    },
    {
        'id': 'rsi_extreme',
        'name': 'RSI 超买超卖',
        'description': 'RSI<30 买入，RSI>70 卖出',
        'params': [
            {'id': 'rsi_period', 'name': 'RSI周期', 'type': 'int', 'default': 14, 'min': 2, 'max': 50},
            {'id': 'rsi_buy', 'name': '买入阈值', 'type': 'int', 'default': 30, 'min': 10, 'max': 50},
            {'id': 'rsi_sell', 'name': '卖出阈值', 'type': 'int', 'default': 70, 'min': 50, 'max': 90},
        ],
    },
    {
        'id': 'bollinger_break',
        'name': '布林带突破',
        'description': '收盘上穿布林上轨买入，下穿下轨卖出',
        'params': [
            {'id': 'bb_period', 'name': '布林周期', 'type': 'int', 'default': 20, 'min': 5, 'max': 60},
            {'id': 'bb_std', 'name': '标准差倍数', 'type': 'float', 'default': 2.0, 'min': 0.5, 'max': 4.0},
        ],
    },
    {
        'id': 'macd_cross',
        'name': 'MACD 金叉死叉',
        'description': 'MACD 线从下方上穿信号线买入，从上方下穿卖出',
        'params': [],
    },
    {
        'id': 'kdj_extreme',
        'name': 'KDJ 超买超卖',
        'description': 'K<20 超卖买入，K>80 超买卖出',
        'params': [
            {'id': 'kdj_k_period', 'name': 'K周期', 'type': 'int', 'default': 9, 'min': 2, 'max': 30},
            {'id': 'kdj_buy', 'name': '超卖线', 'type': 'int', 'default': 20, 'min': 5, 'max': 50},
            {'id': 'kdj_sell', 'name': '超买线', 'type': 'int', 'default': 80, 'min': 50, 'max': 95},
        ],
    },
    {
        'id': 'atr_trailing',
        'name': 'ATR 追踪止损',
        'description': 'ATR 动态止损：买入后以买入价-2*ATR 跟踪止损',
        'params': [
            {'id': 'atr_period', 'name': 'ATR周期', 'type': 'int', 'default': 14, 'min': 5, 'max': 50},
            {'id': 'atr_mult', 'name': 'ATR倍数', 'type': 'float', 'default': 2.0, 'min': 0.5, 'max': 5.0},
        ],
    },
    {
        'id': 'custom_bt',
        'name': '自定义因子 (backtrader)',
        'description': '使用 backtrader 编写策略类，通过 self.buy()/self.sell() 下单；K 线仍由 akshare 拉取，不落库',
        'params': [
            {
                'id': 'user_code',
                'name': '策略代码',
                'type': 'code',
                'default': (
                    'class CustomStrategy(bt.Strategy):\n'
                    '    params = (("rsi_period", 14),)\n'
                    '    def __init__(self):\n'
                    '        self.rsi = bt.indicators.RSI(self.data.close, period=self.p.rsi_period)\n'
                    '    def next(self):\n'
                    '        if not self.position:\n'
                    '            if self.rsi[0] < 30:\n'
                    '                self.buy()\n'
                    '        else:\n'
                    '            if self.rsi[0] > 70:\n'
                    '                self.sell()\n'
                ),
                'min': 0,
                'max': 0,
            },
            {'id': 'rsi_period', 'name': 'RSI周期', 'type': 'int', 'default': 14, 'min': 2, 'max': 50},
        ],
    },
]


def _build_signal_df(
    df: pd.DataFrame, template_id: str, params: Dict[str, Any]
) -> pd.DataFrame:
    """
    按策略模板计算信号 DataFrame（含 'long' / 'short' 布尔列），
    index 与 df 对齐。
    """
    d = df.copy()
    c = d['close'].values.astype(float)
    h = d['high'].values.astype(float)
    lo = d['low'].values.astype(float)

    if template_id == 'ma_cross':
        fast = _sma(c, int(params.get('fast_ma', 5)))
        slow = _sma(c, int(params.get('slow_ma', 20)))
        long = pd.Series(fast > slow, index=d.index).shift(1).fillna(False).astype(bool).infer_objects(copy=False)
        short = pd.Series(fast < slow, index=d.index).shift(1).fillna(False).astype(bool).infer_objects(copy=False)

    elif template_id == 'rsi_extreme':
        rsi = _rsi(c, int(params.get('rsi_period', 14)))
        buy_thr = float(params.get('rsi_buy', 30))
        sell_thr = float(params.get('rsi_sell', 70))
        rsi_s = pd.Series(rsi, index=d.index)
        long = (rsi_s < buy_thr).shift(1).fillna(False).astype(bool).infer_objects(copy=False)
        short = (rsi_s > sell_thr).shift(1).fillna(False).astype(bool).infer_objects(copy=False)

    elif template_id == 'bollinger_break':
        u, m, l = _bbands(c, int(params.get('bb_period', 20)), float(params.get('bb_std', 2.0)))
        u_s = pd.Series(u, index=d.index)
        l_s = pd.Series(l, index=d.index)
        c_s = pd.Series(c, index=d.index)
        long = (c_s > u_s).shift(1).fillna(False).astype(bool).infer_objects(copy=False)
        short = (c_s < l_s).shift(1).fillna(False).astype(bool).infer_objects(copy=False)

    elif template_id == 'macd_cross':
        _, sig, hist = _macd(c)
        hist_s = pd.Series(hist, index=d.index)
        macd_line = pd.Series(_macd(c)[0], index=d.index)
        sig_s = pd.Series(sig, index=d.index)
        above = macd_line > sig_s
        long = (above) & (~above.shift(1).fillna(False))
        long = long.shift(1).fillna(False).astype(bool).infer_objects(copy=False)
        short = (~above) & (above.shift(1).fillna(False))
        short = short.shift(1).fillna(False).astype(bool).infer_objects(copy=False)

    elif template_id == 'kdj_extreme':
        k, d_kdj = _kdjk(h, lo, c, int(params.get('kdj_k_period', 9)))
        buy_thr = float(params.get('kdj_buy', 20))
        sell_thr = float(params.get('kdj_sell', 80))
        k_s = pd.Series(k, index=d.index)
        long = (k_s < buy_thr).shift(1).fillna(False).astype(bool).infer_objects(copy=False)
        short = (k_s > sell_thr).shift(1).fillna(False).astype(bool).infer_objects(copy=False)

    elif template_id == 'atr_trailing':
        atr_arr = _atr(h, lo, c, int(params.get('atr_period', 14)))
        atr_s = pd.Series(atr_arr, index=d.index)
        mult = float(params.get('atr_mult', 2.0))
        entry_price = d['close'].shift(1)
        stop_price = entry_price - mult * atr_s.shift(1)
        close_s = pd.Series(c, index=d.index)
        long = pd.Series(True, index=d.index).shift(1).fillna(False).astype(bool).infer_objects(copy=False)
        short = (close_s < stop_price).shift(1).fillna(False).astype(bool).infer_objects(copy=False)

    else:
        long = pd.Series(False, index=d.index)
        short = pd.Series(False, index=d.index)

    d['long'] = long
    d['short'] = short
    return d.dropna()


# ═══════════════════════════════════════════════════════════════════════════════
# 核心回测逻辑（纯 pandas，绕开 backtrader 复杂性）
# ═══════════════════════════════════════════════════════════════════════════════

def _safe(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 4)
    except (TypeError, ValueError):
        return None


def _date_to_ts(d: Any) -> int:
    if isinstance(d, str):
        dt = datetime.datetime.strptime(d[:10], '%Y-%m-%d').replace(
            tzinfo=datetime.timezone(datetime.timedelta(hours=8))
        )
        return int(dt.timestamp())
    if hasattr(d, 'timestamp'):
        return int(d.timestamp())
    if isinstance(d, (int, float)):
        return int(d)
    return 0


def run_backtest(
    df: pd.DataFrame,
    template_id: str,
    params: Dict[str, Any],
    initial_cash: float = 100000.0,
    commission_pct: float = 0.001,
) -> Dict[str, Any]:
    """
    纯 pandas 回测（无需 backtrader），流程：
    1. 按模板计算 long/short 信号
    2. 逐日模拟：买入 → 持仓 → 卖出 → 空仓
    3. 计算权益曲线 + 回撤 + 统计指标

    df 要求列：date, open, high, low, close, volume
    """
    if df is None or len(df) < 30:
        return {'error': '数据不足，需至少 30 条 K 线', 'success': False}

    # 去重 + 排序
    d = df.copy()
    if 'date' in d.columns:
        d = d.dropna(subset=['date']).sort_values('date').reset_index(drop=True)

    sig_df = _build_signal_df(d, template_id, params)
    if len(sig_df) < 10:
        return {'error': '信号不足，回测区间过短', 'success': False}

    cash = float(initial_cash)
    position = 0.0      # 持仓股数
    entry_price = 0.0   # 买入价
    equity = [float(initial_cash)]
    drawdown = [0.0]
    peak = float(initial_cash)
    trades: List[Dict] = []
    markers: List[Dict] = {}  # date_str -> {'buy': ts, 'sell': ts}

    buy_date = None
    buy_price = 0.0
    last_sell_idx = 0

    for i, row in sig_df.iterrows():
        close = float(row['close'])
        dt = str(row.get('date', ''))[:10]
        ts = _date_to_ts(row.get('date'))

        equity.append(float(cash) + position * float(close))
        cur_equity = equity[-1]
        peak = max(peak, cur_equity)
        dd = (peak - cur_equity) / peak if peak > 0 else 0.0
        drawdown.append(round(dd, 6))

        if position <= 0 and row.get('long') and not row.get('short'):
            vol = int(cash * 0.95 / close)
            if vol <= 0:
                continue
            cost = vol * close * (1 + commission_pct)
            if cost > cash:
                vol = int(cash * 0.95 / (close * (1 + commission_pct)))
            if vol <= 0:
                continue
            cost = vol * close * (1 + commission_pct)
            cash -= cost
            position = vol
            entry_price = close
            buy_date = dt
            buy_price = close
            last_sell_idx = i
            markers[dt] = {'buy': ts}

        elif position > 0 and row.get('short'):
            proceeds = position * close * (1 - commission_pct)
            pnl = proceeds + cash - float(initial_cash)
            trades.append({
                'buyDate': buy_date,
                'sellDate': dt,
                'buyPrice': round(buy_price, 4),
                'sellPrice': round(close, 4),
                'pnlPct': round((close - buy_price) / buy_price * 100, 2),
                'pnlAbs': round(pnl, 2),
                'holdDays': max(1, i - last_sell_idx),
            })
            cash += proceeds
            position = 0
            markers[dt] = {'sell': ts}
            last_sell_idx = i

    # 平仓（回测结束时未卖出）
    if position > 0 and len(sig_df) > 0:
        last_row = sig_df.iloc[-1]
        close = float(last_row['close'])
        dt = str(last_row.get('date', ''))[:10]
        proceeds = position * close * (1 - commission_pct)
        pnl = proceeds + cash - float(initial_cash)
        trades.append({
            'buyDate': buy_date,
            'sellDate': dt,
            'buyPrice': round(buy_price, 4),
            'sellPrice': round(close, 4),
            'pnlPct': round((close - buy_price) / buy_price * 100, 2),
            'pnlAbs': round(pnl, 2),
            'holdDays': max(1, len(sig_df) - last_sell_idx),
        })
        cash += proceeds
        position = 0

    equity = equity[1:]  # 去掉初始虚拟点
    drawdown = drawdown[1:]

    # ── 统计指标 ─────────────────────────────────────────────────────────────
    total_return = (cash - float(initial_cash)) / float(initial_cash) * 100
    n = len(equity)
    returns_arr = np.diff(equity) / equity[:-1]
    returns_arr = returns_arr[np.isfinite(returns_arr)]

    annual_return = total_return / max(n / 252, 0.01)

    if len(returns_arr) > 1 and np.std(returns_arr, ddof=1) > 1e-10:
        sharpe = float(np.mean(returns_arr) / np.std(returns_arr, ddof=1) * np.sqrt(252))
    else:
        sharpe = 0.0

    max_dd = float(max(drawdown)) * 100 if drawdown else 0.0
    max_dd_pct = max_dd

    win_trades = [t for t in trades if t['pnlAbs'] > 0]
    loss_trades = [t for t in trades if t['pnlAbs'] <= 0]
    win_rate = len(win_trades) / max(len(trades), 1) * 100

    avg_gain = float(np.mean([t['pnlPct'] for t in win_trades])) if win_trades else 0.0
    avg_loss = float(np.mean([t['pnlPct'] for t in loss_trades])) if loss_trades else 0.0
    profit_loss_ratio = abs(avg_gain / avg_loss) if avg_loss != 0 else 0.0

    # ── K 线 + 买卖点时间戳 ───────────────────────────────────────────────────
    dates = [_date_to_ts(row.get('date')) for _, row in sig_df.iterrows()]
    opens = [_safe(row.get('open')) for _, row in sig_df.iterrows()]
    highs = [_safe(row.get('high')) for _, row in sig_df.iterrows()]
    lows = [_safe(row.get('low')) for _, row in sig_df.iterrows()]
    closes = [_safe(row.get('close')) for _, row in sig_df.iterrows()]
    volumes = [_safe(row.get('volume')) for _, row in sig_df.iterrows()]

    buy_markers = []
    sell_markers = []
    for dt_str, m in markers.items():
        ts = _date_to_ts(dt_str)
        if 'buy' in m:
            buy_markers.append({'time': m['buy'], 'id': 'buy', 'type': 1, 'tooltip': f'买入 {dt_str}'})
        if 'sell' in m:
            sell_markers.append({'time': m['sell'], 'id': 'sell', 'type': 2, 'tooltip': f'卖出 {dt_str}'})

    equity_line = [round(e, 2) for e in equity]
    drawdown_line = [round(d * 100, 4) for d in drawdown]

    return {
        'success': True,
        'template': template_id,
        'params': {k: _safe(v) if isinstance(v, float) else v for k, v in params.items()},
        'initialCash': round(float(initial_cash), 2),
        'finalCash': round(cash, 2),
        'totalReturnPct': round(total_return, 2),
        'annualReturnPct': round(annual_return, 2),
        'sharpeRatio': round(sharpe, 3),
        'maxDrawdownPct': round(max_dd_pct, 2),
        'tradeCount': len(trades),
        'winRatePct': round(win_rate, 2),
        'avgGainPct': round(float(avg_gain), 2) if avg_gain else 0.0,
        'avgLossPct': round(float(avg_loss), 2) if avg_loss else 0.0,
        'profitLossRatio': round(profit_loss_ratio, 3) if profit_loss_ratio else 0.0,
        'stats': {
            'totalReturnPct': round(total_return, 2),
            'annualReturnPct': round(annual_return, 2),
            'sharpeRatio': round(sharpe, 3),
            'maxDrawdownPct': round(max_dd_pct, 2),
            'winRatePct': round(win_rate, 2),
            'tradeCount': len(trades),
            'winTrades': len(win_trades),
            'lossTrades': len(loss_trades),
            'avgHoldDays': round(
                float(np.mean([t['holdDays'] for t in trades])) if trades else 0, 1
            ),
        },
        'candles': {
            'times': dates,
            'opens': opens,
            'highs': highs,
            'lows': lows,
            'closes': closes,
            'volumes': volumes,
        },
        'equity': equity_line,
        'drawdownPct': drawdown_line,
        'trades': trades,
        'markers': {'buy': buy_markers, 'sell': sell_markers},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 接口层：从前端请求 → 拉数据 → 回测 → 返回结果
# ═══════════════════════════════════════════════════════════════════════════════

def execute_backtest(
    stock_code: str,
    template_id: str,
    params: Dict[str, Any],
    start_date: str | None = None,
    end_date: str | None = None,
    days: int = 120,
    initial_cash: float = 100000.0,
    commission_pct: float = 0.001,
) -> Dict[str, Any]:
    """
    完整的回测执行管道：
    1. 拉取 K 线（新浪，不存库）
    2. 日期截断
    3. 调用 run_backtest()
    4. 返回可序列化结果
    """
    from utils.ths_crawler import get_stock_kline_sina, get_today_realtime_bar

    df = get_stock_kline_sina(str(stock_code).strip(), days=days)
    if df is None or df.empty:
        return {'error': f'无法获取 {stock_code} 的 K 线数据', 'success': False}

    required = ['date', 'open', 'high', 'low', 'close', 'volume']
    missing = [c for c in required if c not in df.columns]
    if missing:
        return {'error': f'K 线数据缺少列: {missing}', 'success': False}

    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')

    if start_date:
        start_dt = pd.to_datetime(start_date)
        df = df[df['date'] >= start_dt]
    if end_date:
        end_dt = pd.to_datetime(end_date)
        df = df[df['date'] <= end_dt]

    # ── 补充当日实时 K 线（仅当回测区间包含今天且是交易日）────────────
    try:
        today = pd.Timestamp('today').normalize()
        has_today = (df['date'].dt.normalize() == today).any()
        if has_today:
            bar = get_today_realtime_bar(str(stock_code).strip())
            if bar:
                bar_date = pd.to_datetime(bar['date'], errors='coerce')
                bar['date'] = bar_date
                # 若今日 K 线不存在（日期不匹配），直接替换最后一条
                today_rows = df[df['date'].dt.normalize() == today]
                bar_row = pd.DataFrame([bar])
                if today_rows.empty:
                    df = pd.concat([df, bar_row], ignore_index=True)
                else:
                    # 已有今日数据 → 用实时数据覆盖（保留索引）
                    idx = today_rows.index[0]
                    for col in bar:
                        if col in df.columns:
                            df.loc[idx, col] = bar[col]
    except Exception as e:
        print(f'[execute_backtest] 补充实时数据失败: {e}')

    if template_id == 'custom_bt':
        from utils.bt_code_sandbox import UnsafeCodeError, load_custom_strategy_class
        from utils.bt_cerebro_runner import run_cerebro_backtest

        raw_code = (params.get('user_code') or '').strip()
        try:
            strat_cls = load_custom_strategy_class(raw_code)
        except UnsafeCodeError as e:
            return {'success': False, 'error': str(e)}
        strat_kw = {k: v for k, v in params.items() if k != 'user_code'}
        result = run_cerebro_backtest(
            df,
            strat_cls,
            strat_kw,
            initial_cash=initial_cash,
            commission_pct=commission_pct,
        )
    else:
        result = run_backtest(df, template_id, params, initial_cash, commission_pct)

    if result.get('success'):
        result['stockCode'] = str(stock_code)
        result['period'] = {
            'start': str(df['date'].min())[:10] if len(df) else start_date or '',
            'end': str(df['date'].max())[:10] if len(df) else end_date or '',
            'bars': len(df),
        }
    return result

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用 backtrader Cerebro 运行用户自定义 Strategy，输出与 run_backtest 一致的结果结构。
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Tuple, Type

import numpy as np
import pandas as pd

try:
    import backtrader as bt
except ImportError:
    bt = None  # type: ignore

if bt is not None:

    class _EquityRecorder(bt.Analyzer):
        def __init__(self):
            self.equity: List[float] = []

        def next(self):
            self.equity.append(float(self.strategy.broker.getvalue()))

else:

    class _EquityRecorder:  # type: ignore
        pass


def _date_to_ts(d: Any) -> int:
    if isinstance(d, str):
        dt = datetime.datetime.strptime(d[:10], "%Y-%m-%d").replace(
            tzinfo=datetime.timezone(datetime.timedelta(hours=8))
        )
        return int(dt.timestamp())
    if hasattr(d, "timestamp"):
        return int(d.timestamp())
    if isinstance(d, (int, float)):
        return int(d)
    return 0


def _prepare_ohlc_df(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    if "date" in d.columns:
        d["date"] = pd.to_datetime(d["date"], errors="coerce")
        d = d.dropna(subset=["date"]).sort_values("date")
        d = d.set_index("date")
    for col in ("open", "high", "low", "close", "volume"):
        if col not in d.columns:
            d[col] = 0.0
        d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0.0)
    return d


def _make_traced_strategy(base_cls: Type[Any], orders_log: List[dict]) -> Type[Any]:
    class TracedStrategy(base_cls):  # type: ignore[misc,valid-type]
        def notify_order(self, order):
            if order.status == order.Completed:
                dt = self.data.datetime.date(0)
                otype = "buy" if order.isbuy() else "sell"
                orders_log.append(
                    {
                        "date": str(dt),
                        "type": otype,
                        "price": float(order.executed.price),
                        "size": float(order.executed.size),
                    }
                )
            super().notify_order(order)

    return TracedStrategy


def run_cerebro_backtest(
    df: pd.DataFrame,
    strategy_cls: Type[bt.Strategy],
    strategy_params: Dict[str, Any],
    initial_cash: float = 100000.0,
    commission_pct: float = 0.001,
) -> Dict[str, Any]:
    if bt is None:
        return {"success": False, "error": "未安装 backtrader，请 pip install backtrader"}

    if df is None or len(df) < 30:
        return {"success": False, "error": "数据不足，需至少 30 条 K 线"}

    d = _prepare_ohlc_df(df)
    if len(d) < 30:
        return {"success": False, "error": "数据不足"}

    orders_log: List[dict] = []
    Traced = _make_traced_strategy(strategy_cls, orders_log)

    pdata = bt.feeds.PandasData(
        dataname=d,
        datetime=None,
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        openinterest=-1,
    )

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(float(initial_cash))
    cerebro.broker.setcommission(commission=float(commission_pct))
    cerebro.adddata(pdata)
    cerebro.addstrategy(Traced, **strategy_params)
    cerebro.addanalyzer(_EquityRecorder, _name="eq")

    try:
        results = cerebro.run()
    except Exception as e:
        return {"success": False, "error": f"backtrader 运行失败: {e}"}

    strat = results[0]
    eq_an = strat.analyzers.eq
    equity_vals = list(eq_an.equity) if eq_an and eq_an.equity else []

    final_cash = float(cerebro.broker.getvalue())
    initial = float(initial_cash)
    total_return = (final_cash - initial) / initial * 100 if initial > 0 else 0.0
    n_bar = len(equity_vals) if equity_vals else len(d)
    annual_return = total_return / max(n_bar / 252, 0.01)

    if len(equity_vals) > 1:
        arr = np.asarray(equity_vals, dtype=float)
        rets = np.diff(arr) / arr[:-1]
        rets = rets[np.isfinite(rets)]
        if len(rets) > 1 and np.std(rets, ddof=1) > 1e-10:
            sharpe = float(np.mean(rets) / np.std(rets, ddof=1) * np.sqrt(252))
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    peak = initial
    max_dd = 0.0
    drawdown_line: List[float] = []
    for v in equity_vals:
        peak = max(peak, v)
        dd = (peak - v) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
        drawdown_line.append(round(dd * 100, 4))

    d_reset = d.reset_index()
    date_col = d_reset.columns[0]
    dates = [_date_to_ts(x) for x in d_reset[date_col]]
    opens = [round(float(x), 4) for x in d_reset["open"]]
    highs = [round(float(x), 4) for x in d_reset["high"]]
    lows = [round(float(x), 4) for x in d_reset["low"]]
    closes = [round(float(x), 4) for x in d_reset["close"]]
    volumes = [round(float(x), 4) for x in d_reset["volume"]]

    buy_markers: List[Dict[str, Any]] = []
    sell_markers: List[Dict[str, Any]] = []
    for o in orders_log:
        ts = _date_to_ts(o["date"])
        if o["type"] == "buy":
            buy_markers.append(
                {"time": ts, "id": "buy", "type": 1, "tooltip": f'买入 {o["date"]}'}
            )
        else:
            sell_markers.append(
                {"time": ts, "id": "sell", "type": 2, "tooltip": f'卖出 {o["date"]}'}
            )

    trades: List[Dict[str, Any]] = []
    buys: List[Tuple[str, float]] = []
    for o in sorted(orders_log, key=lambda x: x["date"]):
        if o["type"] == "buy":
            buys.append((o["date"], o["price"]))
        elif o["type"] == "sell" and buys:
            bd, bp = buys.pop(0)
            sp = o["price"]
            trades.append(
                {
                    "buyDate": bd,
                    "sellDate": o["date"],
                    "buyPrice": round(bp, 4),
                    "sellPrice": round(sp, 4),
                    "pnlPct": round((sp - bp) / bp * 100, 2) if bp else 0.0,
                    "pnlAbs": 0.0,
                    "holdDays": 1,
                }
            )

    win_trades = [t for t in trades if t["pnlPct"] > 0]
    win_rate = len(win_trades) / max(len(trades), 1) * 100

    # 权益曲线与 K 线根数对齐：前段无成交时可能较短，向前填充初始资金
    n = len(dates)
    if len(equity_vals) < n and equity_vals:
        pad_n = n - len(equity_vals)
        eq_aligned = [initial] * pad_n + equity_vals
    elif len(equity_vals) >= n:
        eq_aligned = equity_vals[-n:]
    else:
        eq_aligned = [initial] * n

    dd_aligned = drawdown_line
    if len(dd_aligned) < n and dd_aligned:
        pad_n = n - len(dd_aligned)
        dd_aligned = [0.0] * pad_n + dd_aligned
    elif len(dd_aligned) > n:
        dd_aligned = dd_aligned[-n:]
    elif not dd_aligned:
        dd_aligned = [0.0] * n

    return {
        "success": True,
        "template": "custom_bt",
        "engine": "backtrader",
        "params": strategy_params,
        "initialCash": round(initial, 2),
        "finalCash": round(final_cash, 2),
        "totalReturnPct": round(total_return, 2),
        "annualReturnPct": round(annual_return, 2),
        "sharpeRatio": round(sharpe, 3),
        "maxDrawdownPct": round(max_dd * 100, 2),
        "tradeCount": len(trades),
        "winRatePct": round(win_rate, 2),
        "avgGainPct": 0.0,
        "avgLossPct": 0.0,
        "profitLossRatio": 0.0,
        "stats": {
            "totalReturnPct": round(total_return, 2),
            "annualReturnPct": round(annual_return, 2),
            "sharpeRatio": round(sharpe, 3),
            "maxDrawdownPct": round(max_dd * 100, 2),
            "winRatePct": round(win_rate, 2),
            "tradeCount": len(trades),
            "winTrades": len(win_trades),
            "lossTrades": len(trades) - len(win_trades),
            "avgHoldDays": 0.0,
        },
        "candles": {
            "times": dates,
            "opens": opens,
            "highs": highs,
            "lows": lows,
            "closes": closes,
            "volumes": volumes,
        },
        "equity": [round(x, 2) for x in eq_aligned[:n]],
        "drawdownPct": dd_aligned[:n],
        "trades": trades,
        "markers": {"buy": buy_markers, "sell": sell_markers},
    }

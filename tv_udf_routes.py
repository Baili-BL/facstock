#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TradingView Charting Library UDF 兼容接口（日线 + A 股），供 mobile_white.html 使用。
严格遵循 TradingView UDF 协议：
https://www.tradingview.com/charting-library-docs/latest/data/UDF

关键要求：
- /time        → 纯文本字符串（Unix 秒，不带任何包裹）
- /history     → { s:'ok', t:[], o:[], h:[], l:[], c:[], v:[] }，t[0] = 最早时间戳（UTC 秒）
- NaN/Infinity → 替换为 null，否则 JSON 序列化失败
"""

from __future__ import annotations

import datetime
import logging
import math
import time as _time
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request, Response

import database as db

logger = logging.getLogger(__name__)
tv_udf_bp = Blueprint('tv_udf', __name__)

_SH_TZ = ZoneInfo('Asia/Shanghai')


def _parse_tv_symbol(symbol: str) -> str | None:
    """从 TradingView symbol 字符串提取 6 位股票代码。"""
    if not symbol:
        return None
    s = symbol.strip().upper()
    if ':' in s:
        s = s.split(':', 1)[-1].strip()
    if s.isdigit() and len(s) == 6:
        return s
    return None


def _exchange_for_code(code: str) -> str:
    if code.startswith('6'):
        return 'SSE'
    if code.startswith(('0', '3')):
        return 'SZSE'
    return 'SSE'


def _date_str_to_ts_sec(date_str: str) -> int:
    """
    'YYYY-MM-DD' → Unix 时间戳（UTC 秒）。
    时间点取交易日 00:00 Asia/Shanghai。
    TradingView 按此 UTC 时间戳显示在对应时区的日线柱上。
    """
    d = (date_str or '')[:10]
    dt = datetime.datetime.strptime(d, '%Y-%m-%d').replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=_SH_TZ
    )
    return int(dt.timestamp())


def _ensure_kline_payload(code: str) -> dict | None:
    """
    获取K线数据（TradingView 图表专用，仅 OHLCV，无策略计算）。

    优先级：
    1. kline_raw_cache  — Raw OHLCV，当日有效（最快路径）
    2. kline_cache      — 策略注解数据（含 candles 结构），命中时回写 Raw
    3. 网络抓取         — 新浪原始数据，存入两个缓存

    返回 {'bars': [...]} 或 {'candles': [...]}，tv_history 兼容两种格式。
    """
    # 优先读 Raw 缓存（最快路径，无任何策略计算）
    raw = db.get_kline_raw_cache(code)
    if raw and raw.get('bars'):
        logger.info('[TV] %s raw cache HIT (%d bars)', code, len(raw.get('bars', [])))
        return raw
    logger.info('[TV] %s raw cache MISS', code)

    # 次选策略缓存（已有 candles 结构），命中时回写 Raw 缓存供 TV 直读
    cached = db.get_kline_cache(code)
    if cached and cached.get('candles'):
        logger.info('[TV] %s strategy cache HIT (%d candles)', code, len(cached.get('candles', [])))
        # 回写 kline_raw_cache，避免下次再走到这里
        raw_bars = []
        for c in cached.get('candles', []):
            bar = {
                'date': c.get('time', ''),
                'open': c.get('open'),
                'high': c.get('high'),
                'low': c.get('low'),
                'close': c.get('close'),
            }
            # 从 strategy cache 的 volumes 列表里按 index 匹配 volume
            vol_list = cached.get('volumes', [])
            idx = cached.get('candles', []).index(c)
            if idx < len(vol_list):
                bar['volume'] = vol_list[idx].get('value', 0)
            else:
                bar['volume'] = 0
            raw_bars.append(bar)
        if raw_bars:
            import pandas as _pd
            db.save_kline_raw_cache(code, _pd.DataFrame(raw_bars))
        return cached
    logger.info('[TV] %s strategy cache MISS', code)

    # 两层缓存均未命中，网络抓取
    from utils.ths_crawler import get_stock_kline_sina

    try:
        df = get_stock_kline_sina(code, days=120)
        if df is None or df.empty:
            return None

        # 保存 Raw OHLCV（供 TV 图表用）
        db.save_kline_raw_cache(code, df)

        # 构建 candles/volumes 结构并缓存
        candles, volumes = [], []
        for _, row in df.iterrows():
            d = str(row.get('date', ''))[:10]
            if not d:
                continue
            try:
                close = float(row.get('close', 0))
            except (TypeError, ValueError):
                close = 0.0
            try:
                open_ = float(row.get('open', close))
                high = float(row.get('high', close))
                low = float(row.get('low', close))
                vol = float(row.get('volume', 0))
            except (TypeError, ValueError):
                open_, high, low = close, close, close
                vol = 0.0
            candles.append({'time': d, 'open': open_, 'high': high, 'low': low, 'close': close})
            color = '#ef5350' if close >= open_ else '#26a69a'
            volumes.append({'time': d, 'value': vol, 'color': color})

        payload = {'candles': candles, 'volumes': volumes}
        db.save_kline_cache(code, payload)
        return payload

    except Exception as e:
        logger.warning('tv_udf ensure kline failed %s: %s', code, e)
        return None


def _safe(val) -> float | None:
    """JSON 序列化安全值：NaN/Inf → None，其他转 float。"""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


# ──────────────────────────── TradingView UDF 接口 ────────────────────────────

@tv_udf_bp.route('/config')
def tv_config():
    """
    告知前端 this.datafeed 支持哪些特性。
    https://www.tradingview.com/charting-library-docs/latest/data/UDF/UDF-Module#datafeedconfiguration

    注意：官方 UDFCompatibleDatafeed（bundle.js）在 _setupWithConfiguration 里要求
    supports_search 与 supports_group_request 至少一个为 true，否则直接 throw，
    图表只会发出 /config 后卡住（Network 里看不到 /symbols、/history）。
    本项目用「单标的 /symbols」解析，因此设 supports_search=true、
    supports_group_request=false，resolveSymbol 才会走 _send('symbols') 分支。
    """
    return jsonify({
        'supports_search': True,
        'supports_group_request': False,
        'supports_marks': False,
        'supports_timescale_marks': False,
        'supports_time': True,
        'supported_resolutions': ['1D'],
    })


@tv_udf_bp.route('/time')
def tv_time():
    """
    TradingView 用此接口同步服务器时间。
    必须返回纯文本 Unix 秒字符串，不带任何 JSON 包裹，不带 Content-Type: application/json。
    """
    return Response(str(int(_time.time())), mimetype='text/plain')


@tv_udf_bp.route('/quotes')
def tv_quotes():
    return jsonify({'s': 'ok', 'd': []})


@tv_udf_bp.route('/search')
def tv_search():
    """UDF search：移动端图表未开放搜索，返回空数组即可。"""
    return jsonify([])


@tv_udf_bp.route('/symbols')
def tv_symbols():
    symbol = request.args.get('symbol') or ''
    code = _parse_tv_symbol(symbol)
    if not code:
        return jsonify({'s': 'error', 'errmsg': 'unknown_symbol'})

    exch = _exchange_for_code(code)
    full = f'{exch}:{code}'

    return jsonify({
        'name': code,
        'ticker': full,
        'description': code,
        'type': 'stock',
        'session': '0930-1130,1300-1500',
        'session-regular': '0930-1130,1300-1500',
        'timezone': 'Asia/Shanghai',
        'exchange': exch,
        'listed_exchange': exch,
        'exchange-listed': exch,
        'exchange-traded': exch,
        'minmov': 1,
        'minmovement': 1,
        'pricescale': 100,
        'has_intraday': False,
        'has-intraday': False,
        'has_daily': True,
        'has-daily': True,
        'has_weekly_and_monthly': False,
        'has-weekly-and-monthly': False,
        'has_no_volume': False,
        'has-no-volume': False,
        'visible_plots_set': 'ohlcv',
        'visible-plots-set': 'ohlcv',
        'supported_resolutions': ['1D'],
        'supported-resolutions': ['1D'],
        'volume_precision': 0,
        'volume-precision': 0,
        'currency_code': 'CNY',
        'currency-code': 'CNY',
        'data_status': 'streaming',
    })


@tv_udf_bp.route('/history')
def tv_history():
    """
    TradingView UDF 历史 K 线接口。

    Query params:
        symbol     — e.g. "SZSE:301008"
        resolution  — "1D" / "D"（本项目仅支持日线）
        from       — Unix UTC 秒（窗口起始）
        to         — Unix UTC 秒（窗口结束）
        countback  — 最多返回条数（分页用）

    Returns:
        { s: 'ok', t:[], o:[], h:[], l:[], c:[], v:[], nb: <next_bar_time> }
        t[0] = 最早柱的时间戳（UTC 秒），数据升序排列。
    """
    symbol = request.args.get('symbol') or ''
    resolution = (request.args.get('resolution') or '1D').upper()
    try:
        from_sec = int(float(request.args.get('from', 0)))
        to_sec = int(float(request.args.get('to', 0)))
        countback = int(request.args.get('countback', 0))
    except (TypeError, ValueError):
        from_sec, to_sec, countback = 0, 0, 0

    code = _parse_tv_symbol(symbol)
    if not code:
        return jsonify({'s': 'error', 'errmsg': 'unknown_symbol'})

    if resolution not in ('1D', 'D'):
        return jsonify({'s': 'no_data'})

    # ── 防御：bundle.js 分页溢出时 countback 会变成巨大负数，直接返回 no_data ──
    # 这阻止了无效分页请求打爆服务器
    if countback < 0:
        return jsonify({'s': 'no_data'})

    # ── 防御：from/to 异常（如 1970 年代历史时间戳）直接返回 no_data ──
    # 缓存数据是 2025-12 之后，不可能有更早的数据
    now_sec = int(_time.time())
    if to_sec > 0 and to_sec < (now_sec - 180 * 86400):  # 早于 ~6 个月
        return jsonify({'s': 'no_data'})

    # ── 直接从数据库读取 bar 时间戳，不走字符串转换 ─────────────────────────
    # kline_raw_cache 里 bar['date'] 可能是 'YYYY-MM-DD' 字符串或 pd.Timestamp
    raw = db.get_kline_raw_cache(code)
    if not raw or not raw.get('bars'):
        return jsonify({'s': 'no_data'})

    bars = sorted(raw['bars'], key=lambda b: str(b.get('date') or b.get('time') or ''))
    if not bars:
        return jsonify({'s': 'no_data'})

    # 把 bar.date 转成 Unix 时间戳（秒），兼容字符串和 Timestamp
    def _bar_ts(bar):
        d = bar.get('date') or bar.get('time')
        if isinstance(d, (int, float)):
            return int(d)
        if hasattr(d, 'timestamp'):
            return int(d.timestamp())
        if isinstance(d, str):
            return _date_str_to_ts_sec(d)
        return 0

    first_ts = _bar_ts(bars[0])
    last_ts  = _bar_ts(bars[-1])

    # ── 非重叠检测 ─────────────────────────────────────────────────────────
    # 请求窗口完全在缓存数据左侧（更早）→ no_data
    if to_sec > 0 and to_sec < first_ts:
        return jsonify({'s': 'no_data', 'nextTime': first_ts})
    # 请求窗口完全在缓存数据右侧（更新）
    if from_sec > last_ts:
        return jsonify({'s': 'no_data', 'nextTime': None})

    t_list, o_list, h_list, l_list, c_list, v_list = [], [], [], [], [], []

    for bar in bars:
        if not isinstance(bar, dict):
            continue
        ts = _bar_ts(bar)
        if not ts:
            continue
        # 窗口过滤：只返回落在 [from_sec, to_sec] 内的 bar
        if from_sec and ts < from_sec:
            continue
        if to_sec and ts > to_sec:
            continue

        c = _safe(bar.get('close'))
        if c is None:
            continue

        t_list.append(ts)
        o_list.append(_safe(bar.get('open')) if bar.get('open') is not None else c)
        h_list.append(_safe(bar.get('high')) if bar.get('high') is not None else c)
        l_list.append(_safe(bar.get('low'))  if bar.get('low')  is not None else c)
        c_list.append(c)
        v_list.append(_safe(bar.get('volume')) if bar.get('volume') is not None else 0.0)

    if not t_list:
        return jsonify({'s': 'no_data'})

    return jsonify({
        's': 'ok',
        't': t_list,
        'o': o_list,
        'h': h_list,
        'l': l_list,
        'c': c_list,
        'v': v_list,
    })

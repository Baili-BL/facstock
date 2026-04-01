#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A 股（以上证指数交易日历为准）当前时段状态：北京时间、工作日与连续竞价时段。
不含法定节假日（节假日仍可能显示为「已收盘」）；后续可接交易日历扩展。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo

TZ_SH = ZoneInfo('Asia/Shanghai')

# 连续竞价：09:30–11:30、13:00–15:00
_OPEN_AM = 9 * 60 + 30
_CLOSE_AM = 11 * 60 + 30
_OPEN_PM = 13 * 60
_CLOSE_PM = 15 * 60


def get_a_share_session_payload(now: datetime | None = None) -> Dict[str, Any]:
    """
    Returns:
        label: 展示文案
        dot: 前端状态点 class：is-up | is-off
        code: trading | lunch_break | closed | non_trading_day
        is_trading: 是否在连续竞价时段
        timezone: 固定 Asia/Shanghai
        as_of: 判定所用北京时间 ISO 字符串
    """
    if now is None:
        now = datetime.now(TZ_SH)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=TZ_SH)
    else:
        now = now.astimezone(TZ_SH)

    wday = now.weekday()  # 周一=0 … 周日=6
    is_weekend = wday >= 5
    minute_of_day = now.hour * 60 + now.minute

    if is_weekend:
        label, code, dot = '非交易日', 'non_trading_day', 'is-off'
    elif _OPEN_AM <= minute_of_day < _CLOSE_AM:
        label, code, dot = '交易中', 'trading', 'is-up'
    elif _OPEN_PM <= minute_of_day < _CLOSE_PM:
        label, code, dot = '交易中', 'trading', 'is-up'
    elif _CLOSE_AM <= minute_of_day < _OPEN_PM:
        label, code, dot = '午间休市', 'lunch_break', 'is-off'
    else:
        label, code, dot = '已收盘', 'closed', 'is-off'

    return {
        'label': label,
        'dot': dot,
        'code': code,
        'is_trading': code == 'trading',
        'timezone': 'Asia/Shanghai',
        'as_of': now.isoformat(timespec='seconds'),
    }

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
游资智能体飞书推送服务

职责：
1. 汇总多位游资 Agent 的分析结果
2. 形成共识股票与市场摘要
3. 按固定时点定时推送到飞书
4. 提供状态查询与手动触发能力
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence
from zoneinfo import ZoneInfo

import cache as cache_layer
from market_data import get_limit_up_data, get_market_overview
from utils.feishu_notifier import FeishuNotifier
from utils.llm import get_agent_registry

logger = logging.getLogger(__name__)

DEFAULT_TRADER_AGENT_IDS = ['beijing', 'qiao', 'jia', 'jun']
DEFAULT_SLOT_DEFINITIONS = [
    {'key': '0900', 'time': '09:00', 'label': '盘前策略会', 'template': 'blue'},
    {'key': '1230', 'time': '12:30', 'label': '午间复盘', 'template': 'orange'},
    {'key': '1430', 'time': '14:30', 'label': '午后决策', 'template': 'red'},
    {'key': '2100', 'time': '21:00', 'label': '晚间复盘', 'template': 'indigo'},
]


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def _safe_int(val: Any, default: int = 0) -> int:
    try:
        return int(float(val))
    except Exception:
        return default


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except Exception:
        return default


def _short_text(text: Any, limit: int = 56) -> str:
    value = str(text or '').strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + '…'


def _is_trading_weekday(now: datetime) -> bool:
    return now.weekday() < 5


def mask_webhook_url(url: str) -> str:
    value = str(url or '').strip()
    if not value:
        return ''
    if len(value) <= 16:
        return value
    return f'{value[:12]}…{value[-8:]}'


def parse_agent_ids(agent_ids: Optional[Iterable[str] | str]) -> List[str]:
    if not agent_ids:
        return []
    if isinstance(agent_ids, str):
        parts = [p.strip() for p in agent_ids.split(',')]
    else:
        parts = [str(p).strip() for p in agent_ids]
    deduped: List[str] = []
    for part in parts:
        if part and part not in deduped:
            deduped.append(part)
    return deduped


def get_a_share_session_payload(now: Optional[datetime] = None, tz_name: str = 'Asia/Shanghai') -> Dict[str, Any]:
    tz = ZoneInfo(tz_name)
    current = now.astimezone(tz) if now else datetime.now(tz)
    minutes = current.hour * 60 + current.minute

    if not _is_trading_weekday(current):
        return {
            'phase': '休市观察',
            'label': '休市',
            'isTradingDay': False,
            'window': '休市',
        }

    if minutes < 9 * 60:
        return {
            'phase': '盘前预备',
            'label': '盘前',
            'isTradingDay': True,
            'window': '09:00 前',
        }
    if minutes < 9 * 60 + 25:
        return {
            'phase': '盘前预备',
            'label': '盘前',
            'isTradingDay': True,
            'window': '09:00-09:25',
        }
    if minutes < 9 * 60 + 30:
        return {
            'phase': '集合竞价',
            'label': '竞价',
            'isTradingDay': True,
            'window': '09:25-09:30',
        }
    if minutes < 11 * 60 + 30:
        return {
            'phase': '早盘交易',
            'label': '早盘',
            'isTradingDay': True,
            'window': '09:30-11:30',
        }
    if minutes < 13 * 60:
        return {
            'phase': '午间观察',
            'label': '午间',
            'isTradingDay': True,
            'window': '11:30-13:00',
        }
    if minutes < 15 * 60:
        return {
            'phase': '午后交易',
            'label': '午后',
            'isTradingDay': True,
            'window': '13:00-15:00',
        }
    return {
        'phase': '收盘复核',
        'label': '收盘后',
        'isTradingDay': True,
        'window': '15:00 后',
    }


def _parse_slot_hour_minute(slot_time: str) -> tuple[int, int]:
    hour_str, minute_str = str(slot_time).split(':', 1)
    return int(hour_str), int(minute_str)


class TraderAgentPushService:
    """游资智能体推送聚合服务。"""

    def __init__(
        self,
        analyze_agent_fn: Callable[[str], Dict[str, Any]],
        webhook_url: Optional[str] = None,
        default_agent_ids: Optional[Sequence[str]] = None,
        top_stocks_per_agent: Optional[int] = None,
        consensus_top_n: Optional[int] = None,
        timezone_name: str = 'Asia/Shanghai',
    ):
        self.analyze_agent_fn = analyze_agent_fn
        self.timezone_name = timezone_name
        self.tz = ZoneInfo(timezone_name)
        self.registry = get_agent_registry()
        self.webhook_url = (webhook_url or os.environ.get('AGENT_PUSH_WEBHOOK_URL') or '').strip()
        self.default_agent_ids = (
            parse_agent_ids(os.environ.get('AGENT_PUSH_AGENT_IDS'))
            or list(default_agent_ids or DEFAULT_TRADER_AGENT_IDS)
        )
        self.top_stocks_per_agent = _safe_int(
            os.environ.get('AGENT_PUSH_TOP_STOCKS_PER_AGENT'),
            top_stocks_per_agent or 2,
        )
        self.consensus_top_n = _safe_int(
            os.environ.get('AGENT_PUSH_CONSENSUS_TOP_N'),
            consensus_top_n or 5,
        )
        self.analysis_max_workers = max(
            1,
            _safe_int(os.environ.get('AGENT_PUSH_MAX_WORKERS'), min(4, len(self.default_agent_ids) or 1)),
        )
        self.enabled = _env_flag('AGENT_PUSH_ENABLED', default=_env_flag('FEISHU_ENABLED', default=True))
        self._history: deque[Dict[str, Any]] = deque(maxlen=30)
        self._last_result: Optional[Dict[str, Any]] = None
        self._state_lock = threading.Lock()

    def status(self) -> Dict[str, Any]:
        effective_webhook = self.webhook_url or FeishuNotifier().webhook_url
        with self._state_lock:
            return {
                'enabled': self.enabled,
                'configured': bool(effective_webhook),
                'webhookMasked': mask_webhook_url(effective_webhook),
                'defaultAgentIds': list(self.default_agent_ids),
                'topStocksPerAgent': self.top_stocks_per_agent,
                'consensusTopN': self.consensus_top_n,
                'analysisMaxWorkers': self.analysis_max_workers,
                'lastResult': self._last_result,
                'history': list(self._history),
            }

    def _resolve_agent_ids(self, agent_ids: Optional[Sequence[str] | str]) -> List[str]:
        chosen = parse_agent_ids(agent_ids) or list(self.default_agent_ids)
        valid_ids = {item.get('id') for item in self.registry.list_agents()}
        return [aid for aid in chosen if aid in valid_ids]

    def _normalize_stock(self, item: Dict[str, Any], report: Dict[str, Any]) -> Dict[str, Any]:
        agent_id = report.get('agentId') or report.get('agent_id') or ''
        agent_name = report.get('agentName') or report.get('agent_name') or agent_id
        entry_model = (
            item.get('entryModel')
            or item.get('buyPointType')
            or item.get('entryPlan')
            or item.get('buyMethod')
            or item.get('adviseType')
            or '观察'
        )
        role = (
            item.get('role')
            or item.get('leaderType')
            or item.get('themeRole')
            or item.get('boardType')
            or item.get('selectionType')
            or '候选'
        )
        signal = (
            item.get('signal')
            or item.get('reason')
            or item.get('classificationReason')
            or item.get('sealVerdictSummary')
            or item.get('threeAxesPassed')
            or ''
        )
        position_ratio = item.get('positionRatio') or item.get('仓位建议') or ''
        hold_period = item.get('holdPeriod') or item.get('预计持股周期') or ''
        return {
            'code': str(item.get('code') or '').strip(),
            'name': str(item.get('name') or '').strip(),
            'price': _safe_float(item.get('price') or item.get('close')),
            'changePct': _safe_float(item.get('changePct') or item.get('chg_pct') or item.get('change_pct')),
            'role': str(role).strip(),
            'entryModel': str(entry_model).strip(),
            'entryTrigger': str(item.get('entryTrigger') or item.get('buyRange') or '').strip(),
            'positionRatio': str(position_ratio).strip(),
            'holdPeriod': str(hold_period).strip(),
            'signal': str(signal).strip(),
            'riskLevel': str(item.get('riskLevel') or '').strip(),
            'tradeStatus': str(item.get('tradeStatus') or '').strip(),
            'score': _safe_float(item.get('score')),
            'agentId': agent_id,
            'agentName': agent_name,
        }

    def _normalize_agent_report(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        structured = raw_result.get('structured') or {}
        agent_id = raw_result.get('agent_id') or structured.get('agentId') or ''
        agent_name = raw_result.get('agent_name') or structured.get('agentName') or agent_id
        stocks = structured.get('recommendedStocks') or []
        normalized_stocks = []
        for item in stocks[: max(1, self.top_stocks_per_agent)]:
            if isinstance(item, dict):
                normalized_stocks.append(self._normalize_stock(item, {
                    'agentId': agent_id,
                    'agentName': agent_name,
                }))
        return {
            'agentId': agent_id,
            'agentName': agent_name,
            'role': raw_result.get('role_subtitle') or '',
            'success': bool(raw_result.get('success')),
            'stance': structured.get('stance') or 'neutral',
            'confidence': _safe_int(structured.get('confidence'), 0),
            'marketCommentary': str(structured.get('marketCommentary') or '').strip(),
            'positionAdvice': str(structured.get('positionAdvice') or '').strip(),
            'riskWarning': str(structured.get('riskWarning') or '').strip(),
            'recommendedStocks': normalized_stocks,
            'rawStructured': structured,
            'error': raw_result.get('error') or '',
        }

    def collect_market_brief(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        current = now.astimezone(self.tz) if now else datetime.now(self.tz)
        overview = get_market_overview() or []
        limit_data = get_limit_up_data() or {}
        indices = []
        wanted = ('上证指数', '深证成指', '创业板指')
        for name in wanted:
            item = next((x for x in overview if str(x.get('name')) == name), None)
            if not item:
                continue
            indices.append({
                'name': name,
                'price': _safe_float(item.get('price')),
                'change': _safe_float(item.get('change')),
            })
        return {
            'generatedAt': current.strftime('%Y-%m-%d %H:%M:%S'),
            'session': get_a_share_session_payload(current, self.timezone_name),
            'indices': indices,
            'limitUpCount': _safe_int(limit_data.get('limit_up_count')),
            'limitDownCount': _safe_int(limit_data.get('limit_down_count')),
            'limitSource': str(limit_data.get('count_source') or '').strip(),
            'limitTime': str(limit_data.get('time') or '').strip(),
        }

    def _build_consensus(self, agent_reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        for report in agent_reports:
            confidence = _safe_int(report.get('confidence'), 0)
            for stock in report.get('recommendedStocks') or []:
                code = stock.get('code')
                if not code:
                    continue
                row = merged.setdefault(code, {
                    'code': code,
                    'name': stock.get('name') or '',
                    'price': stock.get('price') or 0.0,
                    'changePct': stock.get('changePct') or 0.0,
                    'supportAgents': [],
                    'roles': [],
                    'entryModels': [],
                    'positionRatios': [],
                    'signals': [],
                    'supportCount': 0,
                    'confidenceScore': 0,
                })
                if report.get('agentName') and report['agentName'] not in row['supportAgents']:
                    row['supportAgents'].append(report['agentName'])
                    row['supportCount'] += 1
                    row['confidenceScore'] += confidence
                for key, field in (
                    ('roles', stock.get('role')),
                    ('entryModels', stock.get('entryModel')),
                    ('positionRatios', stock.get('positionRatio')),
                    ('signals', stock.get('signal')),
                ):
                    value = str(field or '').strip()
                    if value and value not in row[key]:
                        row[key].append(value)
                if not row.get('name') and stock.get('name'):
                    row['name'] = stock['name']
                if not row.get('price') and stock.get('price'):
                    row['price'] = stock['price']
                if not row.get('changePct') and stock.get('changePct'):
                    row['changePct'] = stock['changePct']

        ranked = sorted(
            merged.values(),
            key=lambda item: (
                item.get('supportCount', 0),
                item.get('confidenceScore', 0),
                item.get('changePct', 0),
            ),
            reverse=True,
        )

        result = []
        for item in ranked[: max(1, self.consensus_top_n)]:
            result.append({
                'code': item['code'],
                'name': item.get('name', ''),
                'price': round(_safe_float(item.get('price')), 2),
                'changePct': round(_safe_float(item.get('changePct')), 2),
                'supportCount': item.get('supportCount', 0),
                'supportAgents': item.get('supportAgents', []),
                'roleSummary': ' / '.join(item.get('roles', [])[:2]),
                'entryModelSummary': ' / '.join(item.get('entryModels', [])[:2]),
                'positionSummary': ' / '.join(item.get('positionRatios', [])[:2]),
                'signalSummary': '；'.join(item.get('signals', [])[:2]),
            })
        return result

    def build_digest(
        self,
        agent_ids: Optional[Sequence[str] | str] = None,
        slot_key: Optional[str] = None,
        slot_label: Optional[str] = None,
        trigger_type: str = 'manual',
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        current = now.astimezone(self.tz) if now else datetime.now(self.tz)
        selected_agent_ids = self._resolve_agent_ids(agent_ids)
        agent_reports: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []
        if len(selected_agent_ids) <= 1:
            for agent_id in selected_agent_ids:
                try:
                    raw_result = self.analyze_agent_fn(agent_id)
                    normalized = self._normalize_agent_report(raw_result)
                    if normalized.get('success'):
                        agent_reports.append(normalized)
                    else:
                        errors.append({
                            'agentId': agent_id,
                            'agentName': normalized.get('agentName') or agent_id,
                            'error': normalized.get('error') or '分析失败',
                        })
                except Exception as exc:
                    logger.exception('Agent 推送分析失败: %s', agent_id)
                    errors.append({
                        'agentId': agent_id,
                        'agentName': agent_id,
                        'error': str(exc),
                    })
        else:
            ordered_reports: Dict[str, Dict[str, Any]] = {}
            with ThreadPoolExecutor(max_workers=min(self.analysis_max_workers, len(selected_agent_ids))) as pool:
                future_to_agent = {
                    pool.submit(self.analyze_agent_fn, agent_id): agent_id
                    for agent_id in selected_agent_ids
                }
                for future in as_completed(future_to_agent):
                    agent_id = future_to_agent[future]
                    try:
                        raw_result = future.result()
                        normalized = self._normalize_agent_report(raw_result)
                        if normalized.get('success'):
                            ordered_reports[agent_id] = normalized
                        else:
                            errors.append({
                                'agentId': agent_id,
                                'agentName': normalized.get('agentName') or agent_id,
                                'error': normalized.get('error') or '分析失败',
                            })
                    except Exception as exc:
                        logger.exception('Agent 推送分析失败: %s', agent_id)
                        errors.append({
                            'agentId': agent_id,
                            'agentName': agent_id,
                            'error': str(exc),
                        })
            agent_reports = [ordered_reports[agent_id] for agent_id in selected_agent_ids if agent_id in ordered_reports]

        digest = {
            'digestId': uuid.uuid4().hex[:12],
            'generatedAt': current.strftime('%Y-%m-%d %H:%M:%S'),
            'triggerType': trigger_type,
            'slotKey': slot_key or '',
            'slotLabel': slot_label or get_a_share_session_payload(current, self.timezone_name).get('phase', '策略推送'),
            'marketBrief': self.collect_market_brief(current),
            'agentIds': selected_agent_ids,
            'agentReports': agent_reports,
            'errors': errors,
            'consensusStocks': self._build_consensus(agent_reports),
        }
        digest['summary'] = {
            'agentCount': len(selected_agent_ids),
            'successCount': len(agent_reports),
            'failedCount': len(errors),
            'consensusCount': len(digest['consensusStocks']),
        }
        return digest

    def send_digest(self, digest: Dict[str, Any], webhook_url: Optional[str] = None) -> bool:
        url = (webhook_url or self.webhook_url or os.environ.get('FEISHU_WEBHOOK_URL') or '').strip()
        notifier = FeishuNotifier(webhook_url=url or None)
        return notifier.send_agent_digest(digest)

    def run_push(
        self,
        agent_ids: Optional[Sequence[str] | str] = None,
        slot_key: Optional[str] = None,
        slot_label: Optional[str] = None,
        trigger_type: str = 'manual',
        webhook_url: Optional[str] = None,
        dry_run: bool = False,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        digest = self.build_digest(
            agent_ids=agent_ids,
            slot_key=slot_key,
            slot_label=slot_label,
            trigger_type=trigger_type,
            now=now,
        )
        sent = False
        effective_webhook = webhook_url or self.webhook_url or FeishuNotifier().webhook_url
        if not dry_run:
            sent = self.send_digest(digest, webhook_url=webhook_url)
        result = {
            'success': True,
            'sent': sent,
            'dryRun': dry_run,
            'webhookMasked': mask_webhook_url(effective_webhook),
            'digest': digest,
        }
        with self._state_lock:
            summary = {
                'generatedAt': digest.get('generatedAt'),
                'slotLabel': digest.get('slotLabel'),
                'triggerType': digest.get('triggerType'),
                'sent': sent,
                'dryRun': dry_run,
                'agentCount': digest.get('summary', {}).get('agentCount', 0),
                'successCount': digest.get('summary', {}).get('successCount', 0),
                'failedCount': digest.get('summary', {}).get('failedCount', 0),
                'consensusCount': digest.get('summary', {}).get('consensusCount', 0),
                'topConsensus': [f"{item.get('name', '')}({item.get('code', '')})" for item in digest.get('consensusStocks', [])[:3]],
            }
            self._last_result = summary
            self._history.appendleft(summary)
        return result


class TraderAgentPushScheduler:
    """游资智能体定时推送调度器。"""

    def __init__(
        self,
        service: TraderAgentPushService,
        slot_definitions: Optional[List[Dict[str, str]]] = None,
        poll_interval_seconds: Optional[int] = None,
        grace_period_seconds: Optional[int] = None,
        timezone_name: str = 'Asia/Shanghai',
    ):
        self.service = service
        self.slot_definitions = list(slot_definitions or DEFAULT_SLOT_DEFINITIONS)
        self.poll_interval_seconds = _safe_int(os.environ.get('AGENT_PUSH_POLL_SECONDS'), poll_interval_seconds or 20)
        self.grace_period_seconds = _safe_int(os.environ.get('AGENT_PUSH_GRACE_SECONDS'), grace_period_seconds or 180)
        self.tz = ZoneInfo(timezone_name)
        self.enabled = service.enabled
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._local_claims: set[str] = set()
        self._state_lock = threading.Lock()

    def start(self) -> bool:
        if not self.enabled:
            logger.info('[AgentPush] 调度器未启用，跳过启动')
            return False
        with self._state_lock:
            if self._thread and self._thread.is_alive():
                return True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name='trader-agent-push-scheduler',
                daemon=True,
            )
            self._thread.start()
        logger.info('[AgentPush] 调度器已启动')
        return True

    def stop(self) -> None:
        self._stop_event.set()
        with self._state_lock:
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2)
            self._thread = None

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_pending()
            except Exception as exc:
                logger.exception('[AgentPush] 调度循环异常: %s', exc)
            self._stop_event.wait(self.poll_interval_seconds)

    def _claim_slot(self, slot_date: str, slot_key: str) -> bool:
        claim_key = f'agent_push/slot/{slot_date}/{slot_key}'
        try:
            cache_layer._init_redis()  # type: ignore[attr-defined]
            redis_available = getattr(cache_layer, '_redis_available', False)
            redis_client = getattr(cache_layer, '_redis', None)
            if redis_available and redis_client is not None:
                ok = redis_client.set(claim_key, datetime.now(self.tz).isoformat(), ex=36 * 3600, nx=True)
                return bool(ok)
        except Exception as exc:
            logger.debug('[AgentPush] Redis 槽位去重失败，降级内存: %s', exc)

        with self._state_lock:
            if claim_key in self._local_claims:
                return False
            self._local_claims.add(claim_key)
            return True

    def _compute_next_slot(self, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        current = now.astimezone(self.tz) if now else datetime.now(self.tz)
        for day_offset in range(0, 7):
            base_day = (current + timedelta(days=day_offset)).date()
            probe = datetime.combine(base_day, datetime.min.time(), tzinfo=self.tz)
            if not _is_trading_weekday(probe):
                continue
            for slot in self.slot_definitions:
                hour, minute = _parse_slot_hour_minute(slot['time'])
                candidate = probe.replace(hour=hour, minute=minute)
                if candidate > current:
                    return {
                        'slotKey': slot['key'],
                        'slotLabel': slot['label'],
                        'scheduledAt': candidate.strftime('%Y-%m-%d %H:%M:%S'),
                    }
        return None

    def status(self) -> Dict[str, Any]:
        with self._state_lock:
            running = bool(self._thread and self._thread.is_alive())
        return {
            'enabled': self.enabled,
            'running': running,
            'pollIntervalSeconds': self.poll_interval_seconds,
            'gracePeriodSeconds': self.grace_period_seconds,
            'slots': list(self.slot_definitions),
            'nextSlot': self._compute_next_slot(),
        }

    def run_pending(self, now: Optional[datetime] = None) -> None:
        current = now.astimezone(self.tz) if now else datetime.now(self.tz)
        if not _is_trading_weekday(current):
            return

        today = current.strftime('%Y-%m-%d')
        for slot in self.slot_definitions:
            hour, minute = _parse_slot_hour_minute(slot['time'])
            slot_dt = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
            delta = (current - slot_dt).total_seconds()
            if delta < 0 or delta > self.grace_period_seconds:
                continue
            if not self._claim_slot(today, slot['key']):
                continue
            logger.info('[AgentPush] 触发定时推送: %s %s', today, slot['label'])
            try:
                self.service.run_push(
                    slot_key=slot['key'],
                    slot_label=slot['label'],
                    trigger_type='scheduler',
                    dry_run=False,
                    now=current,
                )
            except Exception as exc:
                logger.exception('[AgentPush] 定时推送失败: %s', exc)

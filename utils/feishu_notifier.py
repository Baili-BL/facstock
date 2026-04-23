#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书 Webhook 通知模块
支持富文本消息卡片推送
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import requests

logger = logging.getLogger(__name__)

# 飞书 Webhook 地址（支持环境变量覆盖）
FEISHU_WEBHOOK_URL = (
    os.environ.get('AGENT_PUSH_WEBHOOK_URL')
    or os.environ.get('FEISHU_WEBHOOK_URL')
    or ''
).strip()

# 推送开关（生产环境建议设为 True）
FEISHU_ENABLED = os.environ.get('FEISHU_ENABLED', 'true').lower() in ('true', '1', 'yes')


def _short_text(value: Any, limit: int = 56) -> str:
    text = str(value or '').strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + '…'


class FeishuNotifier:
    """飞书 Webhook 通知器"""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or FEISHU_WEBHOOK_URL
        self.enabled = FEISHU_ENABLED

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith('http'))

    def _post(self, payload: dict) -> bool:
        """发送 POST 请求到飞书"""
        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            result = resp.json()
            code = result.get('code', 0)
            if code == 0:
                logger.info('[Feishu] 消息推送成功')
                return True
            else:
                logger.warning('[Feishu] 推送失败: code=%s msg=%s', code, result.get('msg', ''))
                return False
        except Exception as e:
            logger.error('[Feishu] 请求异常: %s', e)
            return False

    def send_text(self, text: str) -> bool:
        """发送纯文本消息"""
        if not self.enabled or not self.is_configured:
            logger.debug('[Feishu] 推送已禁用或未配置，跳过文本消息')
            return False
        payload = {'msg_type': 'text', 'content': {'text': text}}
        return self._post(payload)

    def send_scan_alert(
        self,
        scan_id: int,
        scan_time: str,
        sector_results: Dict[str, List[Dict]],
        hot_sectors: List[Dict],
        params: Optional[Dict] = None,
        top_n: int = 10,
    ) -> bool:
        """
        发送布林带扫描结果到飞书（富文本卡片）

        Args:
            scan_id: 扫描 ID
            scan_time: 扫描时间
            sector_results: 按板块分组的股票结果
            hot_sectors: 热点板块列表
            params: 扫描参数
            top_n: 每个板块最多展示股票数

        Returns:
            是否推送成功
        """
        if not self.enabled or not self.is_configured:
            logger.debug('[Feishu] 推送已禁用或未配置，跳过扫描通知')
            return False

        # 计算汇总信息
        total_stocks = sum(len(v) for v in sector_results.values())
        grade_s = sum(1 for stocks in sector_results.values() for s in stocks if s.get('grade') == 'S')
        grade_a = sum(1 for stocks in sector_results.values() for s in stocks if s.get('grade') == 'A')

        # 构建板块股票行
        stock_lines = []
        for sector_name, stocks in sector_results.items():
            stocks_sorted = sorted(stocks, key=lambda x: x.get('total_score', 0), reverse=True)
            for rank, stock in enumerate(stocks_sorted[:top_n], 1):
                grade = stock.get('grade', 'C')
                name = stock.get('name', '')
                code = stock.get('code', '')
                close = stock.get('close', 0)
                pct = stock.get('pct_change', 0)
                score = stock.get('total_score', 0)
                tags = stock.get('tags', [])

                # 颜色：S=红, A=橙, B=蓝, C=灰
                color_map = {'S': 'red', 'A': 'orange', 'B': 'blue', 'C': 'grey'}
                color = color_map.get(grade, 'grey')

                tag_str = ' | '.join(tags[:4]) if tags else ''
                tag_line = f'<annotation type=\"2\">{tag_str}</annotation>' if tag_str else ''

                line = {
                    'tag': 'div',
                    'text': {
                        'tag': 'lark_md',
                        'content': (
                            f'**{name}({code})** {pct:+.2f}% {close:.2f}元 '
                            f'| 评分:{score} {grade}级{tag_line}'
                        )
                    }
                }
                stock_lines.append(line)

        # 热点板块信息
        sector_info_lines = []
        for sec in (hot_sectors or [])[:5]:
            sec_name = sec.get('name', '')
            sec_change = sec.get('change', 0)
            sec_leader = sec.get('leader', '')
            sec_leader_change = sec.get('leader_change', 0)
            if sec_name:
                sector_info_lines.append({
                    'tag': 'div',
                    'text': {
                        'tag': 'lark_md',
                        'content': (
                            f'**{sec_name}** {sec_change:+.2f}% '
                            f'| 领涨: {sec_leader}({sec_leader_change:+.2f}%)'
                        )
                    }
                })

        # 构造卡片元素
        elements = [
            {
                'tag': 'div',
                'text': {
                    'tag': 'lark_md',
                    'content': (
                        f'**📊 布林带扫描 #{scan_id}**  '
                        f'`{scan_time}`  |  '
                        f'总计 {total_stocks} 只  |  '
                        f'<annotation type=\"3\" color=\"red\">S级 {grade_s}</annotation>  '
                        f'<annotation type=\"3\" color=\"orange\">A级 {grade_a}</annotation>'
                    )
                }
            },
            {'tag': 'hr'},
        ]

        if sector_info_lines:
            elements.append({
                'tag': 'div',
                'text': {
                    'tag': 'lark_md',
                    'content': '**🔥 热点板块**'
                }
            })
            elements.extend(sector_info_lines[:5])
            elements.append({'tag': 'hr'})

        if stock_lines:
            elements.append({
                'tag': 'div',
                'text': {
                    'tag': 'lark_md',
                    'content': f'**📈 符合条件股票 (前{top_n}只/板块)**'
                }
            })
            elements.extend(stock_lines)

            elements.append({'tag': 'hr'})
            elements.append({
                'tag': 'note',
                'elements': [
                    {
                        'tag': 'plain_text',
                        'content': f'🔔 由 facSstock 自动推送 | 扫描ID #{scan_id}'
                    }
                ]
            })
        else:
            elements.append({
                'tag': 'div',
                'text': {
                    'tag': 'lark_md',
                    'content': '⚠️ 本次扫描暂无符合条件股票'
                }
            })

        payload = {
            'msg_type': 'interactive',
            'card': {
                'config': {'wide_screen_mode': True},
                'header': {
                    'title': {
                        'tag': 'plain_text',
                        'content': f'📊 布林带策略扫描 #{scan_id}'
                    },
                    'template': 'blue'
                },
                'elements': elements
            }
        }

        return self._post(payload)

    def send_single_stock_alert(
        self,
        stock: Dict[str, Any],
        scan_id: int,
        scan_time: str,
    ) -> bool:
        """
        发送单只股票信号提醒

        Args:
            stock: 股票数据字典
            scan_id: 扫描 ID
            scan_time: 扫描时间
        """
        if not self.enabled or not self.is_configured:
            return False

        code = stock.get('code', '')
        name = stock.get('name', '')
        grade = stock.get('grade', 'C')
        close = stock.get('close', 0)
        pct = stock.get('pct_change', 0)
        tags = stock.get('tags', [])
        sector = stock.get('sector_name', '')
        score = stock.get('total_score', 0)

        tag_str = ' | '.join(tags[:6]) if tags else '无'

        payload = {
            'msg_type': 'interactive',
            'card': {
                'config': {'wide_screen_mode': True},
                'header': {
                    'title': {
                        'tag': 'plain_text',
                        'content': f'🚨 股票信号 #{grade}级'
                    },
                    'template': 'red' if grade in ('S', 'A') else 'orange'
                },
                'elements': [
                    {
                        'tag': 'div',
                        'text': {
                            'tag': 'lark_md',
                            'content': (
                                f'**{name}({code})**  '
                                f'收盘: {close:.2f}元  '
                                f'涨跌: {pct:+.2f}%'
                            )
                        }
                    },
                    {
                        'tag': 'div',
                        'text': {
                            'tag': 'lark_md',
                            'content': (
                                f'板块: **{sector}** | '
                                f'综合评分: **{score}** | '
                                f'等级: **{grade}级**'
                            )
                        }
                    },
                    {
                        'tag': 'div',
                        'text': {
                            'tag': 'lark_md',
                            'content': f'信号: {tag_str}'
                        }
                    },
                    {'tag': 'hr'},
                    {
                        'tag': 'note',
                        'elements': [
                            {
                                'tag': 'plain_text',
                                'content': f'🔔 facSstock 布林带策略 | {scan_time} | #{scan_id}'
                            }
                        ]
                    }
                ]
            }
        }

        return self._post(payload)

    def build_agent_digest_payload(self, digest: Dict[str, Any]) -> Dict[str, Any]:
        """构造游资智能体飞书策略推送卡片。"""
        slot_key = str(digest.get('slotKey') or '').strip()
        slot_label = str(digest.get('slotLabel') or '策略推送').strip()
        generated_at = str(digest.get('generatedAt') or datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        trigger_type = str(digest.get('triggerType') or 'manual').strip()

        market = digest.get('marketBrief') or {}
        session = market.get('session') or {}
        indices = market.get('indices') or []
        limit_up = int(float(market.get('limitUpCount') or 0))
        limit_down = int(float(market.get('limitDownCount') or 0))
        limit_source = str(market.get('limitSource') or '系统聚合').strip()
        session_phase = str(session.get('phase') or '策略时段').strip()

        consensus = digest.get('consensusStocks') or []
        reports = digest.get('agentReports') or []
        errors = digest.get('errors') or []

        header_template_map = {
            '0900': 'blue',
            '1230': 'orange',
            '1430': 'red',
            '2100': 'indigo',
        }
        header_template = header_template_map.get(slot_key, 'blue')

        def _format_pct(val: Any) -> str:
            try:
                return f"{float(val):+,.2f}%"
            except Exception:
                return "0.00%"

        def _format_price(val: Any) -> str:
            try:
                return f"{float(val):.2f}"
            except Exception:
                return "--"

        def _stance_label(val: str) -> str:
            mapping = {
                'bull': '看多',
                'bear': '谨慎',
                'neutral': '中性',
            }
            return mapping.get(str(val or '').strip().lower(), '中性')

        index_line = ' ｜ '.join(
            f"**{item.get('name', '')}** {_format_price(item.get('price'))} ({_format_pct(item.get('change'))})"
            for item in indices[:3]
            if item.get('name')
        ) or '指数数据待同步'

        summary = digest.get('summary') or {}
        agent_names = ' / '.join(
            str(item.get('agentName') or '').strip()
            for item in reports
            if item.get('agentName')
        ) or '暂无成功输出'

        elements: List[Dict[str, Any]] = [
            {
                'tag': 'div',
                'text': {
                    'tag': 'lark_md',
                    'content': (
                        f"**触发时间** `{generated_at}` ｜ **时段** `{slot_label}` ｜ **会话** `{session_phase}`\n"
                        f"**执行来源** {trigger_type} ｜ **成功智能体** {summary.get('successCount', 0)}/{summary.get('agentCount', 0)}\n"
                        f"**参与智能体** {agent_names}"
                    ),
                },
            },
            {
                'tag': 'div',
                'text': {
                    'tag': 'lark_md',
                    'content': (
                        f"{index_line}\n"
                        f"**涨跌停对比** `{limit_up}:{limit_down}` ｜ **口径** {limit_source} ｜ **数据时间** {market.get('limitTime') or generated_at[-8:]}"
                    ),
                },
            },
        ]

        if consensus:
            elements.append({'tag': 'hr'})
            elements.append({
                'tag': 'div',
                'text': {
                    'tag': 'lark_md',
                    'content': '**🎯 共识股票**',
                },
            })
            for idx, item in enumerate(consensus[:5], 1):
                support_agents = ' / '.join(item.get('supportAgents') or []) or '待观察'
                summary_line = (
                    f"{item.get('roleSummary') or '候选'} ｜ {item.get('entryModelSummary') or '观察'}"
                )
                if item.get('positionSummary'):
                    summary_line += f" ｜ {item.get('positionSummary')}"
                signal_line = str(item.get('signalSummary') or '').strip()
                content = (
                    f"**{idx}. {item.get('name', '')}({item.get('code', '')})** "
                    f"{_format_price(item.get('price'))} `{_format_pct(item.get('changePct'))}`\n"
                    f"共识强度：**{item.get('supportCount', 0)}** 家 ｜ {support_agents}\n"
                    f"{summary_line}"
                )
                if signal_line:
                    content += f"\n{signal_line}"
                elements.append({
                    'tag': 'div',
                    'text': {
                        'tag': 'lark_md',
                        'content': content,
                    },
                })

        if reports:
            elements.append({'tag': 'hr'})
            elements.append({
                'tag': 'div',
                'text': {
                    'tag': 'lark_md',
                    'content': '**🧠 智能体观点摘要**',
                },
            })
            for report in reports[:6]:
                stock_lines = []
                for stock in (report.get('recommendedStocks') or [])[:2]:
                    line = (
                        f"- **{stock.get('name', '')}({stock.get('code', '')})** "
                        f"{stock.get('role') or '候选'} ｜ {stock.get('entryModel') or '观察'}"
                    )
                    if stock.get('positionRatio'):
                        line += f" ｜ {stock.get('positionRatio')}"
                    if stock.get('signal'):
                        line += f"\n  {_short_text(stock.get('signal'), 80)}"
                    stock_lines.append(line)
                section = (
                    f"**{report.get('agentName', '')}｜{report.get('role') or '游资模型'}** "
                    f"{report.get('confidence', 0)}分 / {_stance_label(report.get('stance', 'neutral'))}\n"
                    f"市场：{_short_text(report.get('marketCommentary'), 80) or '待观察'}\n"
                    f"仓位：{_short_text(report.get('positionAdvice'), 80) or '按情绪调整'}\n"
                    f"风控：{_short_text(report.get('riskWarning'), 80) or '严格止损'}"
                )
                if stock_lines:
                    section += "\n" + "\n".join(stock_lines)
                elements.append({
                    'tag': 'div',
                    'text': {
                        'tag': 'lark_md',
                        'content': section,
                    },
                })

        if errors:
            elements.append({'tag': 'hr'})
            error_lines = []
            for item in errors[:4]:
                error_lines.append(
                    f"- {item.get('agentName') or item.get('agentId')}: {_short_text(item.get('error'), 60)}"
                )
            elements.append({
                'tag': 'div',
                'text': {
                    'tag': 'lark_md',
                    'content': "**⚠️ 未成功输出的智能体**\n" + '\n'.join(error_lines),
                },
            })

        elements.append({'tag': 'hr'})
        elements.append({
            'tag': 'note',
            'elements': [
                {
                    'tag': 'plain_text',
                    'content': f'facSstock 自动推送 | {slot_label} | {generated_at}',
                }
            ],
        })

        return {
            'msg_type': 'interactive',
            'card': {
                'config': {'wide_screen_mode': True},
                'header': {
                    'title': {
                        'tag': 'plain_text',
                        'content': f'📡 游资智能体策略推送｜{slot_label}',
                    },
                    'template': header_template,
                },
                'elements': elements,
            },
        }

    def send_agent_digest(self, digest: Dict[str, Any]) -> bool:
        """发送游资智能体策略汇总卡片。"""
        if not self.enabled or not self.is_configured:
            logger.debug('[Feishu] 推送已禁用或未配置，跳过智能体策略推送')
            return False
        payload = self.build_agent_digest_payload(digest)
        return self._post(payload)


# ── 全局单例 ──────────────────────────────────────────────────────────────────

_notifier: Optional[FeishuNotifier] = None


def get_feishu_notifier() -> FeishuNotifier:
    """获取飞书通知器单例"""
    global _notifier
    if _notifier is None:
        _notifier = FeishuNotifier()
    return _notifier


def send_feishu_scan_alert(scan_id: int, scan_time: str, sector_results: Dict,
                           hot_sectors: List, params: Optional[Dict] = None) -> bool:
    """快捷函数：发送扫描结果通知"""
    return get_feishu_notifier().send_scan_alert(
        scan_id=scan_id,
        scan_time=scan_time,
        sector_results=sector_results,
        hot_sectors=hot_sectors,
        params=params,
    )


def send_feishu_test(webhook_url: Optional[str] = None) -> bool:
    """快捷函数：发送测试消息；可指定 webhook_url 用于表单内测连"""
    notifier = FeishuNotifier(webhook_url=webhook_url) if webhook_url else FeishuNotifier()
    tail = notifier.webhook_url[-48:] if len(notifier.webhook_url) > 48 else notifier.webhook_url
    return notifier.send_text(
        f'✅ facSstock 飞书通知测试成功！\n'
        f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
        f'Webhook: …{tail}'
    )


def send_feishu_agent_digest(digest: Dict[str, Any], webhook_url: Optional[str] = None) -> bool:
    """快捷函数：发送游资智能体策略推送。"""
    notifier = FeishuNotifier(webhook_url=webhook_url) if webhook_url else FeishuNotifier()
    return notifier.send_agent_digest(digest)

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
FEISHU_WEBHOOK_URL = os.environ.get(
    'FEISHU_WEBHOOK_URL',
    'https://open.feishu.cn/open-apis/bot/v2/hook/22843403-5038-4d34-8105-63354f3f868f'
)

# 推送开关（生产环境建议设为 True）
FEISHU_ENABLED = os.environ.get('FEISHU_ENABLED', 'true').lower() in ('true', '1', 'yes')


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

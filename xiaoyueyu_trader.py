#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小鳄鱼智能交易员 - 龙头战法·超短狙击
====================================

设计思路：
1. 核心思想：只做最强龙头，市场只需要一个龙头
2. 选股标准：市场核心题材 + 连板高度 + 资金强
3. 买点策略：打板、分歧转一致、换手板
4. 卖点策略：龙头断板、情绪退潮、加速后兑现
5. 情绪周期：只在发酵期和高潮期重仓
6. 仓位管理：龙头确认重仓，不确定轻仓，退潮时空仓

Author: facSstock
"""

import time
import random
from functools import partial
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

import pandas as pd
import numpy as np

from utils.retry import retry_request
from cache import get as _cache_get, set as _cache_set, invalidate as _cache_invalidate

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 缓存 Key 常量
# ─────────────────────────────────────────────────────────────────────────────
_CACHE_KEY_HOT_SECTORS = 'xiaoyueyu/hot_sectors'
_CACHE_KEY_LEADER_STOCKS = 'xiaoyueyu/leader_stocks'
_CACHE_KEY_EMOTION = 'xiaoyueyu/emotion'
_CACHE_KEY_KLINE = 'xiaoyueyu/kline:{code}'
_CACHE_KEY_SCAN = 'xiaoyueyu/scan:{date}'

# ─────────────────────────────────────────────────────────────────────────────
# 情绪周期常量
# ─────────────────────────────────────────────────────────────────────────────
EMOTION_PHASES = {
    'startup': {'name': '启动期', 'description': '试探', 'position': '轻仓'},
    'fermentation': {'name': '发酵期', 'description': '扩散', 'position': '重仓'},
    'climax': {'name': '高潮期', 'description': '疯狂连板', 'position': '重仓'},
    'recession': {'name': '退潮期', 'description': '杀跌', 'position': '空仓'},
}


def _df_to_dict(df: pd.DataFrame) -> dict:
    """DataFrame → 普通 dict（用于 JSON 序列化）"""
    if df is None:
        return {}
    return {
        'columns': list(df.columns),
        'data': df.values.tolist(),
    }


def _dict_to_df(d: dict) -> pd.DataFrame:
    """dict → DataFrame"""
    if not d or not d.get('columns') or not d.get('data'):
        return pd.DataFrame()
    df = pd.DataFrame(d['data'], columns=d['columns'])
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = pd.to_numeric(df[col], errors='ignore')
    return df


def _scan_key() -> str:
    from datetime import date
    return _CACHE_KEY_SCAN.format(date=str(date.today()))


def _invalidate_all_xiaoyueyu():
    _cache_invalidate('xiaoyueyu/')


def _get_ak():
    """Lazy import akshare to avoid py_mini_rader crash."""
    import akshare as _ak
    return _ak


# ─────────────────────────────────────────────────────────────────────────────
# 数据获取器
# ─────────────────────────────────────────────────────────────────────────────

class DataFetcher:
    """
    数据获取器 - 统一封装各种数据源获取逻辑

    数据源优先级：
    1. 同花顺（行业板块、成分股、涨停股）
    2. 东方财富（大盘指数、资金流）
    3. 新浪（K线数据）
    """

    def __init__(self):
        self._ths_crawler = None

    @property
    def ths(self):
        """延迟加载同花顺爬虫"""
        if self._ths_crawler is None:
            from utils import ths_crawler
            self._ths_crawler = ths_crawler
        return self._ths_crawler

    def get_hot_sectors(self, top_n: int = 10) -> List[Dict]:
        """获取热点板块（带缓存，TTL 15分钟）"""
        cached = _cache_get(_CACHE_KEY_HOT_SECTORS)
        if cached is not None:
            logger.info("小鳄鱼热点板块命中缓存，返回前 %d 条", top_n)
            return cached[:top_n]

        try:
            df = retry_request(self.ths.get_ths_industry_list, max_retries=3, delay=1.0)

            if df is None or len(df) == 0:
                logger.warning("热点板块数据为空")
                return []

            name_col = '板块名称' if '板块名称' in df.columns else '板块'
            result = []

            for _, row in df.head(top_n).iterrows():
                result.append({
                    'name': row[name_col],
                    'code': row.get('代码', ''),
                    'change': float(row.get('涨跌幅', 0)),
                    'leader': row.get('领涨股', ''),
                    'leaderChange': float(row.get('领涨股-涨跌幅', 0)),
                })

            logger.info(f"小鳄鱼获取到 {len(result)} 个热点板块，存入缓存")
            _cache_set(_CACHE_KEY_HOT_SECTORS, result, ttl=900)
            return result

        except Exception as e:
            logger.error(f"获取热点板块失败: {e}")
            return []

    def get_limit_up_stocks(self) -> List[Dict]:
        """获取今日涨停股（核心：找龙头）"""
        try:
            df = _get_ak().stock_zt_pool_em(date=datetime.now().strftime('%Y%m%d'))

            if df is None or len(df) == 0:
                logger.warning("涨停板数据为空")
                return []

            result = []
            for _, row in df.iterrows():
                result.append({
                    'code': str(row.get('代码', '')),
                    'name': str(row.get('名称', '')),
                    'close': float(row.get('最新价', 0)),
                    'change_pct': float(row.get('涨跌幅', 0)),
                    'turnover': float(row.get('成交额', 0)),
                    'seals': float(row.get('封单额', 0)),
                    'continuity': int(row.get('连板数', 1)),
                    'reason': str(row.get('涨停统计', '')),
                })

            return result

        except Exception as e:
            logger.error(f"获取涨停股失败: {e}")
            return []

    def get_sector_stocks(self, sector_name: str, sector_code: str = '') -> List[Dict]:
        """获取板块成分股"""
        try:
            df = None
            if not sector_code:
                df = self.ths.get_ths_industry_list()
                name_col = '板块名称' if '板块名称' in df.columns else '板块'
                row = df[df[name_col] == sector_name]
                if len(row) > 0:
                    sector_code = row.iloc[0].get('代码', '')

            if not sector_code:
                logger.warning(f"未找到板块 '{sector_name}' 的代码")
                return []

            stocks = retry_request(
                partial(self.ths.fetch_ths_industry_stocks, sector_code, sector_name),
                max_retries=2, delay=0.5
            )

            if not stocks:
                return []

            stocks.sort(key=lambda x: x.get('market_cap', 0), reverse=True)
            return stocks

        except Exception as e:
            logger.error(f"获取板块 '{sector_name}' 成分股失败: {e}")
            return []

    def get_market_index(self) -> Dict:
        """获取大盘指数"""
        try:
            df = _get_ak().stock_zh_index_spot_sina()

            needed = {
                'sh000001': '上证指数',
                'sz399001': '深证成指',
                'sz399006': '创业板指',
            }

            result = {}
            for code, name in needed.items():
                row = df[df['代码'] == code]
                if not row.empty:
                    result[name] = {
                        'change': float(row.iloc[0].get('涨跌幅', 0)),
                        'price': float(row.iloc[0].get('现价', 0)),
                    }

            return result

        except Exception as e:
            logger.error(f"获取大盘指数失败: {e}")
            return {}

    def get_stock_kline(self, code: str, days: int = 60) -> Optional[pd.DataFrame]:
        """获取股票K线数据（带缓存，TTL 5分钟）"""
        key = _CACHE_KEY_KLINE.format(code=code)
        cached = _cache_get(key)
        if cached is not None:
            df = _dict_to_df(cached)
            if not df.empty:
                logger.info("股票 %s K线命中缓存", code)
                return df

        try:
            from utils.ths_crawler import get_stock_kline_sina

            df = retry_request(
                partial(get_stock_kline_sina, code, days=days),
                max_retries=2, delay=0.3
            )

            if df is not None and not df.empty:
                logger.info("股票 %s K线存入缓存", code)
                _cache_set(key, _df_to_dict(df), ttl=300)

            return df

        except Exception as e:
            logger.error(f"获取股票 {code} K线数据失败: {e}")
            return None

    def get_money_flow(self, code: str) -> Dict:
        """获取个股资金流向"""
        try:
            df = _get_ak().stock_individual_fund_flow(stock=code, market='sh' if code.startswith('6') else 'sz')

            if df is None or len(df) == 0:
                return {}

            latest = df.iloc[-1]
            return {
                'main_net_inflow': float(latest.get('主力净流入', 0) or 0),
                'main_ratio': float(latest.get('主力净流入占比', 0) or 0),
                'retail_net_inflow': float(latest.get('散户净流入', 0) or 0),
            }

        except Exception as e:
            logger.error(f"获取资金流向失败: {e}")
            return {}


# ─────────────────────────────────────────────────────────────────────────────
# 数据验证器
# ─────────────────────────────────────────────────────────────────────────────

class DataValidator:
    """数据验证器 - 确保数据质量"""

    @staticmethod
    def validate_stock_data(stock: Dict) -> Tuple[bool, str]:
        """验证股票数据有效性"""
        code = stock.get('code', '')
        name = stock.get('name', '')

        if not code or len(code) != 6:
            return False, f"无效代码: {code}"

        if not name or len(name) < 2:
            return False, f"无效名称: {name}"

        if 'ST' in name or '*' in name:
            return False, "ST类股票"

        return True, ""

    @staticmethod
    def validate_kline(df: Optional[pd.DataFrame], min_days: int = 20) -> bool:
        """验证K线数据有效性"""
        if df is None or len(df) == 0:
            return False

        if len(df) < min_days:
            return False

        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                return False

        return True

    @staticmethod
    def validate_emotion_cycle(index_data: Dict, limit_up_count: int) -> Dict:
        """
        验证市场情绪周期
        返回：{'phase': 'startup/fermentation/climax/recession', 'score': 0-100, 'description': ''}
        """
        avg_change = np.mean([v.get('change', 0) for v in index_data.values()])

        score = 50

        # 根据指数涨跌调整
        if avg_change > 2:
            score += 20
        elif avg_change > 1:
            score += 10
        elif avg_change < -2:
            score -= 30
        elif avg_change < -1:
            score -= 15

        # 根据涨停数量调整
        if limit_up_count > 100:
            score += 20
        elif limit_up_count > 50:
            score += 10
        elif limit_up_count < 20:
            score -= 20
        elif limit_up_count < 10:
            score -= 30

        score = max(0, min(100, score))

        if score >= 80:
            phase = 'climax'
        elif score >= 60:
            phase = 'fermentation'
        elif score >= 40:
            phase = 'startup'
        else:
            phase = 'recession'

        return {
            'phase': phase,
            'score': score,
            'name': EMOTION_PHASES[phase]['name'],
            'description': EMOTION_PHASES[phase]['description'],
            'positionAdvice': EMOTION_PHASES[phase]['position'],
        }


# ─────────────────────────────────────────────────────────────────────────────
# 扫描器核心 - 小鳄鱼战法
# ─────────────────────────────────────────────────────────────────────────────

class XiaoyueyuScanner:
    """
    小鳄鱼扫描器 - 核心选股逻辑

    策略要点：
    1. 只做龙头（涨停板、连板）
    2. 题材驱动（热点板块）
    3. 资金验证（封单大、回封强）
    4. 情绪周期（发酵期/高潮期重仓）
    5. 买点：打板、分歧转一致、换手板
    """

    def __init__(self, data_fetcher: DataFetcher, validator: DataValidator):
        self.fetcher = data_fetcher
        self.validator = validator

        self.min_limit_up_change = 9.5  # 涨停阈值
        self.min_continuity = 2  # 最小连板数
        self.min_seals_ratio = 0.1  # 最小封单占比

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        if df is None or df.empty:
            return df

        # 成交量均线
        df['vol_ma5'] = df['volume'].rolling(window=5).mean()
        df['vol_ma10'] = df['volume'].rolling(window=10).mean()
        df['volume_ratio'] = df['volume'] / df['vol_ma10']

        # 涨幅
        df['pct_change'] = df['close'].pct_change() * 100

        # 最近N天最大涨幅（用于识别连续涨停）
        df['max_gain_5d'] = df['close'].rolling(window=5).max() / df['close'].shift(5) - 1

        # 换手率（如果有）
        if 'turnover_rate' not in df.columns:
            df['turnover_rate'] = 0

        return df

    def _is_limit_up(self, row: pd.Series) -> bool:
        """判断是否涨停"""
        return row.get('pct_change', 0) >= self.min_limit_up_change

    def _analyze_limit_up_stock(self, stock: Dict) -> Optional[Dict]:
        """分析涨停股（龙头候选）"""
        code = stock['code']
        name = stock['name']

        # 获取K线数据
        df = self.fetcher.get_stock_kline(code, days=30)
        if not self.validator.validate_kline(df, min_days=10):
            return None

        df = self._calculate_indicators(df)

        latest = df.iloc[-1]

        # 核心指标
        continuity = stock.get('continuity', 1)
        seals_ratio = stock.get('seals', 0) / (stock.get('turnover', 1) + 1)
        volume_ratio = float(latest.get('volume_ratio', 1))
        turnover_rate = float(latest.get('turnover_rate', 0))

        score = 0
        tags = []

        # 连板评分（核心！）
        if continuity >= 4:
            score += 40
            tags.append(f"连续{continuity}板")
        elif continuity >= 3:
            score += 30
            tags.append(f"连续{continuity}板")
        elif continuity >= 2:
            score += 20
            tags.append(f"连续{continuity}板")

        # 封单评分
        if seals_ratio > 0.5:
            score += 20
            tags.append("封单强势")
        elif seals_ratio > 0.2:
            score += 10
            tags.append("封单良好")

        # 量能评分
        if volume_ratio >= 2:
            score += 15
            tags.append(f"放量{volume_ratio:.1f}倍")
        elif volume_ratio >= 1.5:
            score += 10
            tags.append("温和放量")

        # 换手率评分（换手板）
        if 5 <= turnover_rate <= 15:
            score += 15
            tags.append("换手充分")
        elif turnover_rate > 15:
            score += 5
            tags.append("高换手")

        # 近5日最大涨幅
        max_gain = float(latest.get('max_gain_5d', 0))
        if max_gain > 0.4:
            score += 10
            tags.append("强势上涨")

        score = min(100, score)

        # 等级评定
        if score >= 80 and continuity >= 3:
            grade = 'S'
        elif score >= 60:
            grade = 'A'
        elif score >= 40:
            grade = 'B'
        else:
            grade = 'C'

        return {
            'code': code,
            'name': name,
            'price': stock.get('close', 0),
            'changePct': stock.get('change_pct', 0),
            'continuity': continuity,
            'seals': stock.get('seals', 0),
            'sealsRatio': round(seals_ratio, 3),
            'turnover': stock.get('turnover', 0),
            'volumeRatio': round(volume_ratio, 2),
            'turnoverRate': round(turnover_rate, 2),
            'reason': stock.get('reason', ''),
            'score': score,
            'grade': grade,
            'tags': tags,

            # 买点建议
            'buyType': self._suggest_buy_type(continuity, seals_ratio, volume_ratio),
            'buyRange': self._suggest_buy_range(stock.get('close', 0), continuity),
            'stopLoss': self._suggest_stop_loss(stock.get('close', 0)),

            # 补充字段
            'maxGain5d': round(max_gain * 100, 2),
        }

    def _suggest_buy_type(self, continuity: int, seals_ratio: float, volume_ratio: float) -> str:
        """建议买点类型"""
        if continuity >= 3 and seals_ratio > 0.3:
            return "打板"
        elif seals_ratio < 0.1 and volume_ratio > 1.5:
            return "换手板"
        elif continuity >= 2:
            return "二板接力"
        else:
            return "首板确认"

    def _suggest_buy_range(self, close_price: float, continuity: int) -> str:
        """建议买入区间"""
        if continuity >= 3:
            # 连续涨停，可能一字板，无法买入
            return "排队涨停价"
        elif continuity >= 2:
            # 二板，回踩5日线附近
            return f"{close_price * 0.97:.2f}-{close_price * 1.00:.2f}"
        else:
            # 首板，次日观察开盘
            return f"{close_price * 0.98:.2f}-{close_price * 1.02:.2f}"

    def _suggest_stop_loss(self, close_price: float) -> str:
        """建议止损位"""
        return f"{close_price * 0.92:.2f}"

    def scan_limit_up(self) -> List[Dict]:
        """扫描涨停板（核心方法）"""
        logger.info("小鳄鱼扫描：获取涨停板数据...")

        limit_up_stocks = self.fetcher.get_limit_up_stocks()

        if not limit_up_stocks:
            logger.warning("今日无涨停数据")
            return []

        candidates = []

        for stock in limit_up_stocks:
            valid, reason = self.validator.validate_stock_data(stock)
            if not valid:
                continue

            result = self._analyze_limit_up_stock(stock)

            if result and result['score'] >= 30:
                candidates.append(result)

            time.sleep(random.uniform(0.05, 0.15))

        # 按连板数和评分排序
        candidates.sort(key=lambda x: (x['continuity'], x['score']), reverse=True)

        return candidates

    def scan_by_sector(self, sector_info: Dict) -> List[Dict]:
        """按板块扫描涨停股"""
        sector_name = sector_info['name']
        sector_code = sector_info.get('code', '')
        sector_change = sector_info.get('change', 0)

        stocks = self.fetcher.get_sector_stocks(sector_name, sector_code)

        if not stocks:
            return []

        results = []
        limit_up_stocks = self.fetcher.get_limit_up_stocks()
        limit_up_codes = {s['code'] for s in limit_up_stocks}

        for stock in stocks:
            if stock['code'] not in limit_up_codes:
                continue

            valid, reason = self.validator.validate_stock_data(stock)
            if not valid:
                continue

            limit_up_stock = next((s for s in limit_up_stocks if s['code'] == stock['code']), {})
            if limit_up_stock:
                limit_up_stock['sector_name'] = sector_name
                limit_up_stock['sector_change'] = sector_change
                result = self._analyze_limit_up_stock(limit_up_stock)

                if result and result['score'] >= 30:
                    result['sector_name'] = sector_name
                    result['sector_change'] = sector_change
                    results.append(result)

            time.sleep(random.uniform(0.05, 0.15))

        results.sort(key=lambda x: x['score'], reverse=True)
        return results


# ─────────────────────────────────────────────────────────────────────────────
# 扫描数据格式化
# ─────────────────────────────────────────────────────────────────────────────

def format_scan_data_for_prompt(candidates: List[Dict], max_main: int = 15) -> str:
    """
    将扫描结果格式化为 Prompt 中可读的文本表格。
    """
    if not candidates:
        return "【暂无扫描数据】"

    main_board = [s for s in candidates if s.get('code', '').startswith(('60', '00'))]
    other = [s for s in candidates if not s.get('code', '').startswith(('60', '00'))]

    main_board = sorted(main_board, key=lambda x: x.get('score', 0), reverse=True)[:max_main]
    other = sorted(other, key=lambda x: x.get('score', 0), reverse=True)[:5]

    lines = [f"共扫描到 {len(candidates)} 只涨停股，以下为评分 TOP 结果：\n"]

    if main_board:
        lines.append("## 主板股票（沪/深主板）")
        lines.append("")
        for i, s in enumerate(main_board, 1):
            lines.append(
                f"【股票{i}】{s.get('name','')}({s.get('code','')}) "
                f"- {s.get('score',0)}分（{s.get('grade','')}级）"
            )
            lines.append(
                f"  连板数={s.get('continuity',1)} | 封单比={s.get('sealsRatio',0):.2f} "
                f"| 量比={s.get('volumeRatio',0):.2f} "
                f"| 换手={s.get('turnoverRate',0):.2f}%"
            )
            lines.append(
                f"  买点={s.get('buyType','')} | 买入区间={s.get('buyRange','')} "
                f"| 止损={s.get('stopLoss','')}"
            )
            if s.get('tags'):
                lines.append(f"  标签：{' '.join(s['tags'])}")
            lines.append("")

    if other:
        lines.append("## 创业板/科创板")
        for i, s in enumerate(other, 1):
            lines.append(
                f"- {s.get('name','')}({s.get('code','')}) "
                f"{s.get('score',0)}分（{s.get('grade','')}级）"
                f" | 连板={s.get('continuity',1)}"
            )

    return "\n".join(lines)


def format_holdings_for_prompt(holdings: List[Dict]) -> str:
    """将历史持仓格式化为 Prompt 中可读的文本"""
    if not holdings:
        return "【暂无历史持仓数据】"

    lines = [f"当前持仓共 {len(holdings)} 只：\n"]
    for i, h in enumerate(holdings, 1):
        pl_pct = h.get('profit_loss_pct', 0) or 0
        pl_amt = h.get('profit_loss_amount', 0) or 0
        pl_icon = '🔴' if pl_pct < 0 else '🟢'
        lines.append(
            f"{pl_icon}【持仓{i}】{h.get('stock_name','')}({h.get('stock_code','')}) "
            f"| 盈亏：{pl_pct:+.2f}%（{pl_amt:+.2f}元）"
        )

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# AI 增强
# ─────────────────────────────────────────────────────────────────────────────

def enhance_with_ai(candidates: List[Dict], news: List[Dict],
                    current_time: str) -> Optional[Dict]:
    """
    使用统一 LLM 模块增强扫描结果（针对小鳄鱼战法）。
    """
    from utils.llm import get_client, get_agent_registry

    registry = get_agent_registry()
    client = get_client()
    agent = registry.get('xiaoyueyu')

    if not agent:
        logger.warning("未找到 xiaoyueyu agent 配置")
        return None

    # 格式化数据
    scan_text = format_scan_data_for_prompt(candidates)

    # 从 DB 读取历史持仓
    try:
        import database as _db
        holdings_list = _db.get_all_holdings()
        holdings_text = format_holdings_for_prompt(holdings_list)
    except Exception as e:
        logger.warning(f"读取持仓数据失败: {e}")
        holdings_list = []
        holdings_text = "【暂无历史持仓数据】"

    # 格式化新闻
    news_lines = []
    for idx, n in enumerate((news or [])[:8], 1):
        news_lines.append(
            f"【新闻{idx}】「[{n.get('time','')}] {n.get('title','')}」（{n.get('source','')}）"
        )
    news_text = "\n".join(news_lines) if news_lines else "【暂无最新消息】"

    # 构建 messages 并调用 LLM
    messages = registry.build_messages(
        agent_id='xiaoyueyu',
        scan_data=scan_text,
        news_data=news_text,
        holdings_data=holdings_text,
        current_time=current_time,
        scan_date=current_time[:10] if current_time else None,
    )

    from utils.llm import CallOptions
    options = CallOptions(
        temperature=agent.get('temperature', 0.25),
        max_tokens=agent.get('max_tokens', 3000),
    )

    resp = client.call_messages(messages, options)

    if not resp.success or not resp.content:
        logger.warning("LLM 调用失败: %s，跳过 AI 增强", resp.error)
        return None

    logger.info(
        "[XIAOYUEYU-AI] raw_response_len=%d tokens=%d",
        len(resp.content), resp.tokens_used
    )

    # 解析 JSON
    parsed = registry.extract_json(resp.content)

    if parsed:
        logger.info("[XIAOYUEYU-AI] parsed stance=%s confidence=%s recommendedStocks_count=%d",
                    parsed.get('stance'), parsed.get('confidence'),
                    len(parsed.get('recommendedStocks') or []))
        parsed = registry.sanitize(
            parsed,
            candidates,
            default_advise_type=agent.get('adviseType', '打板'),
        )

    # 构建推荐股列表
    recommended = []
    for s in (parsed.get('recommendedStocks') or [])[:3]:
        code = s.get('code', '')
        src = next((c for c in candidates if c.get('code') == code), {})
        recommended.append({
            'code': s.get('code', '') or src.get('code', ''),
            'name': s.get('name', '') or src.get('name', ''),
            'price': s.get('price') if s.get('price') is not None else src.get('price', 0),
            'changePct': s.get('changePct') if s.get('changePct') is not None else src.get('changePct', 0),
            'score': s.get('score') if s.get('score') is not None else src.get('score', 0),
            'grade': s.get('grade', '') or src.get('grade', ''),
            'buyRange': s.get('buyRange', '') or src.get('buyRange', ''),
            'stopLoss': s.get('stopLoss', '') or src.get('stopLoss', ''),
            'signal': s.get('signal', ''),
            'riskLevel': s.get('riskLevel', ''),
            'adviseType': s.get('adviseType', src.get('buyType', '打板')),
            'continuity': src.get('continuity', 0),
            'meta': s.get('meta', ''),
        })

    # 持久化分析历史
    try:
        import database as _db
        report_date = current_time[:10] if current_time else ""
        if parsed:
            analysis_payload = {
                'agentId': parsed.get('agentId', 'xiaoyueyu'),
                'agentName': parsed.get('agentName', agent['name']),
                'stance': parsed.get('stance', 'neutral'),
                'confidence': int(parsed.get('confidence', 50)),
                'marketCommentary': str(parsed.get('marketCommentary', '')),
                'positionAdvice': str(parsed.get('positionAdvice', '')),
                'riskWarning': str(parsed.get('riskWarning', '')),
                'recommendedStocks': recommended,
            }
            snap = _db.build_analysis_holdings_snapshot(holdings_list, analysis_payload)
            _db.save_agent_analysis_history(
                agent_id='xiaoyueyu',
                report_date=report_date,
                holdings_snapshot=snap,
                analysis_result=analysis_payload,
                raw_response=resp.content,
                stance=parsed.get('stance', 'neutral'),
                confidence=int(parsed.get('confidence', 50)),
                tokens_used=resp.tokens_used,
            )

            # 同步推荐股票到持仓表
            if recommended:
                saved = _db.save_recommended_stocks_as_holdings('xiaoyueyu', recommended)
                logger.info(f"[XIAOYUEYU-AI] 推荐股票已写入 holdings 表，共 {saved} 条")

    except Exception as hist_err:
        logger.warning(f"[XIAOYUEYU-AI] 保存分析历史失败: {hist_err}")

    if not parsed:
        return {
            'agentId': 'xiaoyueyu',
            'agentName': agent['name'],
            'success': True,
            'raw_response': resp.content,
            'structured': None,
            'analysis': resp.content,
            'tokens_used': resp.tokens_used,
        }

    return {
        'agentId': parsed.get('agentId', 'xiaoyueyu'),
        'agentName': parsed.get('agentName', agent['name']),
        'success': True,
        'raw_response': resp.content,
        'structured': {
            'agentId': parsed.get('agentId', 'xiaoyueyu'),
            'agentName': parsed.get('agentName', agent['name']),
            'stance': parsed.get('stance', 'neutral'),
            'confidence': int(parsed.get('confidence', 50)),
            'marketCommentary': str(parsed.get('marketCommentary', '')),
            'positionAdvice': str(parsed.get('positionAdvice', '')),
            'riskWarning': str(parsed.get('riskWarning', '')),
            'recommendedStocks': recommended,
        },
        'analysis': _build_report_text(parsed, recommended),
        'tokens_used': resp.tokens_used,
    }


def _build_report_text(parsed: dict, recommended: list) -> str:
    """从 structured JSON 生成自然语言分析报告文本"""
    stance_label = {'bull': '看多', 'bear': '看空', 'neutral': '中性'}.get(
        parsed.get('stance', 'neutral'), '中性')
    confidence = parsed.get('confidence', 0)
    commentary = parsed.get('marketCommentary', '暂无市场简评。')
    position = parsed.get('positionAdvice', '')
    risk = parsed.get('riskWarning', '')
    agent_name = parsed.get('agentName', '小鳄鱼')

    lines = [
        f"【市场总评】",
        f"当前 AI 立场：**{stance_label}**（信心指数 {confidence}%）",
        f"{commentary}",
        f"",
        f"【仓位建议】",
        f"{position or '暂无具体建议'}",
    ]
    if risk:
        lines.append(f"")
        lines.append(f"【风险提示】")
        lines.append(f"{risk}")

    if recommended:
        lines.append(f"")
        lines.append(f"【龙头标的】")
        for i, st in enumerate(recommended, 1):
            name = st.get('name', '未知')
            code = st.get('code', '')
            continuity = st.get('continuity', 0)
            price = st.get('price', 0)
            change = st.get('changePct', 0)
            buy_range = st.get('buyRange', '—')
            stop = st.get('stopLoss', '—')
            advise = st.get('adviseType', '')
            signal = st.get('signal', '')

            lines.append(
                f"{i}. **{name}**（{code}）| 连板={continuity} | 现价{price}元 "
                f"({'+' if change >= 0 else ''}{change}%）"
            )
            detail_parts = []
            if advise:
                detail_parts.append(f"买点：{advise}")
            if buy_range and buy_range != '—':
                detail_parts.append(f"区间：{buy_range}")
            if stop and stop != '—':
                detail_parts.append(f"止损：{stop}")
            if detail_parts:
                lines.append(f"   {' | '.join(detail_parts)}")
            if signal:
                lines.append(f"   信号：{signal}")

    lines.append(f"")
    lines.append(f"—— 以上分析由【{agent_name}】生成，仅供参考，不构成投资建议。")
    return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 主控制器
# ─────────────────────────────────────────────────────────────────────────────

class XiaoyueyuTrader:
    """
    小鳄鱼智能交易员 - 主控制器

    负责协调整个扫描流程：
    1. 获取大盘环境 + 情绪周期
    2. 获取热点板块
    3. 扫描涨停板（找龙头）
    4. AI 增强分析
    5. 生成建议
    """

    def __init__(self, api_key: str = None, use_ai: bool = True):
        self.fetcher = DataFetcher()
        self.validator = DataValidator()
        self.scanner = XiaoyueyuScanner(self.fetcher, self.validator)
        self.use_ai = use_ai

        self.last_scan_time: Optional[datetime] = None
        self.last_hot_sectors: List[Dict] = []
        self.last_candidates: List[Dict] = []
        self.last_emotion: Dict = {}
        self.last_ai_result: Optional[Dict] = None

    def get_market_condition(self) -> Dict:
        """获取市场环境"""
        index_data = self.fetcher.get_market_index()
        limit_up_stocks = self.fetcher.get_limit_up_stocks()
        limit_up_count = len(limit_up_stocks)

        emotion = self.validator.validate_emotion_cycle(index_data, limit_up_count)

        self.last_emotion = emotion

        logger.info(f"市场环境: {emotion['name']} (评分={emotion['score']}, 涨停={limit_up_count})")

        return {
            'indexData': index_data,
            'limitUpCount': limit_up_count,
            'emotion': emotion,
            'timestamp': datetime.now().isoformat(),
        }

    def get_hot_sectors(self, top_n: int = 5) -> List[Dict]:
        """动态获取热点板块"""
        try:
            sectors = self.fetcher.get_hot_sectors(top_n)
            if not sectors:
                logger.warning("热点板块为空")
                return []

            self.last_hot_sectors = sectors
            return sectors

        except Exception as e:
            logger.error(f"获取热点板块失败: {e}")
            return []

    def get_news(self) -> List[Dict]:
        """获取市场新闻"""
        try:
            from ai_service import fetch_market_news
            return fetch_market_news() or []
        except Exception as e:
            logger.warning(f"获取新闻失败（非致命）: {e}")
            return []

    def run_daily_scan(self, enhance: bool = None) -> Dict:
        """
        执行每日扫描（找龙头）

        Returns:
            扫描结果字典
        """
        start_time = datetime.now()
        enhance = enhance if enhance is not None else self.use_ai

        logger.info("=" * 60)
        logger.info("🐊 小鳄鱼每日扫描开始")
        logger.info("=" * 60)

        # 1. 市场环境 + 情绪周期
        market = self.get_market_condition()

        # 2. 热点板块
        hot_sectors = self.get_hot_sectors(5)

        # 3. 扫描涨停板（找龙头）
        candidates = self.scanner.scan_limit_up()

        # 4. 如果有板块数据，按板块标记
        sector_map = {s['name']: s for s in hot_sectors}
        for c in candidates:
            for sector_name, sector_info in sector_map.items():
                if sector_name in c.get('reason', ''):
                    c['sector_name'] = sector_name
                    c['sector_change'] = sector_info.get('change', 0)
                    break

        # 5. 汇总统计
        stats = {
            'totalCandidates': len(candidates),
            'gradeS': sum(1 for c in candidates if c['grade'] == 'S'),
            'gradeA': sum(1 for c in candidates if c['grade'] == 'A'),
            'gradeB': sum(1 for c in candidates if c['grade'] == 'B'),
            'leaders': sum(1 for c in candidates if c.get('continuity', 0) >= 2),
            'continuity2': sum(1 for c in candidates if c.get('continuity', 0) == 2),
            'continuity3': sum(1 for c in candidates if c.get('continuity', 0) == 3),
            'continuity4plus': sum(1 for c in candidates if c.get('continuity', 0) >= 4),
        }

        # 6. 精选推荐
        recommendations = self._generate_recommendations(candidates)

        # 7. AI 增强
        ai_result = None
        if enhance:
            logger.info("🤖 启动 AI 增强分析...")
            news = self.get_news()
            ai_result = enhance_with_ai(candidates, news, start_time.isoformat())
            if ai_result:
                self.last_ai_result = ai_result
                logger.info(f"✅ AI 增强完成，tokens={ai_result.get('tokens_used', 0)}")

        # 8. 更新状态
        self.last_scan_time = datetime.now()
        self.last_candidates = candidates

        elapsed = (datetime.now() - start_time).total_seconds()

        result = {
            'success': True,
            'scanTime': start_time.isoformat(),
            'elapsedSeconds': round(elapsed, 1),

            'market': market,
            'hotSectors': hot_sectors,
            'emotion': market['emotion'],

            'stats': stats,
            'recommendations': recommendations,
            'candidates': candidates[:20],

            # AI 增强结果
            'agentResult': ai_result,

            'summary': self._generate_summary(stats, market),
        }

        logger.info("=" * 60)
        logger.info(f"✅ 扫描完成: {stats['totalCandidates']} 只候选, 耗时 {elapsed:.1f}s")
        logger.info(f"   情绪周期: {market['emotion']['name']} ({market['emotion']['positionAdvice']})")
        logger.info(f"   龙头数量: {stats['leaders']} 只（连板≥2）")
        logger.info("=" * 60)

        return result

    def _generate_recommendations(self, candidates: List[Dict]) -> List[Dict]:
        """生成精选推荐"""
        recommendations = []

        # 优先选择高连板 + 高评分
        top = sorted(candidates, key=lambda x: (x.get('continuity', 0), x.get('score', 0)), reverse=True)

        for c in top[:5]:
            recommendations.append({
                'code': c['code'],
                'name': c['name'],
                'grade': c['grade'],
                'score': c['score'],
                'price': c['price'],
                'changePct': c['changePct'],
                'continuity': c.get('continuity', 0),
                'sealsRatio': c.get('sealsRatio', 0),
                'buyType': c.get('buyType', ''),
                'buyRange': c.get('buyRange', ''),
                'stopLoss': c.get('stopLoss', ''),
                'tags': c.get('tags', []),
                'reason': c.get('reason', ''),
                'sectorName': c.get('sector_name', ''),
            })

        return recommendations

    def _generate_summary(self, stats: Dict, market: Dict) -> str:
        """生成扫描摘要"""
        emotion = market['emotion']

        return f"""
🐊 小鳄鱼每日扫描报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 市场环境
   情绪周期: {emotion['name']}（{emotion['description']}）
   仓位建议: {emotion['positionAdvice']}
   涨停数量: {market['limitUpCount']} 只

📈 龙头扫描
   候选股票: {stats['totalCandidates']} 只
   二连板: {stats['continuity2']} 只
   三连板+: {stats['continuity3']} 只
   四连板+: {stats['continuity4plus']} 只

🎯 核心策略
   核心思想：只做最强龙头，市场只需要一个龙头
   买点：打板、二板接力、分歧转一致、换手板
   卖点：龙头断板、情绪退潮、加速后兑现

⚠️ 风险提示
   超短线交易风险极高，请严格止损
   本报告仅供参考，不构成投资建议
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# Flask API 端点
# ─────────────────────────────────────────────────────────────────────────────

def register_xiaoyueyu_routes(bp, get_cache, set_cache, invalidate_cache, db_module):
    """注册 XiaoyueyuTrader 相关路由"""

    _xiaoyueyu_trader = None

    def _trader():
        nonlocal _xiaoyueyu_trader
        if _xiaoyueyu_trader is None:
            _xiaoyueyu_trader = XiaoyueyuTrader(use_ai=True)
        return _xiaoyueyu_trader

    from flask import request, jsonify
    import logging as _logger

    @bp.route('/api/xiaoyueyu/market')
    def xiaoyueyu_market():
        """获取市场状态"""
        try:
            result = _trader().get_market_condition()
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            _logger.error(f"获取市场状态失败: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @bp.route('/api/xiaoyueyu/sectors')
    def xiaoyueyu_sectors():
        """获取热点板块"""
        try:
            limit = request.args.get('limit', 10, type=int)
            limit = max(1, min(50, limit))
            sectors = _trader().get_hot_sectors(top_n=limit)
            return jsonify({'success': True, 'data': sectors})
        except Exception as e:
            _logger.error(f"获取热点板块失败: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @bp.route('/api/xiaoyueyu/scan', methods=['POST'])
    def xiaoyueyu_scan():
        """执行扫描"""
        try:
            data = request.json or {}
            enhance = data.get('enhance', True)
            force_refresh = data.get('force', False)

            cache_key = _scan_key()

            # 同日直接返回缓存
            if not force_refresh:
                cached_result = _cache_get(cache_key)
                if cached_result is not None:
                    _logger.info("小鳄鱼扫描结果命中缓存，直接返回")
                    return jsonify({'success': True, 'data': cached_result, 'fromCache': True})

            _logger.info("小鳄鱼扫描开始: enhance=%s", enhance)

            result = _trader().run_daily_scan(enhance=enhance)

            # 保存扫描记录到 DB
            try:
                scan_id = db_module.create_scan_record({
                    'sectors': 0,
                    'mode': 'xiaoyueyu',
                })
                if scan_id and result.get('hotSectors'):
                    db_module.save_hot_sectors(scan_id, result['hotSectors'])
                invalidate_cache('scan/history')
            except Exception as db_err:
                _logger.warning(f"保存扫描记录失败（非致命）: {db_err}")

            # 存入缓存（4h TTL）
            _cache_set(cache_key, result, ttl=14400)
            _logger.info("小鳄鱼扫描结果已缓存")

            return jsonify({'success': True, 'data': result})

        except Exception as e:
            _logger.error(f"小鳄鱼扫描失败: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @bp.route('/api/xiaoyueyu/status')
    def xiaoyueyu_status():
        """获取扫描状态"""
        try:
            trader = _trader()
            return jsonify({
                'success': True,
                'data': {
                    'lastScanTime': trader.last_scan_time.isoformat() if trader.last_scan_time else None,
                    'lastCandidatesCount': len(trader.last_candidates),
                    'hasAiResult': trader.last_ai_result is not None,
                    'emotion': trader.last_emotion,
                }
            })
        except Exception as e:
            _logger.error(f"获取状态失败: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @bp.route('/api/xiaoyueyu/ai-result')
    def xiaoyueyu_ai_result():
        """获取最近一次 AI 增强分析结果"""
        try:
            trader = _trader()
            if not trader.last_ai_result:
                return jsonify({'success': False, 'error': '暂无 AI 分析结果'})
            return jsonify({'success': True, 'data': trader.last_ai_result})
        except Exception as e:
            _logger.error(f"获取 AI 结果失败: {e}")
            return jsonify({'success': False, 'error': str(e)})


# ─────────────────────────────────────────────────────────────────────────────
# 命令行入口
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    parser = argparse.ArgumentParser(description='小鳄鱼智能交易员')
    parser.add_argument('--top', type=int, default=10, help='返回TOP N结果')
    parser.add_argument('--no-ai', action='store_true', help='禁用 AI 增强')

    args = parser.parse_args()

    trader = XiaoyueyuTrader(use_ai=not args.no_ai)
    result = trader.run_daily_scan()

    print("\n" + "=" * 60)
    print("🐊 小鳄鱼精选龙头")
    print("=" * 60)

    print(f"\n情绪周期: {result['emotion']['name']} - {result['emotion']['positionAdvice']}")

    for i, rec in enumerate(result['recommendations'][:args.top], 1):
        print(f"\n{i}. {rec['name']} ({rec['code']})")
        print(f"   连板: {rec['continuity']} | 等级: {rec['grade']} | 评分: {rec['score']}")
        print(f"   现价: {rec['price']} | 涨跌: {rec['changePct']:+.2f}%")
        print(f"   买点: {rec['buyType']} | 区间: {rec['buyRange']} | 止损: {rec['stopLoss']}")
        print(f"   标签: {', '.join(rec['tags'])}")

    if result.get('agentResult') and result['agentResult'].get('success'):
        ar = result['agentResult']
        print("\n" + "=" * 60)
        print(f"🤖 AI 增强分析（{ar.get('agentName', '小鳄鱼')}）")
        print("=" * 60)
        s = ar.get('structured', {})
        print(f"立场: {s.get('stance')} | 信心: {s.get('confidence')}%")
        print(f"市场解读: {s.get('marketCommentary')}")
        print(f"策略建议: {s.get('positionAdvice')}")
        print(f"风险提示: {s.get('riskWarning')}")

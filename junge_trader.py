#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钧哥智能交易员 - 龙头战法自动化执行
====================================

设计思路：
1. 动态获取热点板块，聚焦主线
2. 布林带极度收缩 + 放量 = 主力蓄力信号
3. 板块中军筛选（资金沉淀稳健）
4. 多指标综合评分（S/A/B/C 等级）
5. 降级策略：热点失败 → 全市场谨慎扫描
6. AI 增强：对接 agent_prompts.py 统一 Prompt 工程

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
from bollinger_squeeze_strategy import BollingerSqueezeStrategy
from cache import get as _cache_get, set as _cache_set, invalidate as _cache_invalidate

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 缓存 Key 常量
# ─────────────────────────────────────────────────────────────────────────────
_CACHE_KEY_SECTORS = 'junge/hot_sectors'
_CACHE_KEY_SECTOR_STOCKS = 'junge/sector_stocks:{sector_name}'
_CACHE_KEY_KLINE = 'junge/kline:{code}'
_CACHE_KEY_SCAN = 'junge/scan:{date}:{sectors}'

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

def _sector_stocks_key(name: str) -> str:
    return _CACHE_KEY_SECTOR_STOCKS.format(sector_name=name)

def _kline_key(code: str) -> str:
    return _CACHE_KEY_KLINE.format(code=code)

def _scan_key(sectors: int) -> str:
    from datetime import date
    return _CACHE_KEY_SCAN.format(date=str(date.today()), sectors=sectors)

def _invalidate_all_junge():
    _cache_invalidate('junge/')


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
    1. 同花顺（行业板块、成分股）
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
        cached = _cache_get(_CACHE_KEY_SECTORS)
        if cached is not None:
            logger.info("热点板块命中缓存，返回前 %d 条", top_n)
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

            logger.info(f"获取到 {len(result)} 个热点板块，存入缓存")
            _cache_set(_CACHE_KEY_SECTORS, result, ttl=900)   # 15min
            return result

        except Exception as e:
            logger.error(f"获取热点板块失败: {e}")
            return []

    def get_sector_stocks(self, sector_name: str, sector_code: str = '') -> List[Dict]:
        """获取板块成分股（带缓存，TTL 5分钟）"""
        key = _sector_stocks_key(sector_name)
        cached = _cache_get(key)
        if cached is not None:
            logger.info("板块 '%s' 成分股命中缓存", sector_name)
            return cached

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

            for i, stock in enumerate(stocks):
                stock['isLeader'] = i < 3
                stock['leaderRank'] = i + 1 if i < 3 else 0

            logger.info(f"板块 '{sector_name}' 获取到 {len(stocks)} 只成分股，存入缓存")
            _cache_set(key, stocks, ttl=300)   # 5min
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

    def get_stock_kline(self, code: str, days: int = 120) -> Optional[pd.DataFrame]:
        """获取股票K线数据（带缓存，TTL 5分钟）"""
        key = _kline_key(code)
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
                _cache_set(key, _df_to_dict(df), ttl=300)   # 5min

            return df

        except Exception as e:
            logger.error(f"获取股票 {code} K线数据失败: {e}")
            return None


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
    def validate_kline(df: Optional[pd.DataFrame], min_days: int = 60) -> bool:
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
    def validate_market_condition(index_data: Dict) -> Dict:
        """验证市场环境"""
        if not index_data:
            return {'status': 'unknown', 'bullish': False}

        avg_change = np.mean([v.get('change', 0) for v in index_data.values()])

        if avg_change > 1:
            status = '强势上涨'
            bullish = True
        elif avg_change > 0:
            status = '小幅上涨'
            bullish = True
        elif avg_change > -1:
            status = '小幅调整'
            bullish = False
        else:
            status = '大幅调整'
            bullish = False

        return {
            'status': status,
            'bullish': bullish,
            'avgChange': round(avg_change, 2),
        }


# ─────────────────────────────────────────────────────────────────────────────
# 扫描器核心
# ─────────────────────────────────────────────────────────────────────────────

class JunGeScanner:
    """
    钧哥扫描器 - 核心选股逻辑

    策略要点：
    1. 布林带极度收缩（带宽 < 5% 或 连续收缩 ≥ 3天）
    2. 放量信号（量比 > 1.2）
    3. 资金流入（CMF > 0）
    4. 超卖回升（RSV < 30）或 MACD 金叉
    5. 优先板块中军（市值前3）
    """

    def __init__(self, data_fetcher: DataFetcher, validator: DataValidator):
        self.fetcher = data_fetcher
        self.validator = validator
        self.strategy = BollingerSqueezeStrategy()

        self.min_squeeze_days = 3
        self.min_bb_width_pct = 5.0
        self.min_volume_ratio = 1.2
        self.max_results_per_sector = 10

    def _add_cmf(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算 Chaikin Money Flow (CMF)"""
        if 'volume' not in df.columns or 'close' not in df.columns:
            df['cmf'] = 0.0
            return df

        period = 20
        close = df['close']
        low = df.get('low', close)
        high = df.get('high', close)

        money_flow_multiplier = ((close - low) - (high - close)) / (high - low + 1e-10)
        money_flow_multiplier = money_flow_multiplier.fillna(0)
        money_flow_volume = money_flow_multiplier * df['volume']
        cmf_series = money_flow_volume.rolling(window=period).sum() / df['volume'].rolling(window=period).sum()
        df['cmf'] = cmf_series.fillna(0)
        return df

    def analyze_stock(self, code: str, name: str, sector_name: str = '',
                      sector_change: float = 0, is_leader: bool = False,
                      leader_rank: int = 0) -> Optional[Dict]:
        """分析单只股票"""
        df = self.fetcher.get_stock_kline(code, days=120)

        if not self.validator.validate_kline(df):
            return None

        df = self.strategy.calculate_bollinger_bands(df)
        df = self.strategy.calculate_squeeze_signal(df)
        df = self.strategy.calculate_volume_signal(df)
        df = self.strategy.calculate_trend_indicators(df)
        df = self._add_cmf(df)

        latest = df.iloc[-1]

        bb_width_pct = float(latest.get('bb_width_pct', 999))
        squeeze_streak = int(latest.get('squeeze_streak', 0))
        volume_ratio = float(latest.get('volume_ratio', 0))
        cmf = float(latest.get('cmf', 0))
        rsv = float(latest.get('rsi', 50))
        pct_change = float(latest.get('pct_change', 0))
        turnover = float(latest.get('turnover', 0))

        score = 0
        tags = []

        # 布林带收缩评分（最高30分）
        if squeeze_streak >= self.min_squeeze_days:
            score += 20
            tags.append(f"收缩{squeeze_streak}天")
        if bb_width_pct < self.min_bb_width_pct:
            score += 10
            tags.append("极度收缩")

        # 量能评分（最高20分）
        if volume_ratio >= self.min_volume_ratio:
            score += 15
            tags.append(f"放量{volume_ratio:.1f}倍")
        elif volume_ratio >= 1.0:
            score += 5

        # 资金流向评分（最高20分）
        if cmf > 0.1:
            score += 20
            tags.append("强势流入")
        elif cmf > 0:
            score += 10
            tags.append("资金流入")

        # 超卖/动量评分（最高15分）
        if rsv < 30:
            score += 15
            tags.append(f"超卖RSV={rsv:.0f}")
        elif rsv < 50:
            score += 8
            tags.append("低位RSV")

        if latest.get('macd_golden', False):
            score += 10
            tags.append("MACD金叉")

        # 趋势评分（最高15分）
        if latest.get('ma_full_bullish', False):
            score += 15
            tags.append("多头排列")
        elif latest.get('ma_bullish', False):
            score += 8
            tags.append("短多")

        # 等级评定
        if score >= 85:
            grade = 'S'
        elif score >= 70:
            grade = 'A'
        elif score >= 50:
            grade = 'B'
        else:
            grade = 'C'

        # 中军加分
        if is_leader:
            score += 5
            tags.append(f"中军#{leader_rank}")

        score = min(100, score)

        close_price = float(latest.get('close', 0))

        return {
            'code': code,
            'name': name,
            'sector': sector_name,
            'sectorChange': sector_change,
            'price': close_price,
            'changePct': round(pct_change, 2),
            'score': score,
            'grade': grade,
            'tags': tags,

            # 详细指标
            'bbWidthPct': round(bb_width_pct, 2),
            'squeezeDays': squeeze_streak,
            'volumeRatio': round(volume_ratio, 2),
            'cmf': round(cmf, 3),
            'rsv': round(rsv, 1),
            'turnover': round(turnover, 2),

            # 趋势
            'isLeader': is_leader,
            'leaderRank': leader_rank,

            # 买入建议（来自指标计算）
            'buyRange': f"{close_price * 0.98:.2f}-{close_price * 1.01:.2f}",
            'stopLoss': f"{close_price * 0.95:.2f}",

            # 补充字段（对接 agent_prompts.py）
            'squeezeRatio': round(bb_width_pct, 2),
            'marketCap': 0,
        }

    def scan_by_sector(self, sector_info: Dict) -> List[Dict]:
        """扫描单个板块"""
        sector_name = sector_info['name']
        sector_code = sector_info.get('code', '')
        sector_change = sector_info.get('change', 0)

        stocks = self.fetcher.get_sector_stocks(sector_name, sector_code)

        if not stocks:
            return []

        results = []

        for stock in stocks:
            valid, reason = self.validator.validate_stock_data(stock)
            if not valid:
                continue

            result = self.analyze_stock(
                code=stock['code'],
                name=stock['name'],
                sector_name=sector_name,
                sector_change=sector_change,
                is_leader=stock.get('isLeader', False),
                leader_rank=stock.get('leaderRank', 0),
            )

            if result and result['score'] >= 50:
                results.append(result)

            time.sleep(random.uniform(0.05, 0.15))

        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:self.max_results_per_sector]

    def scan_all_stocks(self, stock_codes: List[str] = None) -> List[Dict]:
        """降级策略：全市场扫描"""
        logger.warning("使用降级策略：全市场扫描")

        if stock_codes is None:
            try:
                df = _get_ak().stock_zh_a_spot_em()
                if df is not None and len(df) > 0:
                    df = df.nlargest(200, '涨跌幅')
                    stock_codes = df['代码'].tolist()
            except Exception as e:
                logger.error(f"获取全市场股票列表失败: {e}")
                return []

        results = []
        for code in stock_codes[:50]:
            try:
                result = self.analyze_stock(code=code, name='')
                if result and result['score'] >= 70:
                    results.append(result)
            except Exception:
                continue

            time.sleep(random.uniform(0.1, 0.2))

        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:20]


# ─────────────────────────────────────────────────────────────────────────────
# 扫描数据格式化（对接 agent_prompts.py）
# ─────────────────────────────────────────────────────────────────────────────

def format_scan_data_for_prompt(candidates: List[Dict], max_main: int = 15,
                                 max_other: int = 5) -> str:
    """
    将扫描结果格式化为 Prompt 中可读的文本表格。

    格式参考 agent_prompts.py 中的 USER_COMMON_HEADER：
    - 主板股票放前面（60/00 开头）
    - 每只股票包含所有关键字段
    """
    if not candidates:
        return "【暂无扫描数据】"

    main_board = [s for s in candidates if s.get('code', '').startswith(('60', '00'))]
    other = [s for s in candidates if not s.get('code', '').startswith(('60', '00'))]

    main_board = sorted(main_board, key=lambda x: x.get('score', 0), reverse=True)[:max_main]
    other = sorted(other, key=lambda x: x.get('score', 0), reverse=True)[:max_other]

    lines = [f"共扫描到 {len(candidates)} 只股票，以下为评分 TOP 结果：\n"]

    if main_board:
        lines.append("## 主板股票（沪/深主板）")
        lines.append("")
        for i, s in enumerate(main_board, 1):
            lines.append(
                f"【股票{i}】{s.get('name','')}({s.get('code','')}) "
                f"- {s.get('score',0)}分（{s.get('grade','')}级）"
            )
            lines.append(
                f"  板块：{s.get('sector','')} "
                f"| 涨跌：{s.get('changePct',0):+.2f}% "
                f"| 收缩率={s.get('squeezeRatio',0):.1f}% "
                f"| 带宽={s.get('bbWidthPct',0):.2f}% "
                f"| 量比={s.get('volumeRatio',0):.2f} "
                f"| CMF={s.get('cmf',0):.3f} "
                f"| RSV={s.get('rsv',0):.1f}"
            )
            if s.get('isLeader'):
                lines.append(f"  [中军#{s.get('leaderRank',0)}]")
            lines.append("")

    if other:
        lines.append("## 创业板/科创板")
        for i, s in enumerate(other, 1):
            lines.append(
                f"- {s.get('name','')}({s.get('code','')}) "
                f"{s.get('score',0)}分（{s.get('grade','')}级）"
                f" | {s.get('sector','')}"
            )

    return "\n".join(lines)


def format_holdings_for_prompt(holdings: List[Dict]) -> str:
    """将历史持仓格式化为 Prompt 中可读的文本，用于对比分析。"""
    if not holdings:
        return "【暂无历史持仓数据】"

    lines = [f"当前持仓共 {len(holdings)} 只：\n"]
    for i, h in enumerate(holdings, 1):
        pl_pct = h.get('profit_loss_pct', 0) or 0
        pl_amt = h.get('profit_loss_amount', 0) or 0
        sector = h.get('sector', '') or '未知板块'
        avg_cost = h.get('avg_cost', 0) or 0
        cur_price = h.get('current_price', 0) or 0
        hold_days = h.get('hold_days', 0) or 0
        ratio = h.get('position_ratio', 0) or 0

        pl_icon = '🔴' if pl_pct < 0 else '🟢'
        lines.append(
            f"{pl_icon}【持仓{i}】{h.get('stock_name','')}({h.get('stock_code','')}) "
            f"| 盈亏：{pl_pct:+.2f}%（{pl_amt:+.2f}元）"
        )
        lines.append(
            f"  持仓占比={ratio:.1f}% | 成本={avg_cost:.3f} "
            f"| 现价={cur_price:.3f} | 持有={hold_days}天"
            f" | 板块={sector}"
        )
        lines.append("")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# AI 增强（统一使用 utils.llm 模块）
# ─────────────────────────────────────────────────────────────────────────────

def enhance_with_ai(candidates: List[Dict], news: List[Dict],
                    current_time: str) -> Optional[Dict]:
    """
    使用统一 LLM 模块增强扫描结果。

    流程：
    1. 格式化扫描数据 + 新闻 + 持仓
    2. 通过 AgentRegistry 构建 messages
    3. 通过 LLMClient 调用 LLM
    4. 通过 AgentRegistry 解析 JSON 并清洗输出
    5. 持久化分析历史

    返回结构化结果（对齐 AgentOutput）。
    """
    from utils.llm import get_client, get_agent_registry

    registry = get_agent_registry()
    client = get_client()
    agent = registry.get('jun')

    if not agent:
        logger.warning("未找到 jun agent 配置")
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

    # 构建 messages 并调用 LLM（通过统一客户端）
    messages = registry.build_messages(
        agent_id='jun',
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
        "[JUN-AI] raw_response_len=%d tokens=%d content_preview=%.100s...",
        len(resp.content), resp.tokens_used, resp.content[:100]
    )

    # 解析 JSON
    parsed = registry.extract_json(resp.content)

    if parsed:
        logger.info("[JUN-AI] parsed stance=%s confidence=%s recommendedStocks_count=%d",
                    parsed.get('stance'), parsed.get('confidence'),
                    len(parsed.get('recommendedStocks') or []))
        parsed = registry.sanitize(
            parsed,
            candidates,
            default_advise_type=agent.get('adviseType', '低吸'),
        )
        logger.info("[JUN-AI] after_sanitize recommendedStocks_count=%d",
                    len(parsed.get('recommendedStocks') or []))
    else:
        logger.warning("[JUN-AI] JSON 解析失败，raw 前200字: %.200s", resp.content[:200])

    # 构建推荐股列表（确保数据格式一致，0 值不被误判为无效）
    recommended = []
    for s in (parsed.get('recommendedStocks') or [])[:3]:
        code = s.get('code', '')
        src = next((c for c in candidates if c.get('code') == code), {})
        recommended.append({
            'code': s.get('code', '') or src.get('code', ''),
            'name': s.get('name', '') or src.get('name', ''),
            'sector': s.get('sector', '') or src.get('sector', ''),
            # 使用 if is not None 判断，保留 0 这样的有效值
            'price': s.get('price') if s.get('price') is not None else src.get('price', 0),
            'changePct': s.get('changePct') if s.get('changePct') is not None else src.get('changePct', 0),
            'score': s.get('score') if s.get('score') is not None else src.get('score', 0),
            'grade': s.get('grade', '') or src.get('grade', ''),
            'buyRange': s.get('buyRange', '') or src.get('buyRange', ''),
            'stopLoss': s.get('stopLoss', '') or src.get('stopLoss', ''),
            'targetPrice': s.get('targetPrice', ''),
            'holdPeriod': s.get('holdPeriod', ''),
            'positionRatio': s.get('positionRatio', ''),
            'signal': s.get('signal', ''),
            'riskLevel': s.get('riskLevel', ''),
            'safetyMargin': s.get('safetyMargin', ''),
            'valuation': s.get('valuation', ''),
            'adviseType': s.get('adviseType', '低吸'),
            'meta': s.get('meta', ''),
        })

    # 持久化分析历史（Agent+日期唯一，历史锁定）
    try:
        import database as _db
        report_date = current_time[:10] if current_time else ""
        if parsed:
            analysis_payload = {
                'agentId': parsed.get('agentId', 'jun'),
                'agentName': parsed.get('agentName', agent['name']),
                'stance': parsed.get('stance', 'neutral'),
                'confidence': int(parsed.get('confidence', 50)),
                'marketCommentary': str(parsed.get('marketCommentary', '')),
                'positionAdvice': str(parsed.get('positionAdvice', '')),
                'riskWarning': str(parsed.get('riskWarning', '')),
                'recommendedStocks': recommended,
            }
            # 快照优先级：AI推荐 > DB持仓（与 app.py 保持一致）
            snap = _db.build_analysis_holdings_snapshot(holdings_list, analysis_payload)
            _db.save_agent_analysis_history(
                agent_id='jun',
                report_date=report_date,
                holdings_snapshot=snap,
                analysis_result=analysis_payload,
                raw_response=resp.content,
                stance=parsed.get('stance', 'neutral'),
                confidence=int(parsed.get('confidence', 50)),
                tokens_used=resp.tokens_used,
            )
        else:
            # JSON 解析失败，保存原始文本
            snap_fail = _db.snapshot_rows_from_db_holdings(holdings_list)
            _db.save_agent_analysis_history(
                agent_id='jun',
                report_date=report_date,
                holdings_snapshot=snap_fail,
                analysis_result={'raw_text': resp.content},
                raw_response=resp.content,
                tokens_used=resp.tokens_used,
            )
        logger.info(f"[JUN-AI] 历史已写入 agent_analysis_history agent=jun date={report_date}")

        # 同步推荐股票到持仓表（与 /api/agents/analyze/jun 保持一致）
        if recommended:
            try:
                import database as _db
                saved = _db.save_recommended_stocks_as_holdings('jun', recommended)
                logger.info(f"[JUN-AI] 推荐股票已写入 holdings 表，共 {saved} 条")
            except Exception as sync_err:
                logger.warning(f"[JUN-AI] 同步推荐股票到持仓表失败: {sync_err}")

    except Exception as hist_err:
        logger.warning(f"[JUN-AI] 保存分析历史失败: {hist_err}")

    if not parsed:
        return {
            'agentId': 'jun',
            'agentName': agent['name'],
            'success': True,
            'raw_response': resp.content,
            'structured': None,
            'analysis': resp.content,
            'tokens_used': resp.tokens_used,
        }

    return {
        'agentId': parsed.get('agentId', 'jun'),
        'agentName': parsed.get('agentName', agent['name']),
        'success': True,
        'raw_response': resp.content,
        'structured': {
            'agentId': parsed.get('agentId', 'jun'),
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
    """从 structured JSON 生成自然语言分析报告文本。"""
    stance_label = {'bull': '看多', 'bear': '看空', 'neutral': '中性'}.get(
        parsed.get('stance', 'neutral'), '中性')
    confidence = parsed.get('confidence', 0)
    commentary = parsed.get('marketCommentary', '暂无市场简评。')
    position = parsed.get('positionAdvice', '')
    risk = parsed.get('riskWarning', '')
    agent_name = parsed.get('agentName', '策略分析师')

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
        lines.append(f"【重点个股】")
        grade_icon = {'S': '⭐', 'A': 'A', 'B': 'B', 'C': 'C'}
        for i, st in enumerate(recommended, 1):
            grade = st.get('grade', 'C')
            icon = grade_icon.get(grade, '')
            name = st.get('name', '未知')
            code = st.get('code', '')
            sector = st.get('sector', '')
            price = st.get('price', 0)
            change = st.get('changePct', 0)
            score = st.get('score', 0)
            buy_range = st.get('buyRange', '—')
            stop = st.get('stopLoss', '—')
            advise = st.get('adviseType', '')
            signal = st.get('signal', '')
            target = st.get('targetPrice', '')
            period = st.get('holdPeriod', '')

            lines.append(
                f"{i}. **{name}**（{code}）{icon}级 | {sector} | 现价{price}元 "
                f"({'+' if change >= 0 else ''}{change}%）"
            )
            detail_parts = []
            if buy_range and buy_range != '—':
                detail_parts.append(f"低吸区间：{buy_range}")
            if stop and stop != '—':
                detail_parts.append(f"止损：{stop}")
            if target:
                detail_parts.append(f"目标：{target}")
            if period:
                detail_parts.append(f"周期：{period}")
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

class JunGeTrader:
    """
    钧哥智能交易员 - 主控制器

    负责协调整个扫描流程：
    1. 获取大盘环境
    2. 获取热点板块
    3. 按板块扫描
    4. 汇总排序
    5. AI 增强（可选）
    6. 生成建议
    """

    def __init__(self, api_key: str = None, use_ai: bool = True):
        self.fetcher = DataFetcher()
        self.validator = DataValidator()
        self.scanner = JunGeScanner(self.fetcher, self.validator)
        self.use_ai = use_ai

        self.last_scan_time: Optional[datetime] = None
        self.last_hot_sectors: List[Dict] = []
        self.last_results: List[Dict] = []
        self.last_ai_result: Optional[Dict] = None

    def get_market_condition(self) -> Dict:
        """获取市场环境判断"""
        index_data = self.fetcher.get_market_index()
        condition = self.validator.validate_market_condition(index_data)

        logger.info(f"市场环境: {condition['status']} (平均涨跌: {condition.get('avgChange', 0):+.2f}%)")

        return {
            'indexData': index_data,
            'condition': condition,
            'timestamp': datetime.now().isoformat(),
        }

    def get_hot_sectors(self, top_n: int = 5) -> List[Dict]:
        """动态获取热点板块（失败返回空列表）"""
        try:
            sectors = self.fetcher.get_hot_sectors(top_n)
            if not sectors:
                logger.warning("热点板块为空，尝试降级...")
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

    def run_daily_scan(self, top_sectors: int = 5, enhance: bool = None) -> Dict:
        """
        执行每日扫描

        Args:
            top_sectors: 扫描前N个热点板块
            enhance: 是否启用 AI 增强（默认继承 self.use_ai）

        Returns:
            扫描结果字典
        """
        start_time = datetime.now()
        enhance = enhance if enhance is not None else self.use_ai

        logger.info("=" * 60)
        logger.info("🔥 钧哥每日扫描开始")
        logger.info("=" * 60)

        # 1. 市场环境
        market = self.get_market_condition()

        # 2. 热点板块
        hot_sectors = self.get_hot_sectors(top_sectors)

        if not hot_sectors:
            logger.warning("热点板块为空，转为全市场扫描")
            candidates = self.scanner.scan_all_stocks()
            scan_mode = 'fallback'
        else:
            candidates = []
            scan_mode = 'hot_sectors'

            for sector in hot_sectors:
                logger.info(f"🔍 扫描板块: {sector['name']} ({sector.get('change', 0):+.2f}%)")

                sector_results = self.scanner.scan_by_sector(sector)

                if sector_results:
                    logger.info(f"  ✅ {sector['name']}: {len(sector_results)} 只候选")
                    candidates.extend(sector_results)
                else:
                    logger.info(f"  ⚠️ {sector['name']}: 无候选")

        # 3. 去重 & 排序
        seen = set()
        unique_candidates = []
        for c in candidates:
            if c['code'] not in seen:
                seen.add(c['code'])
                unique_candidates.append(c)

        unique_candidates.sort(key=lambda x: (x['score'], x.get('sectorChange', 0)), reverse=True)

        # 4. 汇总统计
        stats = {
            'totalCandidates': len(unique_candidates),
            'gradeS': sum(1 for c in unique_candidates if c['grade'] == 'S'),
            'gradeA': sum(1 for c in unique_candidates if c['grade'] == 'A'),
            'gradeB': sum(1 for c in unique_candidates if c['grade'] == 'B'),
            'leaders': sum(1 for c in unique_candidates if c.get('isLeader', False)),
        }

        # 5. 精选推荐（扫描层）
        recommendations = self._generate_recommendations(unique_candidates)

        # 6. AI 增强（可选）- 即使扫描数据为空也执行，让 AI 基于市场知识推荐
        ai_result = None
        if enhance:
            logger.info("🤖 启动 AI 增强分析...")
            news = self.get_news()
            ai_result = enhance_with_ai(unique_candidates, news, start_time.isoformat())
            if ai_result:
                self.last_ai_result = ai_result
                logger.info(f"✅ AI 增强完成，tokens={ai_result.get('tokens_used', 0)}")

        # 7. 更新状态
        self.last_scan_time = datetime.now()
        self.last_results = unique_candidates[:10]

        elapsed = (datetime.now() - start_time).total_seconds()

        result = {
            'success': True,
            'scanTime': start_time.isoformat(),
            'elapsedSeconds': round(elapsed, 1),
            'scanMode': scan_mode,

            'market': market,
            'hotSectors': hot_sectors,

            'stats': stats,
            'recommendations': recommendations,
            'candidates': unique_candidates[:20],

            # AI 增强结果（AgentOutput 格式）
            'agentResult': ai_result,

            'summary': self._generate_summary(stats, market, scan_mode),
        }

        logger.info("=" * 60)
        logger.info(f"✅ 扫描完成: {stats['totalCandidates']} 只候选, 耗时 {elapsed:.1f}s")
        logger.info("=" * 60)

        return result

    def _generate_recommendations(self, candidates: List[Dict]) -> List[Dict]:
        """生成精选推荐"""
        recommendations = []

        for c in candidates:
            if c['grade'] in ('S', 'A') or c.get('isLeader', False):
                if len(recommendations) >= 5:
                    break
                recommendations.append({
                    'code': c['code'],
                    'name': c['name'],
                    'grade': c['grade'],
                    'score': c['score'],
                    'sector': c['sector'],
                    'price': c['price'],
                    'changePct': c['changePct'],
                    'buyRange': c['buyRange'],
                    'stopLoss': c['stopLoss'],
                    'tags': c['tags'],
                    'reason': self._generate_reason(c),
                })

        return recommendations

    def _generate_reason(self, stock: Dict) -> str:
        """生成推荐理由"""
        reasons = []

        if '极度收缩' in stock['tags']:
            reasons.append('布林带极度收缩')
        if '放量' in ' '.join(stock['tags']):
            reasons.append('放量启动')
        if '强势流入' in stock['tags']:
            reasons.append('资金强势流入')
        if '超卖' in ' '.join(stock['tags']):
            reasons.append('超卖反弹')
        if stock.get('isLeader'):
            reasons.append('板块中军')

        return ' + '.join(reasons) if reasons else '综合评分优秀'

    def _generate_summary(self, stats: Dict, market: Dict, scan_mode: str) -> str:
        """生成扫描摘要"""
        condition = market['condition']

        return f"""
📊 今日市场: {condition['status']}
🔥 扫描模式: {'热点板块' if scan_mode == 'hot_sectors' else '全市场降级'}
🎯 候选股票: {stats['totalCandidates']} 只

📈 评级分布:
   S级: {stats['gradeS']} 只
   A级: {stats['gradeA']} 只
   B级: {stats['gradeB']} 只

💡 核心策略:
   布林带极度收缩 + 放量 + 资金流入 = 主力蓄力信号
   优先关注板块中军（市值排名前3）
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# Flask API 端点（集成到 strategy_routes.py）
# ─────────────────────────────────────────────────────────────────────────────

def register_junge_routes(bp, get_cache, set_cache, invalidate_cache, db_module):
    """注册 JunGeTrader 相关路由（供 strategy_routes.py 调用）"""

    # 全局 JunGeTrader 实例（延迟初始化）
    _junge_trader = None

    def _trader():
        nonlocal _junge_trader
        if _junge_trader is None:
            _junge_trader = JunGeTrader(use_ai=True)
        return _junge_trader

    from flask import request, jsonify
    import logging as _logger

    @bp.route('/api/junge/market')
    def junge_market():
        try:
            result = _trader().get_market_condition()
            return jsonify({'success': True, 'data': result})
        except Exception as e:
            _logger.error(f"获取市场状态失败: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @bp.route('/api/junge/sectors')
    def junge_sectors():
        try:
            limit = request.args.get('limit', 10, type=int)
            limit = max(1, min(50, limit))
            sectors = _trader().get_hot_sectors(top_n=limit)
            return jsonify({'success': True, 'data': sectors})
        except Exception as e:
            _logger.error(f"获取热点板块失败: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @bp.route('/api/junge/scan', methods=['POST'])
    def junge_scan():
        try:
            data = request.json or {}
            top_sectors = data.get('sectors', 5)
            enhance = data.get('enhance', True)
            force_refresh = data.get('force', False)   # 强制刷新
            top_sectors = max(1, min(20, int(top_sectors)))

            cache_key = _scan_key(top_sectors)

            # 同日同参数直接返回缓存（84秒 → 毫秒级）
            if not force_refresh:
                cached_result = _cache_get(cache_key)
                if cached_result is not None:
                    _logger.info("扫描结果命中缓存 (sectors=%d)，直接返回", top_sectors)
                    return jsonify({'success': True, 'data': cached_result, 'fromCache': True})

            _logger.info("JunGeTrader 扫描开始: sectors=%d, enhance=%s", top_sectors, enhance)

            result = _trader().run_daily_scan(top_sectors=top_sectors, enhance=enhance)

            # 保存扫描记录到 DB
            try:
                scan_id = db_module.create_scan_record({
                    'sectors': top_sectors,
                    'mode': result.get('scanMode', 'hot_sectors'),
                })
                if scan_id and result.get('hotSectors'):
                    db_module.save_hot_sectors(scan_id, result['hotSectors'])
                invalidate_cache('scan/history')
            except Exception as db_err:
                _logger.warning(f"保存扫描记录失败（非致命）: {db_err}")

            # 存入缓存（4h TTL），供同日复用
            _cache_set(cache_key, result, ttl=14400)
            _logger.info("扫描结果已缓存 (key=%s, TTL=4h)", cache_key)

            return jsonify({'success': True, 'data': result})

        except Exception as e:
            _logger.error(f"JunGeTrader 扫描失败: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @bp.route('/api/junge/status')
    def junge_status():
        try:
            trader = _trader()
            return jsonify({
                'success': True,
                'data': {
                    'lastScanTime': trader.last_scan_time.isoformat() if trader.last_scan_time else None,
                    'lastHotSectorsCount': len(trader.last_hot_sectors),
                    'lastResultsCount': len(trader.last_results),
                    'hasAiResult': trader.last_ai_result is not None,
                }
            })
        except Exception as e:
            _logger.error(f"获取 JunGeTrader 状态失败: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @bp.route('/api/junge/cache', methods=['DELETE'])
    def junge_cache_clear():
        """清除 JunGeTrader 所有缓存（用于强制刷新）"""
        try:
            _invalidate_all_junge()
            _logger.info("JunGeTrader 缓存已清除")
            return jsonify({'success': True, 'message': '缓存已清除'})
        except Exception as e:
            _logger.error(f"清除缓存失败: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @bp.route('/api/junge/ai-result')
    def junge_ai_result():
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

    parser = argparse.ArgumentParser(description='钧哥智能交易员')
    parser.add_argument('--sectors', type=int, default=5, help='热点板块数量')
    parser.add_argument('--top', type=int, default=10, help='返回TOP N结果')
    parser.add_argument('--no-ai', action='store_true', help='禁用 AI 增强')

    args = parser.parse_args()

    trader = JunGeTrader(use_ai=not args.no_ai)
    result = trader.run_daily_scan(top_sectors=args.sectors)

    print("\n" + "=" * 60)
    print("📋 精选推荐")
    print("=" * 60)

    for i, rec in enumerate(result['recommendations'][:args.top], 1):
        print(f"\n{i}. {rec['name']} ({rec['code']})")
        print(f"   板块: {rec['sector']} | 等级: {rec['grade']} | 评分: {rec['score']}")
        print(f"   现价: {rec['price']} | 涨跌: {rec['changePct']:+.2f}%")
        print(f"   买入区间: {rec['buyRange']} | 止损: {rec['stopLoss']}")
        print(f"   推荐理由: {rec['reason']}")
        print(f"   标签: {', '.join(rec['tags'])}")

    if result.get('agentResult') and result['agentResult'].get('success'):
        ar = result['agentResult']
        print("\n" + "=" * 60)
        print(f"🤖 AI 增强分析（{ar.get('agentName', '钧哥')}）")
        print("=" * 60)
        s = ar.get('structured', {})
        print(f"立场: {s.get('stance')} | 信心: {s.get('confidence')}%")
        print(f"市场解读: {s.get('marketCommentary')}")
        print(f"策略建议: {s.get('positionAdvice')}")
        print(f"风险提示: {s.get('riskWarning')}")
        for i, st in enumerate(s.get('recommendedStocks', [])[:3], 1):
            print(f"\n{i}. {st.get('name')} ({st.get('code')}) - {st.get('score')}分")
            print(f"   买入区间: {st.get('buyRange')} | 止损: {st.get('stopLoss')}")

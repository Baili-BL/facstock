#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
陈小群智能交易员 - 趋势战法·主升持有
====================================

设计思路：
1. 核心思想：趋势主升 + 回调低吸 + 破位离场
2. 选股标准：趋势龙头 + 容量中军 + 趋势补涨
3. 买点策略：回调低吸、突破加仓、趋势持仓
4. 卖点策略：趋势不破不卖，破了必须走
5. 趋势环境：主升行情重仓，震荡行情谨慎，弱势行情空仓
6. 仓位管理：趋势确认重仓，回调轻仓，破坏时空仓

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
_CACHE_KEY_TREND_ENV = 'chenxiaoqun/trend_env'
_CACHE_KEY_TREND_LEADERS = 'chenxiaoqun/trend_leaders'
_CACHE_KEY_SCAN = 'chenxiaoqun/scan:{date}'

# ─────────────────────────────────────────────────────────────────────────────
# 趋势环境常量
# ─────────────────────────────────────────────────────────────────────────────
TREND_PHASES = {
    'main_up': {'name': '趋势行情', 'description': '主升段', 'position': '重仓持有'},
    'shock': {'name': '震荡行情', 'description': '谨慎操作', 'position': '轻仓试探'},
    'weak': {'name': '弱势行情', 'description': '空仓等待', 'position': '空仓'},
}

# ─────────────────────────────────────────────────────────────────────────────
# 趋势结构常量
# ─────────────────────────────────────────────────────────────────────────────
TREND_STRUCTURES = {
    'main_up': {'name': '主升趋势', 'description': '均线多头排列，持续新高放量'},
    'pullback': {'name': '趋势回调', 'description': '回踩均线，缩量调整'},
    'breakdown': {'name': '趋势破坏', 'description': '跌破均线，放量下跌'},
}

# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────

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


def _invalidate_all_chenxiaoqun():
    _cache_invalidate('chenxiaoqun/')


def _get_ak():
    """Lazy import akshare to avoid py_mini_rader crash."""
    import akshare as _ak
    return _ak


# ─────────────────────────────────────────────────────────────────────────────
# 数据获取器
# ─────────────────────────────────────────────────────────────────────────────

class DataFetcher:
    """
    数据获取器 - 陈小群版
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

    def get_market_indices(self) -> Dict:
        """获取大盘指数"""
        try:
            indices = {}
            # 上证指数
            sh_df = _get_ak().stock_zh_index_spot_em(symbol="000001")
            if sh_df is not None and len(sh_df) > 0:
                indices['上证指数'] = {
                    'code': '000001',
                    'price': float(sh_df.iloc[0].get('最新价', 0)),
                    'change': float(sh_df.iloc[0].get('涨跌幅', 0)),
                }
            
            # 创业板
            cy_df = _get_ak().stock_zh_index_spot_em(symbol="399006")
            if cy_df is not None and len(cy_df) > 0:
                indices['创业板指'] = {
                    'code': '399006',
                    'price': float(cy_df.iloc[0].get('最新价', 0)),
                    'change': float(cy_df.iloc[0].get('涨跌幅', 0)),
                }
            
            return indices
        except Exception as e:
            logger.error(f"获取大盘指数失败: {e}")
            return {}

    def get_hot_sectors(self, top_n: int = 15) -> List[Dict]:
        """获取热点板块"""
        cached = _cache_get(_CACHE_KEY_TREND_LEADERS)
        if cached is not None:
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
                    'turnover': float(row.get('成交额', 0)),
                })

            logger.info(f"陈小群获取到 {len(result)} 个热点板块")
            _cache_set(_CACHE_KEY_TREND_LEADERS, result, ttl=900)
            return result

        except Exception as e:
            logger.error(f"获取热点板块失败: {e}")
            return []

    def get_trend_stocks(self, sector_name: str = '') -> List[Dict]:
        """获取趋势股票（涨幅3%-8%的强势股，非涨停）"""
        try:
            # 获取涨幅靠前的股票（非涨停）
            df = _get_ak().stock_zh_a_spot_em()
            
            if df is None or len(df) == 0:
                return []

            # 筛选条件：涨幅3%-8%，成交额大于5亿
            result = []
            for _, row in df.iterrows():
                change = float(row.get('涨跌幅', 0))
                turnover = float(row.get('成交额', 0))
                
                # 趋势股特征：涨幅3%-8%
                if 3.0 <= change <= 10.0 and turnover > 500000000:
                    result.append({
                        'code': str(row.get('代码', '')),
                        'name': str(row.get('名称', '')),
                        'price': float(row.get('最新价', 0)),
                        'changePct': change,
                        'turnover': turnover,
                        'volumeRatio': float(row.get('量比', 0)),
                        'sector': row.get('行业', '') or sector_name,
                    })

            # 按成交额排序
            result.sort(key=lambda x: x['turnover'], reverse=True)
            return result[:50]

        except Exception as e:
            logger.error(f"获取趋势股票失败: {e}")
            return []

    def get_stock_kline(self, code: str, period: str = 'daily', adjust: str = 'qfq') -> pd.DataFrame:
        """获取股票K线数据"""
        try:
            if code.startswith('6'):
                symbol = f"sh{code}"
            else:
                symbol = f"sz{code}"
            
            df = _get_ak().stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date='20250101',
                end_date=datetime.now().strftime('%Y%m%d'),
                adjust=adjust
            )
            return df
        except Exception as e:
            logger.error(f"获取K线失败 {code}: {e}")
            return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# 趋势分析器
# ─────────────────────────────────────────────────────────────────────────────

class TrendAnalyzer:
    """
    趋势结构分析器
    """

    def __init__(self):
        pass

    def analyze_trend_environment(self, indices_data: Dict) -> Dict:
        """
        分析趋势环境
        """
        trend_score = 0
        reasons = []

        for name, data in indices_data.items():
            change = data.get('change', 0)
            if change >= 1.0:
                trend_score += 2
                reasons.append(f"{name}涨幅{change:.2f}%，强势")
            elif change >= 0:
                trend_score += 1
                reasons.append(f"{name}微涨{change:.2f}%")
            elif change >= -1.0:
                trend_score -= 1
                reasons.append(f"{name}小幅回调{change:.2f}%")
            else:
                trend_score -= 2
                reasons.append(f"{name}下跌{change:.2f}%，偏弱")

        if trend_score >= 3:
            stage = 'main_up'
            action = '趋势行情明确，积极参与主升段'
        elif trend_score >= 0:
            stage = 'shock'
            action = '震荡行情，谨慎操作，回调低吸为主'
        else:
            stage = 'weak'
            action = '弱势行情，控制仓位，等待趋势明朗'

        confidence = min(95, 50 + trend_score * 10)

        return {
            'stage': stage,
            'name': TREND_PHASES[stage]['name'],
            'description': TREND_PHASES[stage]['description'],
            'action': action,
            'positionAdvice': TREND_PHASES[stage]['position'],
            'confidence': confidence,
            'reasons': reasons,
            'trendScore': trend_score,
        }

    def analyze_trend_structure(self, kline_df: pd.DataFrame) -> Dict:
        """
        分析趋势结构
        """
        if kline_df is None or len(kline_df) < 20:
            return {
                'type': 'unknown',
                'name': '数据不足',
                'description': 'K线数据不足',
                'strength': 0,
                'buyOpportunity': False,
            }

        df = kline_df.tail(30).copy()
        
        # 计算均线
        df['ma5'] = df['收盘'].rolling(window=5).mean()
        df['ma10'] = df['收盘'].rolling(window=10).mean()
        df['ma20'] = df['收盘'].rolling(window=20).mean()
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # 判断趋势结构
        current_price = latest['收盘']
        ma5 = latest['ma5']
        ma10 = latest['ma10']
        ma20 = latest['ma20']

        # 主升趋势判断
        if (ma5 > ma10 > ma20 and 
            current_price >= ma5 * 0.98 and
            latest['成交量'] > df['成交量'].rolling(5).mean().iloc[-1] * 1.0):
            structure_type = 'main_up'
            strength = 80 + min(20, (current_price / ma20 - 1) * 100)
            buy_opportunity = False
            risk_level = '中等'
        # 回调判断
        elif (current_price < ma5 and 
              current_price >= ma10 * 0.98 and
              latest['成交量'] < df['成交量'].rolling(5).mean().iloc[-1] * 0.8):
            structure_type = 'pullback'
            strength = 60 + min(20, (ma5 - current_price) / ma5 * 100)
            buy_opportunity = True
            risk_level = '较低'
        # 破坏判断
        elif current_price < ma10 * 0.95:
            structure_type = 'breakdown'
            strength = 30
            buy_opportunity = False
            risk_level = '高风险'
        else:
            structure_type = 'shock'
            strength = 50
            buy_opportunity = False
            risk_level = '中等'

        return {
            'type': structure_type,
            'name': TREND_STRUCTURES[structure_type]['name'],
            'description': TREND_STRUCTURES[structure_type]['description'],
            'strength': int(strength),
            'buyOpportunity': buy_opportunity,
            'riskLevel': risk_level,
            'ma5': round(ma5, 2) if pd.notna(ma5) else 0,
            'ma10': round(ma10, 2) if pd.notna(ma10) else 0,
            'ma20': round(ma20, 2) if pd.notna(ma20) else 0,
            'currentPrice': round(current_price, 2),
        }

    def calculate_trend_score(self, kline_df: pd.DataFrame) -> Dict:
        """
        计算趋势综合评分
        """
        if kline_df is None or len(kline_df) < 20:
            return {'total': 0, 'trend': 0, 'volume': 0, 'momentum': 0}

        df = kline_df.tail(20).copy()
        
        # 趋势得分（均线多头）
        ma5 = df['收盘'].rolling(5).mean()
        ma10 = df['收盘'].rolling(10).mean()
        ma20 = df['收盘'].rolling(20).mean()
        
        trend_score = 0
        if ma5.iloc[-1] > ma10.iloc[-1] > ma20.iloc[-1]:
            trend_score = 40
        elif ma5.iloc[-1] > ma10.iloc[-1]:
            trend_score = 25
        elif ma5.iloc[-1] > ma20.iloc[-1]:
            trend_score = 15
        
        # 动量得分（涨幅）
        gain_5d = (df['收盘'].iloc[-1] / df['收盘'].iloc[-5] - 1) * 100 if len(df) >= 5 else 0
        momentum_score = min(30, max(0, gain_5d * 3))
        
        # 量能得分
        vol_ratio = df['成交量'].iloc[-1] / df['成交量'].rolling(5).mean().iloc[-1]
        volume_score = min(30, vol_ratio * 15)

        total = trend_score + momentum_score + volume_score

        return {
            'total': int(total),
            'trend': trend_score,
            'momentum': int(momentum_score),
            'volume': int(volume_score),
            'gain5d': round(gain_5d, 2),
        }


# ─────────────────────────────────────────────────────────────────────────────
# 陈小群交易员
# ─────────────────────────────────────────────────────────────────────────────

class ChenxiaoqunTrader:
    """
    陈小群智能交易员
    """

    def __init__(self):
        self.fetcher = DataFetcher()
        self.analyzer = TrendAnalyzer()

    def scan_trend_stocks(self) -> Dict:
        """
        扫描趋势股票（核心方法）
        """
        logger.info("陈小群扫描：获取趋势股票...")

        # 1. 获取大盘指数
        indices = self.fetcher.get_market_indices()
        
        # 2. 分析趋势环境
        trend_env = self.analyzer.analyze_trend_environment(indices)
        
        # 3. 获取热点板块
        sectors = self.fetcher.get_hot_sectors(top_n=10)
        
        # 4. 获取趋势股票
        trend_stocks = self.fetcher.get_trend_stocks()
        
        # 5. 分析每只股票的趋势结构
        analyzed_stocks = []
        for stock in trend_stocks[:30]:
            kline = self.fetcher.get_stock_kline(stock['code'])
            structure = self.analyzer.analyze_trend_structure(kline)
            trend_score = self.analyzer.calculate_trend_score(kline)
            
            # 只保留评分较高的股票
            if trend_score['total'] >= 50:
                analyzed_stocks.append({
                    **stock,
                    'structure': structure,
                    'trendScore': trend_score,
                    'score': trend_score['total'],
                })

        # 6. 按评分排序
        analyzed_stocks.sort(key=lambda x: x['score'], reverse=True)
        
        # 7. 生成买点建议
        recommendations = []
        for stock in analyzed_stocks[:10]:
            entry_plan = self._suggest_entry_plan(stock)
            exit_plan = self._suggest_exit_plan(stock)
            recommendations.append({
                **stock,
                'entryPlan': entry_plan,
                'exitPlan': exit_plan,
                'tags': self._generate_tags(stock),
            })

        return {
            'trendEnvironment': trend_env,
            'marketIndices': indices,
            'hotSectors': sectors,
            'trendStocks': analyzed_stocks[:20],
            'recommendations': recommendations,
            'scanTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    def _suggest_entry_plan(self, stock: Dict) -> Dict:
        """建议买点"""
        structure = stock.get('structure', {})
        structure_type = structure.get('type', 'unknown')
        
        if structure_type == 'pullback':
            return {
                'type': '回调低吸',
                'description': '回踩均线缩量，可分批低吸',
                'entryZone': f"{stock['price'] * 0.98:.2f}-{stock['price']:.2f}",
                'confidence': 75,
            }
        elif structure_type == 'main_up':
            return {
                'type': '趋势持有',
                'description': '主升趋势中，耐心持有',
                'entryZone': f"{stock['price'] * 0.99:.2f}-{stock['price'] * 1.01:.2f}",
                'confidence': 80,
            }
        elif structure_type == 'shock':
            return {
                'type': '观望等待',
                'description': '震荡整理，等待方向明确',
                'entryZone': '',
                'confidence': 40,
            }
        else:
            return {
                'type': '不参与',
                'description': '趋势不明，不宜介入',
                'entryZone': '',
                'confidence': 20,
            }

    def _suggest_exit_plan(self, stock: Dict) -> Dict:
        """建议卖点"""
        structure = stock.get('structure', {})
        structure_type = structure.get('type', 'unknown')
        ma5 = structure.get('ma5', stock['price'])
        ma10 = structure.get('ma10', stock['price'])
        
        if structure_type == 'breakdown':
            return {
                'signal': '趋势破坏',
                'urgency': '紧急',
                'description': '跌破均线，必须离场',
                'stopLoss': f"{stock['price'] * 0.92:.2f}",
            }
        elif structure_type == 'pullback':
            return {
                'signal': '回调中',
                'urgency': '观察',
                'description': '若跌破10日线考虑减仓',
                'stopLoss': f"{ma10 * 0.95:.2f}",
            }
        elif structure_type == 'main_up':
            return {
                'signal': '持有',
                'urgency': '耐心',
                'description': '趋势不破不卖，破了必须走',
                'stopLoss': f"{ma5 * 0.97:.2f}",
            }
        else:
            return {
                'signal': '观望',
                'urgency': '等待',
                'description': '等待趋势明朗',
                'stopLoss': '',
            }

    def _generate_tags(self, stock: Dict) -> List[str]:
        """生成标签"""
        tags = []
        structure = stock.get('structure', {})
        structure_type = structure.get('type', 'unknown')
        
        if structure_type == 'main_up':
            tags.append('趋势主升')
            tags.append('可持有')
        elif structure_type == 'pullback':
            tags.append('趋势回调')
            tags.append('低吸机会')
        elif structure_type == 'breakdown':
            tags.append('趋势破坏')
            tags.append('必须离场')
        
        # 成交额标签
        if stock.get('turnover', 0) > 2000000000:
            tags.append('容量中军')
        elif stock.get('turnover', 0) > 500000000:
            tags.append('趋势标的')
        
        return tags


# ─────────────────────────────────────────────────────────────────────────────
# 格式化函数
# ─────────────────────────────────────────────────────────────────────────────

def format_scan_data_for_prompt(scan_result: Dict, max_stocks: int = 15) -> str:
    """
    将扫描结果格式化为 Prompt 中可读的文本。
    """
    if not scan_result:
        return "【暂无扫描数据】"

    trend_env = scan_result.get('trendEnvironment', {})
    stocks = scan_result.get('recommendations', [])
    
    lines = []
    
    # 趋势环境
    lines.append("## 趋势环境判断")
    lines.append(f"当前市场：【{trend_env.get('name', '未知')}】")
    lines.append(f"操作建议：{trend_env.get('action', '')}")
    lines.append(f"仓位建议：{trend_env.get('positionAdvice', '')}")
    lines.append("")

    if not stocks:
        lines.append("【暂无线索趋势股票】")
        return "\n".join(lines)

    lines.append(f"## 趋势股票扫描（共 {len(stocks)} 只，以下为评分 TOP）")
    lines.append("")

    for i, s in enumerate(stocks[:max_stocks], 1):
        structure = s.get('structure', {})
        entry = s.get('entryPlan', {})
        
        lines.append(f"【股票{i}】{s.get('name','')}({s.get('code','')})")
        lines.append(f"  评分：{s.get('score',0)}分 | {structure.get('name','')}")
        lines.append(f"  趋势强度：{s.get('trendScore',{}).get('total',0)}分")
        lines.append(f"  买点：{entry.get('type','')} | {entry.get('description','')}")
        if entry.get('entryZone'):
            lines.append(f"  买入区间：{entry.get('entryZone')}")
        lines.append(f"  标签：{' '.join(s.get('tags',[]))}")
        lines.append("")

    return "\n".join(lines)


def format_holdings_for_prompt(holdings: List[Dict]) -> str:
    """将历史持仓格式化为 Prompt 中可读的文本"""
    if not holdings:
        return "【暂无历史持仓数据】"

    lines = [f"当前持仓共 {len(holdings)} 只：\n"]
    for i, h in enumerate(holdings, 1):
        pl_pct = h.get('profit_loss_pct', 0) or 0
        pl_amt = h.get('profit_loss_amount', 0) or 0
        lines.append(
            f"【持仓{i}】{h.get('stock_name','')}({h.get('stock_code','')}) "
            f"| 盈亏：{pl_pct:+.2f}%（{pl_amt:+.2f}元）"
        )

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# AI 增强
# ─────────────────────────────────────────────────────────────────────────────

def enhance_with_ai(scan_result: Dict, news: List[Dict],
                   current_time: str) -> Optional[Dict]:
    """
    使用统一 LLM 模块增强扫描结果（针对陈小群战法）。
    """
    from utils.llm import get_client, get_agent_registry

    registry = get_agent_registry()
    client = get_client()
    agent = registry.get('chenxiaoqun')

    if not agent:
        logger.warning("未找到 chenxiaoqun agent 配置")
        return None

    # 格式化数据
    scan_text = format_scan_data_for_prompt(scan_result)

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
        agent_id='chenxiaoqun',
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
        "[CHENXIAOQUN-AI] raw_response_len=%d tokens=%d",
        len(resp.content), resp.tokens_used
    )

    # 解析 JSON
    parsed = registry.extract_json(resp.content)

    if parsed:
        logger.info("[CHENXIAOQUN-AI] parsed stance=%s confidence=%s recommendedStocks_count=%d",
                    parsed.get('stance'), parsed.get('confidence'),
                    len(parsed.get('recommendedStocks') or []))
        parsed = registry.sanitize(
            parsed,
            scan_result.get('recommendations', []),
            default_advise_type='趋势持有',
        )

    # 构建推荐股列表
    recommended = []
    for s in (parsed.get('recommendedStocks') or [])[:3]:
        code = s.get('code', '')
        src = next((c for c in scan_result.get('recommendations', []) if c.get('code') == code), {})
        recommended.append({
            'code': s.get('code', '') or src.get('code', ''),
            'name': s.get('name', '') or src.get('name', ''),
            'price': s.get('price') if s.get('price') is not None else src.get('price', 0),
            'changePct': s.get('changePct') if s.get('changePct') is not None else src.get('changePct', 0),
            'score': s.get('score') if s.get('score') is not None else src.get('score', 0),
            'structure': s.get('structure') or src.get('structure', {}),
            'entryPlan': s.get('entryPlan') or src.get('entryPlan', {}),
            'exitPlan': s.get('exitPlan') or src.get('exitPlan', {}),
            'tags': s.get('tags') or src.get('tags', []),
            'signal': s.get('signal', ''),
            'riskLevel': s.get('riskLevel', ''),
            'adviseType': s.get('adviseType', '趋势持有'),
            'meta': s.get('meta', ''),
        })

    # 持久化分析历史
    try:
        import database as _db
        report_date = current_time[:10] if current_time else ""
        if parsed:
            analysis_payload = {
                'agentId': parsed.get('agentId', 'chenxiaoqun'),
                'agentName': parsed.get('agentName', agent['name']),
                'stance': parsed.get('stance', 'neutral'),
                'confidence': int(parsed.get('confidence', 50)),
                'marketCommentary': str(parsed.get('marketCommentary', '')),
                'positionAdvice': str(parsed.get('positionAdvice', '')),
                'riskWarning': str(parsed.get('riskWarning', '')),
                'recommendedStocks': recommended,
                'trendEnvironment': scan_result.get('trendEnvironment', {}),
            }
            _db.save_agent_analysis(report_date, analysis_payload)
    except Exception as e:
        logger.warning(f"保存分析历史失败: {e}")

    return {
        'success': True,
        'structured': parsed,
        'recommendedStocks': recommended,
        'confidence': parsed.get('confidence', 50) if parsed else 50,
        'stance': parsed.get('stance', 'neutral') if parsed else 'neutral',
        'marketCommentary': parsed.get('marketCommentary', '') if parsed else '',
        'positionAdvice': parsed.get('positionAdvice', '') if parsed else '',
        'riskWarning': parsed.get('riskWarning', '') if parsed else '',
    }


# ─────────────────────────────────────────────────────────────────────────────
# 主扫描函数（供 API 调用）
# ─────────────────────────────────────────────────────────────────────────────

def run_trend_scan() -> Dict:
    """
    执行趋势扫描（主入口）
    """
    trader = ChenxiaoqunTrader()
    return trader.scan_trend_stocks()


def run_full_analysis() -> Dict:
    """
    执行完整分析（含AI增强）
    """
    trader = ChenxiaoqunTrader()
    
    # 基础扫描
    scan_result = trader.scan_trend_stocks()
    
    # 获取新闻
    try:
        from ai_service import fetch_market_news
        news = fetch_market_news()
    except Exception:
        news = []
    
    current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')
    
    # AI 增强
    ai_result = enhance_with_ai(scan_result, news, current_time)
    
    return {
        'scanResult': scan_result,
        'aiResult': ai_result,
        'timestamp': current_time,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Flask API 端点
# ─────────────────────────────────────────────────────────────────────────────

def register_chenxiaoqun_routes(bp, get_cache, set_cache, invalidate_cache, db_module):
    """注册 ChenxiaoqunTrader 相关路由"""

    _chenxiaoqun_trader = None

    def _trader():
        nonlocal _chenxiaoqun_trader
        if _chenxiaoqun_trader is None:
            _chenxiaoqun_trader = ChenxiaoqunTrader()
        return _chenxiaoqun_trader

    from flask import request, jsonify
    import logging as _logger

    @bp.route('/api/chenxiaoqun/market')
    def chenxiaoqun_market():
        """获取市场状态"""
        try:
            indices = _trader().fetcher.get_market_indices()
            return jsonify({'success': True, 'data': indices})
        except Exception as e:
            _logger.error(f"获取市场状态失败: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @bp.route('/api/chenxiaoqun/sectors')
    def chenxiaoqun_sectors():
        """获取热点板块"""
        try:
            limit = request.args.get('limit', 10, type=int)
            limit = max(1, min(50, limit))
            sectors = _trader().fetcher.get_hot_sectors(top_n=limit)
            return jsonify({'success': True, 'data': sectors})
        except Exception as e:
            _logger.error(f"获取热点板块失败: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @bp.route('/api/chenxiaoqun/scan', methods=['POST'])
    def chenxiaoqun_scan():
        """执行趋势扫描"""
        try:
            data = request.json or {}
            enhance = data.get('enhance', True)
            force_refresh = data.get('force', False)

            cache_key = f'chenxiaoqun/scan:{datetime.now().strftime("%Y-%m-%d")}'

            # 同日直接返回缓存
            if not force_refresh:
                cached_result = get_cache(cache_key)
                if cached_result is not None:
                    _logger.info("陈小群扫描结果命中缓存，直接返回")
                    return jsonify({'success': True, 'data': cached_result, 'fromCache': True})

            _logger.info("陈小群扫描开始: enhance=%s", enhance)

            # 基础扫描
            scan_result = _trader().scan_trend_stocks()

            # AI 增强（可选）
            ai_result = None
            if enhance:
                try:
                    from ai_service import fetch_market_news
                    news = fetch_market_news()
                    current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')
                    ai_result = enhance_with_ai(scan_result, news, current_time)
                except Exception as ai_err:
                    _logger.warning(f"AI 增强失败: {ai_err}")

            result = {
                'scanResult': scan_result,
                'aiResult': ai_result,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }

            # 存入缓存（4h TTL）
            set_cache(cache_key, result, ttl=14400)
            _logger.info("陈小群扫描结果已缓存")

            return jsonify({'success': True, 'data': result})

        except Exception as e:
            _logger.error(f"陈小群扫描失败: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @bp.route('/api/chenxiaoqun/status')
    def chenxiaoqun_status():
        """获取扫描状态"""
        try:
            cache_key = f'chenxiaoqun/scan:{datetime.now().strftime("%Y-%m-%d")}'
            cached = get_cache(cache_key)
            return jsonify({
                'success': True,
                'data': {
                    'lastScanTime': cached.get('timestamp') if cached else None,
                    'hasResult': cached is not None,
                    'trendEnvironment': cached.get('scanResult', {}).get('trendEnvironment') if cached else None,
                }
            })
        except Exception as e:
            _logger.error(f"获取状态失败: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @bp.route('/api/chenxiaoqun/ai-result')
    def chenxiaoqun_ai_result():
        """获取最近一次 AI 增强分析结果"""
        try:
            cache_key = f'chenxiaoqun/scan:{datetime.now().strftime("%Y-%m-%d")}'
            cached = get_cache(cache_key)
            ai_result = cached.get('aiResult') if cached else None
            return jsonify({'success': True, 'data': ai_result})
        except Exception as e:
            _logger.error(f"获取 AI 结果失败: {e}")
            return jsonify({'success': False, 'error': str(e)})

    _logger.info("ChenxiaoqunTrader 路由注册完成")

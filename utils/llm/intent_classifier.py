"""
数据源意图识别器
================

根据用户输入，识别需要哪些数据源：
1. Qwen（同花顺）- 结果/统计类数据（涨停、热门板块、资金流向等）
2. AKShare - 日线/分钟线级别数据

意图类型：
- INTENT_THEMATIC: 题材/热点分析 → Qwen
- INTENT_TECHNICAL: 技术分析 → AKShare（日线/分钟线）
- INTENT_BOTH: 综合分析 → Qwen + AKShare
- INTENT_NEWS: 新闻/事件分析 → Web Search
- INTENT_FULL: 全面分析 → 全部数据源
"""

from enum import Enum
from typing import List, Dict, Optional, Set
import re


class DataIntent(Enum):
    """数据意图类型"""
    # 单一意图
    THEMATIC = "thematic"           # 题材热点（涨停、连板、热门板块）
    TECHNICAL = "technical"         # 技术分析（日线、分钟线）
    NEWS = "news"                   # 新闻事件
    HOLDINGS = "holdings"          # 持仓分析
    QUANTITATIVE = "quantitative"   # 量化分析

    # 复合意图
    COMPREHENSIVE = "comprehensive"  # 全面分析
    THEME_TECH = "theme_tech"        # 题材+技术


# 关键词映射
THEMATIC_KEYWORDS = {
    '涨停', '连板', '跌停', '炸板', '强势股', '热门板块',
    '热点', '题材', '概念', '龙头', '龙头股',
    '板块涨跌', '资金流向', '主力资金', '北向资金',
    '打板', '首板', '二板', '三板', '空间板',
    '情绪', '赚钱效应', '亏钱效应', '短线',
    '游资', '柚子', '庄股', '筹码', '换手',
}

TECHNICAL_KEYWORDS = {
    'K线', 'k线', '均线', 'MA', 'MACD', 'KDJ', '布林带',
    '日线', '周线', '月线', '分钟', '5分钟', '15分钟', '30分钟', '60分钟',
    '突破', '回踩', '支撑', '压力', '阻力',
    '趋势', '上升趋势', '下降趋势', '横盘',
    '金叉', '死叉', '背离', '放量', '缩量',
    '走势', '行情', '收盘', '开盘', '最高', '最低',
    '成交量', '成交额', '量比', '换手率',
    '技术分析', '形态', '头肩顶', '头肩底', '双重底',
}

NEWS_KEYWORDS = {
    '新闻', '公告', '政策', '消息', '事件',
    '财报', '业绩', '分红', '送股', '配股',
    '重组', '并购', 'ipo', '上市', '退市',
    '制裁', '禁令', '调查', '问询',
}


# 同花顺/Qwen 可提供的数据类型
QWEN_DATA_TYPES = {
    'limit_up': THEMATIC_KEYWORDS,           # 涨停数据
    'hot_sectors': THEMATIC_KEYWORDS,         # 热门板块
    'capital_flow': THEMATIC_KEYWORDS,         # 资金流向
    'news_events': NEWS_KEYWORDS,             # 新闻事件
    'market_sentiment': THEMATIC_KEYWORDS,    # 市场情绪
}

# AKShare 可提供的数据类型
AKSHARE_DATA_TYPES = {
    'daily_kline': TECHNICAL_KEYWORDS,        # 日K线
    'minute_kline': TECHNICAL_KEYWORDS,        # 分钟K线
    'realtime_quote': TECHNICAL_KEYWORDS,       # 实时行情
    'stock_profile': {},                        # 基本面
}


class IntentClassifier:
    """意图分类器"""

    def __init__(self):
        self.thematic_keywords = THEMATIC_KEYWORDS
        self.technical_keywords = TECHNICAL_KEYWORDS
        self.news_keywords = NEWS_KEYWORDS

    def classify(self, user_input: str) -> Dict:
        """
        分析用户输入，返回需要的数据源

        Returns:
            {
                'intent': DataIntent,
                'primary_source': 'qwen' | 'akshare' | 'both',
                'secondary_sources': [],
                'required_tools': ['get_limit_up_stocks', 'get_daily_kline', ...],
                'confidence': 0.0-1.0,
                'reasoning': str
            }
        """
        text = user_input.lower()

        # 计算各意图的得分
        thematic_score = self._calc_score(text, self.thematic_keywords)
        technical_score = self._calc_score(text, self.technical_keywords)
        news_score = self._calc_score(text, self.news_keywords)

        # 意图组合判断
        if thematic_score > 0 and technical_score > 0:
            intent = DataIntent.THEME_TECH
            primary = 'both'
        elif thematic_score >= technical_score and thematic_score >= news_score:
            intent = DataIntent.THEMATIC
            primary = 'qwen'
        elif technical_score > 0:
            intent = DataIntent.TECHNICAL
            primary = 'akshare'
        elif news_score > 0:
            intent = DataIntent.NEWS
            primary = 'web'
        else:
            # 默认全面分析
            intent = DataIntent.COMPREHENSIVE
            primary = 'both'

        # 确定需要调用的工具
        tools = self._determine_tools(intent)

        # 计算置信度
        max_score = max(thematic_score, technical_score, news_score)
        confidence = min(max_score / 3.0, 1.0) if max_score > 0 else 0.5

        return {
            'intent': intent,
            'primary_source': primary,
            'thematic_score': thematic_score,
            'technical_score': technical_score,
            'news_score': news_score,
            'required_tools': tools,
            'confidence': confidence,
            'reasoning': self._generate_reasoning(intent, thematic_score, technical_score, news_score)
        }

    def _calc_score(self, text: str, keywords: Set[str]) -> int:
        """计算关键词匹配得分"""
        score = 0
        for kw in keywords:
            if kw in text:
                score += 1
        return score

    def _determine_tools(self, intent: DataIntent) -> List[str]:
        """根据意图确定需要的工具"""
        tool_map = {
            DataIntent.THEMATIC: ['get_limit_up_stocks', 'get_hot_sectors', 'get_market_sentiment'],
            DataIntent.TECHNICAL: ['get_daily_kline', 'get_minute_kline', 'get_realtime_quote'],
            DataIntent.THEME_TECH: [
                'get_limit_up_stocks', 'get_hot_sectors',
                'get_daily_kline', 'get_minute_kline'
            ],
            DataIntent.COMPREHENSIVE: [
                'get_limit_up_stocks', 'get_hot_sectors', 'get_market_sentiment',
                'get_daily_kline', 'get_minute_kline', 'web_search'
            ],
            DataIntent.NEWS: ['web_search', 'get_news_events'],
            DataIntent.HOLDINGS: ['get_portfolio_analysis'],
            DataIntent.QUANTITATIVE: ['get_quant_signals'],
        }
        return tool_map.get(intent, [])

    def _generate_reasoning(self, intent: DataIntent, thematic: int, technical: int, news: int) -> str:
        """生成推理说明"""
        parts = []
        if thematic > 0:
            parts.append(f"题材分析需求(强度:{thematic})")
        if technical > 0:
            parts.append(f"技术分析需求(强度:{technical})")
        if news > 0:
            parts.append(f"新闻事件需求(强度:{news})")

        if not parts:
            return "无明确意图，执行全面分析"

        return " + ".join(parts)


# 全局实例
_classifier = None

def get_intent_classifier() -> IntentClassifier:
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier


def classify_intent(user_input: str) -> Dict:
    """便捷函数：快速分类用户意图"""
    return get_intent_classifier().classify(user_input)

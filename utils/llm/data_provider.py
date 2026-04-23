"""
数据获取层 v2
=============

Qwen（同花顺数据）→ 通过 Prompt 生成数据
AKShare → 获取日线/分钟线数据

核心设计：
- Qwen: 使用 Prompt 直接生成市场数据（新闻、资金流向、涨停分析等）
- AKShare: 获取技术行情数据
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DataSourceResult:
    """数据源返回结果"""
    source: str
    data_type: str
    data: Any
    success: bool
    error: str = ""
    timestamp: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# Qwen 数据源 - 通过 Prompt 获取数据
# ══════════════════════════════════════════════════════════════════════════════


class QwenDataSource:
    """
    Qwen 数据源

    通过 enable_search=True 联网搜索获取真实市场数据：
    - 市场新闻（S/A/B级题材）
    - 板块资金流向
    - 涨停/连板分析
    - 市场情绪
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.model = "qwen-plus"

    def _get_api_key(self) -> str:
        """获取 API Key"""
        import os
        if self.api_key:
            return self.api_key
        # 从环境变量获取
        return os.environ.get('DASHSCOPE_API_KEY', '') or os.environ.get('QWEN_API_KEY', '')

    def call(self, prompt: str, max_tokens: int = 3000, enable_search: bool = True) -> Dict:
        """
        调用 Qwen API（联网搜索）

        Args:
            prompt: 用户输入
            max_tokens: 最大 token 数
            enable_search: 是否启用联网搜索

        Returns:
            {'content': str, 'success': bool, 'error': str}
        """
        import os

        # 清除代理
        for k in list(os.environ.keys()):
            if 'proxy' in k.lower():
                del os.environ[k]

        api_key = self._get_api_key()
        if not api_key:
            return {'content': '', 'success': False, 'error': '未配置 API Key'}

        try:
            import dashscope

            messages = [
                {'role': 'system', 'content': '你是一位专业的A股财经分析师，专注于题材炒作和事件驱动选股。请基于最新市场数据给出准确分析。'},
                {'role': 'user', 'content': prompt}
            ]

            response = dashscope.Generation.call(
                api_key=api_key,
                model=self.model,
                messages=messages,
                enable_search=enable_search,
                result_format='message',
                max_tokens=max_tokens,
                temperature=0.3,
            )

            if response.status_code == 200:
                content = response.output.choices[0].message.content or ''
                return {'content': content, 'success': True, 'usage': response.usage}
            else:
                error_msg = response.message or f"HTTP {response.status_code}"
                logger.warning(f"[QwenDataSource] API Error: {error_msg}")
                return {'content': '', 'success': False, 'error': error_msg}

        except Exception as e:
            logger.error(f"[QwenDataSource] Error: {e}")
            return {'content': '', 'success': False, 'error': str(e)}


class DataProvider:
    """
    统一数据提供器

    Qwen → 生成市场数据（新闻、资金流向）
    AKShare → 获取技术行情
    """

    def __init__(self):
        self.qwen = None
        self.akshare = AKShareDataSource()
        self._init_qwen()

    def _init_qwen(self):
        """初始化 Qwen"""
        import os
        api_key = os.environ.get('DASHSCOPE_API_KEY', '') or os.environ.get('QWEN_API_KEY', '')
        if api_key:
            self.qwen = QwenDataSource(api_key)
            logger.info("[DataProvider] Qwen 数据源已初始化（联网搜索模式）")
        else:
            logger.warning("[DataProvider] 未配置 Qwen API Key")

    # ─── Qwen 数据获取方法（联网搜索）────────────────────────────────

    def fetch_news_data(self, date_range: str = "今日") -> Dict:
        """
        获取市场新闻数据（S/A/B级题材）

        Qwen 联网搜索获取最新市场数据
        """
        if not self.qwen:
            return {'success': False, 'error': 'Qwen 未初始化'}

        today = datetime.now().strftime('%Y年%m月%d日')

        prompt = f"""请联网搜索并分析今天（{today}）A股市场的重要新闻：

1. **S级题材**：国家政策、顶层设计（最多1条）
2. **A级题材**：部委政策、行业利好（最多2条）
3. **B级题材**：个股公告、业绩公告（最多2条）

请按题材级别排序，输出格式：
|【S级题材】
...（新闻内容）

|【A级题材】
...（新闻内容）

|【B级题材】
...（新闻内容）

如果某级别暂无，写"暂无"。"""

        result = self.qwen.call(prompt, max_tokens=3000, enable_search=True)
        return {
            'success': result.get('success', False),
            'data': result.get('content', ''),
            'error': result.get('error', '')
        }

    def fetch_capital_flow_data(self) -> Dict:
        """
        获取板块资金流向数据

        Qwen 联网搜索获取真实资金流向
        """
        if not self.qwen:
            return {'success': False, 'error': 'Qwen 未初始化'}

        today = datetime.now().strftime('%Y年%m月%d日')

        prompt = f"""请联网搜索今天（{today}）A股板块资金流向数据：

1. 行业板块净流入 TOP5（板块名、净流入金额、涨跌幅）
2. 概念板块净流入 TOP5（概念名、净流入金额、涨跌幅）

请列出具体数据，数据必须真实。"""

        result = self.qwen.call(prompt, max_tokens=2000, enable_search=True)
        return {
            'success': result.get('success', False),
            'data': result.get('content', ''),
            'error': result.get('error', '')
        }

    def fetch_limit_up_analysis(self) -> Dict:
        """
        获取涨停板分析

        Qwen 联网搜索获取真实涨停数据
        """
        if not self.qwen:
            return {'success': False, 'error': 'Qwen 未初始化'}

        today = datetime.now().strftime('%Y年%m月%d日')

        prompt = f"""请联网搜索今天（{today}）A股涨停板数据：

1. 今日涨停家数
2. 重点连板股（股票名称、代码、连板数、涨停原因）
3. 市场空间板
4. 情绪判断（启动/发酵/高潮/退潮）

请列出重点关注标的，数据必须真实。"""

        result = self.qwen.call(prompt, max_tokens=2500, enable_search=True)
        return {
            'success': result.get('success', False),
            'data': result.get('content', ''),
            'error': result.get('error', '')
        }

    def fetch_sentiment_data(self) -> Dict:
        """
        获取市场情绪数据
        """
        if not self.qwen:
            return {'success': False, 'error': 'Qwen 未初始化'}

        today = datetime.now().strftime('%Y年%m月%d日')

        prompt = f"""请联网搜索今天（{today}）A股市场情绪数据：

1. 涨跌停家数（涨停/跌停）
2. 炸板率
3. 昨日涨停今日表现
4. 情绪周期判断（启动/发酵/高潮/退潮/冰点）
5. 赚钱效应（强/中/弱）
6. 亏钱效应（无/局部/扩散）

请基于真实数据给出。"""

        result = self.qwen.call(prompt, max_tokens=1000, enable_search=True)
        return {
            'success': result.get('success', False),
            'data': result.get('content', ''),
            'error': result.get('error', '')
        }

    def fetch_all_data(self) -> Dict:
        """
        获取所有市场数据（综合）
        """
        return {
            'news': self.fetch_news_data(),
            'capital_flow': self.fetch_capital_flow_data(),
            'limit_up': self.fetch_limit_up_analysis(),
            'sentiment': self.fetch_sentiment_data(),
        }

    # ─── AKShare 数据获取方法 ───────────────────────────────────────────

    def fetch_market_snapshot(self) -> Dict:
        """获取市场快照（指数）"""
        try:
            import akshare as ak

            indices = {
                '上证指数': '000001',
                '深证成指': '399001',
                '创业板': '399006',
                '科创50': '000688'
            }

            snapshot = {}
            for name, code in indices.items():
                try:
                    df = ak.stock_zh_index_daily(symbol=f"sh{code}")
                    if df is not None and not df.empty:
                        latest = df.iloc[-1]
                        snapshot[name] = {
                            '最新价': latest.get('close', 0),
                            '涨跌幅': f"{latest.get('pct_change', 0):.2f}%" if 'pct_change' in latest else 'N/A'
                        }
                except:
                    pass

            return {'indices': snapshot}
        except Exception as e:
            logger.error(f"[DataProvider] fetch_market_snapshot error: {e}")
            return {'indices': {}}

    def fetch_technical_data(self, code: str, periods: List[str] = None) -> Dict:
        """获取技术数据"""
        if periods is None:
            periods = ['daily']

        result = {}
        for period in periods:
            if period == 'daily':
                res = self.akshare.get_daily_kline(code)
            elif period.endswith('min'):
                res = self.akshare.get_minute_kline(code, period[:-3])
            else:
                continue

            if res.success:
                result[period] = res.data

        return result


# ══════════════════════════════════════════════════════════════════════════════
# AKShare 数据源
# ══════════════════════════════════════════════════════════════════════════════


class AKShareDataSource:
    """AKShare 数据源 - 获取技术行情数据"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_daily_kline(self, code: str, adjust: str = "qfq") -> DataSourceResult:
        """获取日K线"""
        try:
            import akshare as ak

            # 代码格式转换
            if code.startswith('000') or code.startswith('001'):
                symbol = f"sz{code}"
            elif code.startswith('60'):
                symbol = f"sh{code}"
            else:
                symbol = code

            df = ak.stock_zh_a_hist(symbol=symbol, period="daily",
                                    start_date="20240101", end_date="",
                                    adjust=adjust)

            if df is None or df.empty:
                return DataSourceResult(source='akshare', data_type='daily_kline',
                                       data=None, success=False, error='无数据')

            recent = df.tail(30).to_dict('records')
            return DataSourceResult(source='akshare', data_type='daily_kline',
                                    data={'code': code, 'records': recent, 'count': len(df)},
                                    success=True)

        except Exception as e:
            self.logger.error(f"[AKShare] get_daily_kline error: {e}")
            return DataSourceResult(source='akshare', data_type='daily_kline',
                                   data=None, success=False, error=str(e))

    def get_minute_kline(self, code: str, period: str = "60") -> DataSourceResult:
        """获取分钟K线"""
        try:
            import akshare as ak

            if code.startswith('000') or code.startswith('001'):
                symbol = f"sz{code}"
            elif code.startswith('60'):
                symbol = f"sh{code}"
            else:
                symbol = code

            df = ak.stock_zh_a_hist(symbol=symbol, period=f"{period}min",
                                    start_date="", end_date="", adjust="qfq")

            if df is None or df.empty:
                return DataSourceResult(source='akshare', data_type='minute_kline',
                                       data=None, success=False, error='无数据')

            recent = df.tail(100).to_dict('records')
            return DataSourceResult(source='akshare', data_type='minute_kline',
                                    data={'code': code, 'period': f'{period}min', 'records': recent},
                                    success=True)

        except Exception as e:
            self.logger.error(f"[AKShare] get_minute_kline error: {e}")
            return DataSourceResult(source='akshare', data_type='minute_kline',
                                   data=None, success=False, error=str(e))


# 全局实例
_provider = None

def get_data_provider() -> DataProvider:
    global _provider
    if _provider is None:
        _provider = DataProvider()
    return _provider

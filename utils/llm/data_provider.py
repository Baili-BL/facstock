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
        """获取 API Key，优先百炼，备选 DeepSeek"""
        import os
        if self.api_key:
            return self.api_key
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
        import requests

        # 清除代理
        for k in list(os.environ.keys()):
            if 'proxy' in k.lower():
                del os.environ[k]

        api_key = self._get_api_key()
        if not api_key:
            return {'content': '', 'success': False, 'error': '未配置 API Key'}

        try:
            messages = [
                {'role': 'system', 'content': '你是一位专业的A股财经分析师，专注于题材炒作和事件驱动选股。请基于最新市场数据给出准确分析。'},
                {'role': 'user', 'content': prompt}
            ]

            # 优先使用百炼（Qwen）
            resp = self._call_dashscope(api_key, self.model, messages, max_tokens, enable_search)
            if resp:
                return resp
        except Exception as e:
            logger.warning(f"[QwenDataSource] 百炼调用失败: {e}，尝试 DeepSeek 降级...")

        # 百炼失败，降级尝试 DeepSeek
        import os as _os
        deepseek_key = _os.environ.get('DEEPSEEK_API_KEY', '')
        if deepseek_key:
            try:
                ds_messages = [
                    {'role': 'system', 'content': '你是一位专业的A股财经分析师，专注于题材炒作和事件驱动选股。请基于最新市场数据给出准确分析。'},
                    {'role': 'user', 'content': prompt}
                ]
                resp = self._call_deepseek(deepseek_key, 'deepseek-chat', ds_messages, max_tokens, enable_search)
                if resp:
                    return resp
            except Exception as e2:
                logger.warning(f"[QwenDataSource] DeepSeek 降级也失败: {e2}")

        return {'content': '', 'success': False, 'error': '所有 API 提供商均调用失败'}

    def _call_dashscope(self, api_key: str, model: str, messages: List[Dict], max_tokens: int, enable_search: bool) -> Optional[Dict]:
        """调用百炼 Qwen API"""
        import requests

        for k in list(__import__('os').environ.keys()):
            if 'proxy' in k.lower():
                del __import__('os').environ[k]

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "enable_search": enable_search,
        }

        resp = requests.post(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
            proxies={"http": None, "https": None},
        )
        resp.raise_for_status()
        data = resp.json()

        content = data['choices'][0]['message']['content']
        usage = data.get('usage', {})
        return {'content': content, 'success': True, 'usage': usage}

    def _call_deepseek(self, api_key: str, model: str, messages: List[Dict], max_tokens: int, enable_search: bool) -> Optional[Dict]:
        """调用 DeepSeek API（联网搜索降级）"""
        import requests

        for k in list(__import__('os').environ.keys()):
            if 'proxy' in k.lower():
                del __import__('os').environ[k]

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "extra_body": {
                "thinking": {"type": "enabled"},
                "enable_search": enable_search,
            },
        }

        resp = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
            proxies={"http": None, "https": None},
        )
        resp.raise_for_status()
        data = resp.json()

        content = data['choices'][0]['message']['content'] or ''
        # DeepSeek 可能返回 reasoning_content
        reasoning = data['choices'][0]['message'].get('reasoning_content', '') or ''
        if reasoning:
            content = reasoning + '\n\n' + content
        usage = data.get('usage', {})
        return {'content': content, 'success': True, 'usage': usage}



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

    def fetch_limit_up_pool_via_qwen(self) -> Dict[str, Any]:
        """
        通过 Qwen 联网搜索获取涨停池数据（作为 akshare 的 fallback）

        返回结构兼容 akshare stock_zt_pool_em 返回的字段。
        """
        if not self.qwen:
            return {'success': False, 'error': 'Qwen 未初始化', 'stocks': []}

        today = datetime.now().strftime('%Y年%m月%d日')

        prompt = f"""请联网搜索今天（{today}）A股涨停板数据，严格按照以下格式输出：

1. 首先输出【涨停概览】：今日涨停总家数、昨日涨停今日表现、炸板率、市场情绪周期判断
2. 然后输出【重点涨停股】列表（最多30只），每只股票格式：
股票名称|股票代码|所属行业|换手率|流通市值（亿）|成交额（亿）|首次封板时间|连板数|封板资金（亿）|涨停原因

数据必须真实，搜索同花顺、东方财富、东财Choice等数据源。不要编造数据，如果没有某字段则留空。"""

        result = self.qwen.call(prompt, max_tokens=4000, enable_search=True)
        if not result.get('success'):
            return {'success': False, 'error': result.get('error', 'Qwen 调用失败'), 'stocks': []}

        content = result.get('content', '')

        stocks = []
        import re
        lines = content.split('\n')
        in_list = False
        for line in lines:
            line = line.strip()
            if '重点涨停股' in line or '涨停股' in line or re.match(r'^\d+\.', line):
                in_list = True
                continue
            if in_list and line and not line.startswith('['):
                parts = line.split('|')
                if len(parts) >= 2:
                    name = parts[0].strip()
                    code_match = re.search(r'\d{{6}}', parts[1])
                    if code_match:
                        code = code_match.group()
                        stocks.append({
                            '名称': name,
                            '代码': code,
                            '所属行业': parts[2].strip() if len(parts) > 2 else '',
                            '换手率': parts[3].strip() if len(parts) > 3 else '',
                            '流通市值': parts[4].strip() if len(parts) > 4 else '',
                            '成交额': parts[5].strip() if len(parts) > 5 else '',
                            '首次封板时间': parts[6].strip() if len(parts) > 6 else '',
                            '连板数': parts[7].strip() if len(parts) > 7 else '',
                            '封板资金': parts[8].strip() if len(parts) > 8 else '',
                            '涨停原因': parts[9].strip() if len(parts) > 9 else '',
                            '_qwen_source': True,
                        })

        overview = ''
        if '涨停概览' in content:
            start = content.index('【涨停概览】')
            end = content.index('【重点涨停股】') if '【重点涨停股】' in content else len(content)
            overview = content[start:end].strip()

        return {
            'success': True,
            'overview': overview,
            'stocks': stocks,
            'raw': content,
        }

    def fetch_market_overview_via_qwen(self) -> str:
        """
        通过 Qwen 联网搜索获取市场概览（指数点位），
        作为新浪接口的 fallback。
        """
        if not self.qwen:
            return ''

        prompt = """请联网搜索今日A股三大指数的最新数据：

上证指数、深证成指、创业板指的：
1. 最新点位
2. 涨跌幅
3. 涨跌额

请直接输出数值，不要解释。格式示例：
上证指数: 3300.00 | +0.50 (+0.02%)
深证成指: 11000.00 | -50.00 (-0.45%)
创业板指: 2200.00 | -30.00 (-1.35%)"""

        result = self.qwen.call(prompt, max_tokens=500, enable_search=True)
        if result.get('success'):
            return result.get('content', '')
        return ''

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

"""
AI 分析服务
============

使用统一 LLM 模块（utils.llm）提供 AI 股票分析能力。

核心功能：
- fetch_market_news(): 获取财联社、东方财富等实时新闻
- AIAnalysisService: 封装 AI 分析流程（扫描数据 + 新闻 → LLM → 分析报告）

已消除重复代码：
- API Key / Base URL / Model 配置 → utils.llm.client
- LLM 调用逻辑                   → utils.llm.client.LLMClient
"""

import os
import logging
from datetime import datetime
from typing import Optional

from utils.llm import get_client, CallOptions

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# 领域数据获取（保留，非 LLM 逻辑）
# ══════════════════════════════════════════════════════════════════════════════


def fetch_market_news(scan_date: str = None):
    """
    获取市场新闻和政策消息

    Args:
        scan_date: 扫描日期，格式 YYYY-MM-DD，新闻必须早于或等于此日期
    """
    news_list = []

    if scan_date:
        try:
            scan_dt = datetime.strptime(scan_date[:10], '%Y-%m-%d')
        except Exception:
            scan_dt = datetime.now()
    else:
        scan_dt = datetime.now()

    try:
        import akshare as ak

        def extract_time(row):
            for col in ['发布时间', '时间', 'time', 'datetime', '日期']:
                if col in row.index:
                    val = row[col]
                    if val is not None and str(val).strip():
                        return str(val).strip()
            return datetime.now().strftime('%m-%d %H:%M')

        def extract_content(row):
            for col in ['内容', '标题', 'content', 'title', '新闻内容']:
                if col in row.index:
                    val = row[col]
                    if val is not None and str(val).strip():
                        return str(val).strip()[:120]
            return ''

        # 财联社电报
        try:
            df = ak.stock_telegraph_cls()
            if df is not None and not df.empty:
                for _, row in df.head(8).iterrows():
                    time_str = extract_time(row)
                    title = extract_content(row)
                    if title and len(title) > 5:
                        news_list.append({
                            'time': time_str,
                            'title': title,
                            'source': '财联社'
                        })
        except Exception as e:
            logger.warning(f"获取财联社新闻失败: {e}")

        # 东方财富全球财经快讯
        try:
            df = ak.stock_info_global_em()
            if df is not None and not df.empty:
                for _, row in df.head(8).iterrows():
                    time_str = extract_time(row)
                    title = extract_content(row)
                    if title and len(title) > 5:
                        news_list.append({
                            'time': time_str,
                            'title': title,
                            'source': '东方财富'
                        })
        except Exception as e:
            logger.warning(f"获取东方财富新闻失败: {e}")

        # 同花顺财经新闻
        try:
            df = ak.stock_info_global_ths()
            if df is not None and not df.empty:
                for _, row in df.head(5).iterrows():
                    time_str = extract_time(row)
                    title = extract_content(row)
                    if title and len(title) > 5:
                        news_list.append({
                            'time': time_str,
                            'title': title,
                            'source': '同花顺'
                        })
        except Exception as e:
            logger.warning(f"获取同花顺新闻失败: {e}")

        # 富途资讯
        try:
            df = ak.stock_info_global_futu()
            if df is not None and not df.empty:
                for _, row in df.head(4).iterrows():
                    time_str = extract_time(row)
                    title = extract_content(row)
                    if title and len(title) > 5:
                        news_list.append({
                            'time': time_str,
                            'title': title,
                            'source': '富途资讯'
                        })
        except Exception as e:
            logger.warning(f"获取富途新闻失败: {e}")

    except ImportError:
        logger.warning("akshare 未安装，跳过新闻获取")
    except Exception as e:
        logger.warning(f"获取新闻失败: {e}")

    # 去重（按标题前50字符判断）
    seen_titles = set()
    unique_news = []
    for news in news_list:
        title = news.get('title', '')[:50]
        if title not in seen_titles and len(title) > 5:
            seen_titles.add(title)
            unique_news.append(news)

    return unique_news[:15]


# ══════════════════════════════════════════════════════════════════════════════
# 钧哥低吸策略 Prompt（保留领域特色）
# ══════════════════════════════════════════════════════════════════════════════

JUNGE_STRATEGY_PROMPT = """
你是一位专业的A股技术分析师。请基于下方提供的扫描数据和市场新闻进行分析。

## 重要时间说明
- 股票扫描时间：{current_time}
- 下方新闻均为扫描时间当天或之前的消息
- 分析时请注意：新闻发布时间 ≤ 股票数据更新时间

## 最新市场消息（扫描日期及之前）
{news_data}

## 选股策略：钧哥低吸策略
优先级：政策利好 > 布林带收缩 > 量价配合 > 资金流向（CMF）

### 关键指标解读
- **收缩率**：越高表示布林带越收紧，突破信号越强
- **带宽%**：<5% 表示极度收缩，可能即将突破
- **量比**：>1.5 表示放量，配合收缩更佳
- **CMF**：>0 资金流入，<0 资金流出
- **RSV**：<20 超卖区，>80 超买区

## 扫描结果数据
{scan_data}

## 任务要求
请从上述扫描结果中，结合最新市场消息，筛选 2-3 只股票：

### 筛选条件
1. **必须是主板股票**（代码以 60 或 00 开头）
2. **政策关联**：优先选择与最新政策/新闻相关的板块
3. **评分优先**：优先选择 S级 或 A级
4. **技术形态**：收缩率高 + 带宽低 = 布林带收紧，突破概率大
5. **量价配合**：量比>1 且 CMF>0 更佳

### 输出格式（必须严格按此格式，填入真实数据）

#### 一、今日重点消息
从上方新闻列表中选 2-3 条，原文复制：

1. 【新闻X】「[时间] 新闻内容」（来源）→ 利好板块：xxx

#### 二、精选股票

从上方扫描数据表格中选择 2-3 只主板股票，必须填入真实的股票名称和代码：

**1. [填入股票名称]（[填入6位代码]）** - [填入评分]分（[填入等级]级）
- 所属板块：[填入板块名]
- 📰 关联消息：【新闻X】「[复制新闻原文]」
- 📊 技术数据：收缩率=[填入]% | 带宽=[填入]% | 量比=[填入] | CMF=[填入] | RSV=[填入]
- 💡 买入建议：[低吸策略建议]
- ⚠️ 风险提示：[具体风险]

**2. [填入股票名称]（[填入6位代码]）** - [填入评分]分（[填入等级]级）
- 所属板块：[填入板块名]
- 📰 关联消息：【新闻X】或"无直接关联，纯技术面"
- 📊 技术数据：收缩率=[填入]% | 带宽=[填入]% | 量比=[填入] | CMF=[填入] | RSV=[填入]
- 💡 买入建议：[低吸策略建议]
- ⚠️ 风险提示：[具体风险]

#### 三、整体风险提示
[市场风险说明]

### ⚠️ 严格要求
1. 股票名称和代码必须从扫描数据表格中复制，例如：隆基绿能（601012）
2. 技术数据必须从表格中复制真实数值，不能写"XX"或空着
3. 新闻必须从上方新闻列表原文复制
4. 禁止推荐扫描数据中不存在的股票

## 重要提醒
- 股票必须来自扫描数据，不要推荐数据中没有的股票
- 技术指标数值必须引用扫描数据中的真实数值
- 新闻解读要客观，不要过度解读
"""


# ══════════════════════════════════════════════════════════════════════════════
# AI 分析服务
# ══════════════════════════════════════════════════════════════════════════════


class AIAnalysisService:
    """AI 股票分析服务 — 基于统一 LLM 模块"""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        """懒加载统一 LLM 客户端"""
        if self._client is None:
            self._client = get_client()
        return self._client

    def is_configured(self) -> bool:
        """检查是否已配置"""
        return self.client.is_configured()

    def analyze_stocks(self, scan_data: dict, current_time: str) -> dict:
        """
        分析股票数据

        Args:
            scan_data: 扫描结果数据
            current_time: 当前时间字符串

        Returns:
            分析结果字典
        """
        if not self.is_configured():
            return {
                'success': False,
                'error': 'AI 服务未配置'
            }

        try:
            formatted_data = self._format_scan_data(scan_data)
            scan_date = scan_data.get('scan_time', '')[:10] if scan_data.get('scan_time') else None
            news_data = self._format_news_data(scan_date)

            prompt = JUNGE_STRATEGY_PROMPT.format(
                current_time=current_time,
                news_data=news_data,
                scan_data=formatted_data
            )

            system_prompt = (
                '你是一位严谨的A股技术分析助手。你只能基于用户提供的扫描数据进行分析，'
                '绝对不能编造任何数据中没有的股票、价格、涨幅等信息。如果数据不足，请如实说明。'
            )

            options = CallOptions(
                temperature=0.3,
                max_tokens=2000,
            )

            resp = self.client.call(prompt, system=system_prompt, options=options)

            if not resp.success:
                return {
                    'success': False,
                    'error': f'AI 分析失败: {resp.error}'
                }

            return {
                'success': True,
                'analysis': resp.content,
                'model': f"{resp.provider}/{resp.model}",
                'tokens_used': resp.tokens_used
            }

        except Exception as e:
            logger.error(f"AI 分析异常: {e}")
            return {
                'success': False,
                'error': f'AI 分析失败: {str(e)}'
            }

    def _format_news_data(self, scan_date: str = None) -> str:
        """格式化新闻数据"""
        news_list = fetch_market_news(scan_date)

        if not news_list:
            return "【暂无最新消息】"

        lines = [f"以下是 {scan_date or '今日'} 及之前的真实新闻，引用时必须原文复制：\n"]
        for i, news in enumerate(news_list, 1):
            time_str = news.get('time', '')
            title = news.get('title', '')
            source = news.get('source', '')
            lines.append(f"【新闻{i}】「[{time_str}] {title}」（{source}）")

        lines.append("\n★ 引用规则：必须原文复制「」内的内容，包括时间和标题，禁止改写")

        return "\n".join(lines)

    def _format_scan_data(self, scan_data: dict) -> str:
        """格式化扫描数据为文本"""
        if not scan_data or 'results' not in scan_data:
            return "【无扫描数据】"

        results = scan_data.get('results', [])
        if not results:
            return "【无扫描数据】"

        main_board = [s for s in results if s.get('code', '').startswith(('60', '00'))]
        other = [s for s in results if not s.get('code', '').startswith(('60', '00'))]

        main_board = sorted(main_board, key=lambda x: x.get('total_score', 0), reverse=True)[:15]
        other = sorted(other, key=lambda x: x.get('total_score', 0), reverse=True)[:5]

        lines = [f"共扫描到 {len(results)} 只股票，以下为筛选结果：\n"]

        if main_board:
            lines.append("## 主板股票（请从以下股票中选择推荐）")
            lines.append("")

            for i, stock in enumerate(main_board, 1):
                code = stock.get('code', '')
                name = stock.get('name', '')
                sector = stock.get('sector', '')
                score = stock.get('total_score', 0)
                grade = stock.get('grade', '')
                squeeze_ratio = stock.get('squeeze_ratio', 0)
                bb_width_pct = stock.get('bb_width_pct', 0)
                volume_ratio = stock.get('volume_ratio', 0)
                cmf = stock.get('cmf', 0)
                rsv = stock.get('rsv', 0)

                lines.append(f"【股票{i}】{name}（{code}）- {score}分（{grade}级）")
                lines.append(f"  板块：{sector}")
                lines.append(
                    f"  技术数据：收缩率={squeeze_ratio:.1f}% | 带宽={bb_width_pct:.2f}% "
                    f"| 量比={volume_ratio:.2f} | CMF={cmf:.3f} | RSV={rsv:.1f}"
                )
                lines.append("")

            lines.append("")

        if other:
            lines.append("## 创业板/科创板（仅供参考）")
            for i, stock in enumerate(other, 1):
                code = stock.get('code', '')
                name = stock.get('name', '')
                score = stock.get('total_score', 0)
                lines.append(f"- {name}（{code}）评分{score}分")
            lines.append("")

        lines.append("【注意：请仅从上述主板股票中选择推荐】")

        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# 单例实例
# ══════════════════════════════════════════════════════════════════════════════

_ai_service_instance: Optional[AIAnalysisService] = None


def get_ai_service() -> AIAnalysisService:
    """获取 AI 分析服务单例"""
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIAnalysisService()
    return _ai_service_instance

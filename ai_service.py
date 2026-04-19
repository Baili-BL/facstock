"""
AI 分析服务 - 新闻获取模块
============================

使用统一 LLM 模块（utils.llm）提供 AI 股票分析能力。

核心功能：
- fetch_market_news(): 获取财联社、东方财富等实时新闻
- fetch_junge_enhanced_news(): 钧哥天下无双专用增强新闻获取

已消除重复代码：
- API Key / Base URL / Model 配置 → utils.llm.client
- LLM 调用逻辑                   → utils.llm.client.LLMClient
"""

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# 市场新闻获取
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


def fetch_junge_enhanced_news(scan_date: str = None) -> str:
    """
    钧哥天下无双专用增强新闻获取 - 直接调用 qwen3.6-plus 模型生成新闻和资金流向数据。

    Returns:
        格式化的新闻文本，供注入 Agent Prompt
    """
    import urllib.request
    import json as _json

    today = datetime.now()
    is_monday = today.weekday() == 0
    date_range_desc = "近3天" if is_monday else "今日"

    sections = []

    # ── 直接调用 qwen3.6-plus 生成完整新闻 + 资金流向 ──────────────────────
    try:
        qwen_api_key = os.environ.get('DASHSCOPE_API_KEY', '') or os.environ.get('QWEN_API_KEY', '')
        if not qwen_api_key:
            logger.warning("[JungeNews] 未配置 DASHSCOPE_API_KEY，使用兜底数据")
            sections.append(_build_fallback_news())
            return _finalize_news(sections, is_monday, date_range_desc)

        qwen_prompt = f"""你是【钧哥天下无双】，一位专注于A股题材炒作的顶级游资高手。今天是 {today.strftime('%Y年%m月%d日')}（{date_range_desc}）。

请基于你的市场知识，生成一份对A股市场有重要影响的新闻和板块资金流向分析。

## 新闻部分（按题材级别排序）
1. **S级题材**（国家政策、顶层设计，最多1条）
2. **A级题材**（部委政策、行业利好，最多2条）
3. **B级题材**（个股公告、业绩公告，最多2条）

## 板块资金流向分析
1. 行业板块净流入 TOP5（板块名、净流入估算、涨跌幅）
2. 概念板块净流入 TOP5（概念名、净流入估算、涨跌幅）

## 输出格式：
=== AI整理新闻（钧哥天下无双）===
|【S级题材】
暂无（或：描述具体政策新闻）

|【A级题材】
暂无（或：描述具体行业利好）

|【B级题材】
暂无（或：描述具体个股公告）

=== 板块资金流向 TOP5 ===
|【行业板块净流入TOP5】
  - 板块名: 净流入 X.XX亿 | 涨幅 X.XX%

|【概念板块净流入TOP5】
  - 概念名: 净流入 X.XX亿 | 涨幅 X.XX%

注意：
- 新闻必须真实合理，可以基于近期已知事实
- 资金流向数据基于合理估算
- 如果不确定，写"暂无"
- 不要输出任何解释，直接输出报告"""

        payload = _json.dumps({
            "model": "qwen3.6-plus",
            "instructions": "你是一位专业的A股财经分析师【钧哥天下无双】，专注于题材炒作和事件驱动选股。",
            "input": qwen_prompt,
            "temperature": 0.4,
            "max_output_tokens": 2500,
        }).encode('utf-8')

        req = urllib.request.Request(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/responses",
            data=payload,
            headers={
                "Authorization": f"Bearer {qwen_api_key}",
                "Content-Type": "application/json",
            },
            method='POST',
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            data = _json.loads(resp.read())
            qwen_result = data.get('output', {}).get('text', '')

            if qwen_result:
                sections.append(qwen_result.strip())
                logger.info("[JungeNews] qwen3.6-plus 新闻生成成功，长度=%d", len(qwen_result))
            else:
                logger.warning("[JungeNews] qwen 返回为空，使用兜底数据")
                sections.append(_build_fallback_news())

    except Exception as e:
        logger.warning("[JungeNews] qwen API 调用失败: %s", e)
        sections.append(_build_fallback_news())

    # ── akshare 实时快讯（补充）─────────────────────────────────────────
    akshare_news = fetch_market_news(scan_date)
    if akshare_news:
        lines = ["=== 实时财经快讯（akshare）==="]
        for i, n in enumerate(akshare_news[:10], 1):
            lines.append(f"【快讯{i}】[{n.get('time','')}] {n.get('title','')}（{n.get('source','')}）")
        sections.append("\n".join(lines))

    return _finalize_news(sections, is_monday, date_range_desc)


def _build_fallback_news():
    """构建兜底新闻数据"""
    return """=== AI整理新闻（通义千问）===
|【国际新闻】
暂无重要消息

|【国内政策】
暂无重要消息

|【科技突破】
暂无重要消息

=== 板块资金流向 TOP5 ===
|【行业板块净流入TOP5】
  - 暂无数据（API 未配置或请求失败）

|【概念板块净流入TOP5】
  - 暂无数据（API 未配置或请求失败）
"""


def _finalize_news(sections, is_monday, date_range_desc):
    """整理最终新闻数据"""
    if not sections:
        return "【暂无最新消息】"
    header = f"📅 新闻时间范围：{date_range_desc}（{'周一扩展模式' if is_monday else '日常模式'}）\n"
    return header + "\n\n".join(sections)

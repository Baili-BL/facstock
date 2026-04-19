"""
测试 DataProvider - Playwright 问财爬虫
用法：python test_data_provider.py
"""

import sys
import os

# 确保导入路径正确
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.llm.data_provider import get_data_provider, DataProvider
from datetime import datetime

def test_single_query():
    """单条查询测试"""
    provider = DataProvider()
    print(f"今日日期: {provider.today_full}")
    print(f"今日ISO: {provider.today_date}")
    print("=" * 60)

    # 测试涨停板
    print("\n[1/5] 测试涨停板...")
    r = provider.fetch("limit_up")
    print(f"  success={r.success} error={r.error}")
    if r.success and isinstance(r.data, list):
        print(f"  共 {len(r.data)} 条")
        for row in r.data[:3]:
            print(f"  {row}")
    elif r.success and isinstance(r.data, dict):
        raw = r.data.get("raw_text", "")
        print(f"  降级文本(前200字): {raw[:200]}")

    # 测试板块
    print("\n[2/5] 测试板块涨跌幅...")
    r = provider.fetch("sector")
    print(f"  success={r.success} error={r.error}")
    if r.success and isinstance(r.data, list):
        print(f"  共 {len(r.data)} 条")
        for row in r.data[:3]:
            print(f"  {row}")

    # 测试资金流向
    print("\n[3/5] 测试资金流向...")
    r = provider.fetch("capital_flow")
    print(f"  success={r.success} error={r.error}")
    if r.success and isinstance(r.data, list):
        print(f"  共 {len(r.data)} 条")
        for row in r.data[:3]:
            print(f"  {row}")

    # 测试连板股
    print("\n[4/5] 测试连板股...")
    r = provider.fetch("continuous_board")
    print(f"  success={r.success} error={r.error}")
    if r.success and isinstance(r.data, list):
        print(f"  共 {len(r.data)} 条")
        for row in r.data[:3]:
            print(f"  {row}")

    # 测试跌停
    print("\n[5/5] 测试跌停板...")
    r = provider.fetch("limit_down")
    print(f"  success={r.success} error={r.error}")
    if r.success and isinstance(r.data, list):
        print(f"  共 {len(r.data)} 条")
        for row in r.data[:3]:
            print(f"  {row}")

    provider.close()
    print("\n✅ 单条查询测试完成")


def test_batch():
    """批量查询测试（共享浏览器实例）"""
    provider = DataProvider()
    print(f"\n{'=' * 60}")
    print(f"今日: {provider.today_full}")
    print("[批量查询] 同时请求涨停+板块+资金流向...")

    results = provider.fetch_batch([
        "limit_up", "sector", "capital_flow",
        "continuous_board", "broken_board",
    ])

    for qt, r in results.items():
        if r.success:
            count = len(r.data) if isinstance(r.data, list) else 0
            print(f"  ✅ {qt}: {count} 条")
        else:
            print(f"  ❌ {qt}: {r.error}")

    provider.close()
    print("✅ 批量查询测试完成")


def test_market_snapshot():
    """测试大盘快照（AKShare）"""
    provider = DataProvider()
    print(f"\n{'=' * 60}")
    print("[大盘快照] 获取上证/深证/创业板/科创50...")

    r = provider.akshare.get_market_snapshot()
    if r.success:
        for name, data in r.data.items():
            print(f"  {name}: 收盘={data.get('close')} 涨跌={data.get('pct_change')}%")
    else:
        print(f"  失败: {r.error}")

    print("✅ 大盘快照测试完成")


def test_news_format():
    """测试新闻格式化"""
    provider = DataProvider()
    print(f"\n{'=' * 60}")
    print("[新闻格式化] 从问财数据生成新闻文本...")

    result = provider.fetch_news()
    if result.get('success'):
        print(f"  today: {result.get('today')}")
        print(f"  today_date: {result.get('today_date')}")
        print(f"  news_text:\n{result.get('news_text', '')[:500]}")
    else:
        print(f"  失败")

    provider.close()
    print("✅ 新闻格式化测试完成")


if __name__ == "__main__":
    print("🚀 DataProvider Playwright 问财爬虫测试")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    test_single_query()
    test_batch()
    test_market_snapshot()
    test_news_format()

    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

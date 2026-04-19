"""
极简版测试 - 只验证 Playwright 能否正常工作
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.llm.data_provider import IwenCaiCrawler
from datetime import datetime

def test_browser_launch():
    """测试浏览器启动"""
    print("测试1: 浏览器启动...")
    crawler = IwenCaiCrawler()
    ok = crawler._ensure_browser()
    if ok:
        print("  ✅ 浏览器启动成功")
        # 打开一个简单页面测试
        page = crawler._page
        page.goto("https://www.baidu.com", timeout=15000)
        title = page.title()
        print(f"  ✅ 访问百度成功: {title}")
        crawler.close()
        return True
    else:
        print("  ❌ 浏览器启动失败")
        return False

def test_iwencai_simple():
    """测试问财（单个查询，5秒超时）"""
    print("\n测试2: 访问问财...")
    crawler = IwenCaiCrawler()
    if not crawler._ensure_browser():
        print("  ❌ 浏览器不可用")
        crawler.close()
        return

    page = crawler._page
    try:
        import urllib.parse
        query = urllib.parse.quote("今日涨停股一览")
        url = f"https://www.iwencai.com/unifiedwap/result?w={query}&ie=utf-8&proto=4"
        print(f"  访问: {url}")
        page.goto(url, timeout=20000, wait_until="domcontentloaded")
        print(f"  ✅ 页面加载成功，title: {page.title()[:50]}")
        # 尝试等表格出现
        try:
            page.wait_for_selector("table", timeout=5000)
            print("  ✅ 找到表格元素")
        except Exception as e:
            print(f"  ⚠️ 表格未找到: {e}")
    except Exception as e:
        print(f"  ❌ 失败: {e}")
    finally:
        crawler.close()

def test_fetch_limit_up():
    """测试抓取涨停数据"""
    print("\n测试3: 抓取涨停数据...")
    crawler = IwenCaiCrawler()
    result = crawler.fetch("limit_up", max_retries=1)
    print(f"  success={result.success} error={result.error}")
    if result.success:
        data = result.data
        if isinstance(data, list):
            print(f"  ✅ 获取 {len(data)} 条数据")
            for row in data[:3]:
                print(f"    {row}")
        elif isinstance(data, dict):
            raw = data.get("raw_text", "")
            print(f"  ✅ 降级文本模式 (前300字): {raw[:300]}")
    crawler.close()

def test_data_provider_news():
    """测试 DataProvider 新闻格式化"""
    print("\n测试4: DataProvider 新闻格式化...")
    from utils.llm.data_provider import DataProvider
    provider = DataProvider()
    print(f"  今日日期: {provider.today_full}")
    result = provider.fetch_news()
    print(f"  success={result.get('success')}")
    print(f"  news_text:\n{result.get('news_text', '')[:500]}")
    provider.close()

if __name__ == "__main__":
    print(f"🚀 Playwright 极简测试 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    test_browser_launch()
    test_iwencai_simple()
    test_fetch_limit_up()
    test_data_provider_news()
    print(f"\n结束: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

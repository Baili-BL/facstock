import time
import urllib.parse
from playwright.sync_api import sync_playwright

def fetch_iwencai_data(query_string):
    with sync_playwright() as p:
        # 1. 浏览器配置：伪装 User-Agent
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"

        # 关键修改：设置为 True，浏览器将在后台运行，不显示界面
        browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])

        page = browser.new_page(user_agent=user_agent, viewport={'width': 1920, 'height': 1080})

        try:
            # 2. 构造直接跳转的 URL
            encoded_query = urllib.parse.quote(query_string)
            target_url = f"https://www.iwencai.com/unifiedwap/result?w={encoded_query}"

            print(f"正在后台访问: {target_url}")
            page.goto(target_url, timeout=60000)

            # 3. 等待数据加载
            print("正在等待结果渲染...")
            try:
                page.wait_for_selector("table tbody tr", timeout=20000)
                time.sleep(2) # 额外等待，确保JS渲染完成
            except Exception as e:
                print(f"⚠️ 等待超时或元素未找到: {e}")
                # 即使无头模式，也可以截图来排查问题
                page.screenshot(path="headless_error.png")
                print("已保存错误截图 headless_error.png")
                return

            # 4. 提取数据
            rows = page.locator("table tbody tr").all()

            print(f"\n✅ 成功！共找到 {len(rows)} 条数据：")
            print("-" * 50)

            for i, row in enumerate(rows):
                cells = row.locator("td").all_inner_texts()
                clean_cells = [c.strip() for c in cells if c.strip()]

                # 打印前 10 条数据
                if i < 10:
                    print(f"第 {i+1} 条: {clean_cells}")

            print("-" * 50)
            # 可选：在无头模式下截图，确认抓取效果
            page.screenshot(path="headless_success.png")
            print("已保存成功截图 headless_success.png")

        except Exception as e:
            print(f"❌ 发生致命错误: {e}")

        finally:
            # 5. 关闭浏览器
            browser.close()
            print("浏览器已关闭。")

if __name__ == "__main__":
    my_query = "股价创60日新高"
    fetch_iwencai_data(my_query)

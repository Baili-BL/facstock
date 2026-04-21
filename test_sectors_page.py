#!/usr/bin/env python3
"""测试板块页面是否正常显示数据"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1400, "height": 900})
    page = context.new_page()

    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda err: console_errors.append(f"PAGE ERROR: {err}"))

    # 先检查端口
    print("=== Checking port ===")
    resp = page.goto("http://localhost:5177", timeout=5000)
    print(f"Port 5177: status={resp.status if resp else 'none'}")

    # 导航到板块页面
    print("\n=== Testing /sectors ===")
    try:
        resp = page.goto("http://localhost:5177/sectors", wait_until="domcontentloaded", timeout=10000)
        print(f"Status: {resp.status if resp else 'none'}")
        page.wait_for_timeout(5000)

        body_text = page.locator("body").inner_text()
        print(f"Body text (first 800):\n{body_text[:800]}")
        print(f"\nHas '热门板块': {'热门板块' in body_text}")
        print(f"Has '暂无数据': {'暂无数据' in body_text}")
        print(f"Has '互联网电商': {'互联网电商' in body_text}")
        print(f"Has '华为': {'华为' in body_text}")

        rows = page.locator(".sec-hot-row").all()
        print(f"sec-hot-row count: {len(rows)}")

        page.screenshot(path="/Users/kevin/Desktop/facSstock/screenshot_sectors.png")
        print("Screenshot saved: screenshot_sectors.png")

        if console_errors:
            print(f"\nConsole errors ({len(console_errors)}):")
            for e in console_errors[:10]:
                print(f"  {e}")
        else:
            print("\nNo console errors")
    except Exception as e:
        print(f"Error: {e}")

    browser.close()
    print("\nDone!")

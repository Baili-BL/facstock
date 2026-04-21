#!/usr/bin/env python3
"""测试首页板块显示"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1400, "height": 900})
    page = context.new_page()

    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda err: errors.append(f"PAGE ERROR: {err}"))

    print("=== Testing homepage ===")
    resp = page.goto("http://localhost:5177/", wait_until="domcontentloaded", timeout=10000)
    print(f"Status: {resp.status if resp else 'none'}")
    page.wait_for_timeout(5000)

    body = page.locator("body").inner_text()
    print(f"Body (first 600):\n{body[:600]}")

    # 截图
    page.screenshot(path="/Users/kevin/Desktop/facSstock/screenshot_home.png")
    print("Screenshot saved: screenshot_home.png")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors[:5]:
            print(f"  {e[:200]}")
    else:
        print("\nNo errors")

    browser.close()

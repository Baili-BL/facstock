#!/usr/bin/env python3
"""Test frontend with Playwright"""
import asyncio
import sys

async def test_frontend():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Playwright not installed. Installing...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"])
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
        from playwright.async_api import async_playwright

    ports = [5173, 5174, 5175, 5176, 5177, 5178, 5179]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Collect console messages
        console_messages = []
        page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: console_messages.append(f"[PAGE ERROR] {err}"))

        for port in ports:
            try:
                print(f"\n=== Testing http://localhost:{port} ===")
                await page.goto(f"http://localhost:{port}", timeout=5000)
                await asyncio.sleep(1)
                title = await page.title()
                print(f"Page title: {title}")
                print(f"URL: {page.url}")

                # Check for sectors path
                try:
                    await page.goto(f"http://localhost:{port}/sectors", timeout=5000)
                    await asyncio.sleep(2)
                    content = await page.content()

                    # Look for key elements
                    has_hot_sectors = "hotSectors" in content or "hot-sectors" in content or "热门板块" in content
                    has_no_data = "暂无数据" in content or "no data" in content.lower()

                    print(f"URL after navigation: {page.url}")
                    print(f"Has hot sectors section: {has_hot_sectors}")
                    print(f"Has '暂无数据': {has_no_data}")

                    # Get visible text snippet
                    body_text = await page.inner_text("body")
                    print(f"\nPage body text (first 500 chars):\n{body_text[:500]}")

                except Exception as e:
                    print(f"Error navigating to /sectors: {e}")

                break  # Found working server

            except Exception as e:
                print(f"Port {port}: Not responding ({e})")
                continue

        print("\n\n=== Browser Console Messages ===")
        for msg in console_messages:
            print(msg)

        if not console_messages:
            print("(No console messages)")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_frontend())

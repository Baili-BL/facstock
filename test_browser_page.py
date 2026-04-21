import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        console_messages = []
        errors = []
        page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: errors.append(f"PAGE ERROR: {err}"))

        print("=== Navigating to http://localhost:5177/strategy/agents ===")
        await page.goto("http://localhost:5177/strategy/agents", wait_until="networkidle", timeout=30000)
        print(f"Page title: {await page.title()}")

        # Wait for initial load
        await page.wait_for_timeout(3000)

        # Try to find and click the "全部智能体" tab (second tab button)
        all_agents_tab = page.locator("button", has_text="全部智能体")
        count = await all_agents_tab.count()
        print(f'"全部智能体" tab count: {count}')

        if count > 0:
            print('Clicking "全部智能体" tab...')
            await all_agents_tab.first.click()
            await page.wait_for_timeout(3000)

        # Check for history cards
        card_texts = [
            "周度策略共识",
            "宏观同步快讯",
            "收益率优化建议",
            "绩效洞察",
            "查看完整报告"
        ]

        print("\n=== Content Check ===")
        body_text = await page.locator("body").inner_text()
        for text in card_texts:
            found = text in body_text
            print(f'"{text}": {"FOUND" if found else "NOT FOUND"}')

        # Count cards
        cards = await page.locator(".card, .agent-card, [class*='card']").all()
        print(f"\nTotal card-like elements found: {len(cards)}")

        # Screenshot
        print("\n=== Taking screenshot ===")
        await page.screenshot(path="screenshot_strategy_agents.png", full_page=False)
        print("Screenshot saved as screenshot_strategy_agents.png")

        # Report console messages
        print("\n=== Console Messages ===")
        if not console_messages:
            print("No console messages")
        else:
            for m in console_messages:
                print(m)

        print("\n=== Page Errors ===")
        if not errors:
            print("No page errors")
        else:
            for e in errors:
                print(e)

        # Also get some HTML context for key sections
        print("\n=== Key HTML Sections ===")
        try:
            perf_section = await page.locator("*", has_text="绩效洞察").first.inner_html()
            print("绩效洞察 section HTML (first 500 chars):", perf_section[:500])
        except Exception as e:
            print(f"Could not get 绩效洞察 section: {e}")

        # List all tab buttons
        print("\n=== Tab Buttons ===")
        tabs = await page.locator("button").all()
        for i, tab in enumerate(tabs):
            try:
                text = await tab.inner_text()
                if text.strip():
                    print(f"  Tab {i}: '{text.strip()}'")
            except:
                pass

        await browser.close()
        print("\nDone!")
        return {
            "body_text": body_text,
            "console_messages": console_messages,
            "errors": errors,
        }

if __name__ == "__main__":
    result = asyncio.run(main())

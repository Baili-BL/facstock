#!/usr/bin/env python3
"""
Playwright test script to verify AI analysis streaming batching fix.

The fix changes:
1. Backend: thinking content is sent as ONE complete event per LLM response round
   (instead of splitting by newlines and sending many events)
2. Frontend: accumulates thinking content and flushes in batches by 【 sections
   (instead of flushing on every \n)

Run from your Mac terminal:
    cd /Users/kevin/Desktop/facSstock
    python3 test_streaming_fix.py

Requirements:
    pip install playwright
    playwright install chromium
"""
import asyncio
import json
import os
import re
import sys
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Installing playwright...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"], check=True)
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    from playwright.async_api import async_playwright


SCREENSHOT_DIR = Path("/Users/kevin/Desktop/facSstock/test_screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)


def parse_sse_line(line: bytes) -> dict | None:
    """Parse a single SSE data line."""
    if not line.startswith(b"data: "):
        return None
    try:
        return json.loads(line[6:])
    except:
        return None


async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()

        # Capture SSE events via fetch monitoring
        sse_events = []
        original_fetch = None

        async def handle_response(response):
            if "/api/agents/analyze/" in response.url and "/stream" in response.url:
                try:
                    body = await response.body()
                    text = body.decode("utf-8", errors="replace")
                    lines = text.split("\n")
                    for line in lines:
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                sse_events.append(data)
                            except:
                                pass
                except Exception as e:
                    print(f"Error capturing SSE: {e}")

        page.on("response", handle_response)

        console_logs = []

        async def handle_console(msg):
            console_logs.append(f"[{msg.type}] {msg.text}")

        page.on("console", handle_console)

        try:
            # Navigate to the page
            print("Navigating to analysis page...")
            await page.goto(
                "http://localhost:5173/strategy/agents/beijing/analysis",
                wait_until="networkidle",
                timeout=30000,
            )
            await page.wait_for_timeout(2000)

            await page.screenshot(
                path=str(SCREENSHOT_DIR / "01_page_loaded.png"),
                full_page=True,
            )
            print("Page loaded and screenshot saved.")

            # Find the run button
            button = page.locator(".fac-btn-run")
            if await button.count() == 0:
                button = page.locator("button:has-text('启动'), button:has-text('分析')")
            button_count = await button.count()
            print(f"Found {button_count} run button(s)")

            if button_count == 0:
                print("ERROR: Could not find the '启动 AI 分析' button!")
                await browser.close()
                return

            btn_text = await button.first.inner_text()
            print(f"Button text: '{btn_text.strip()}'")

            # Click the button
            print("Clicking '启动 AI 分析' button...")
            await button.first.click()

            await page.screenshot(
                path=str(SCREENSHOT_DIR / "02_button_clicked.png"),
                full_page=True,
            )

            # Wait for analysis to complete (up to 90s)
            print("Waiting for analysis to complete (max 90s)...")
            max_wait = 90
            elapsed = 0
            interval = 5

            while elapsed < max_wait:
                await page.wait_for_timeout(interval * 1000)
                elapsed += interval

                # Check if done
                done_badge = page.locator(".fac-badge--done")
                is_done = await done_badge.count() > 0

                # Count thinking items
                thinking_items = page.locator(".fac-timeline__item")
                thinking_count = await thinking_items.count()

                # Count report lines
                report_lines = page.locator(".fac-report-line")
                report_count = await report_lines.count()

                # Check for error badge
                error_badge = page.locator(".fac-badge--error")
                has_error = await error_badge.count() > 0

                print(
                    f"  {elapsed}s: thinking_items={thinking_count}, "
                    f"report_lines={report_count}, done={is_done}, error={has_error}"
                )

                # Take screenshot every 15 seconds
                if elapsed % 15 == 0:
                    await page.screenshot(
                        path=str(
                            SCREENSHOT_DIR / f"03_progress_{elapsed}s.png"
                        ),
                        full_page=True,
                    )

                if is_done:
                    print("Analysis completed!")
                    break

                if has_error:
                    print("Error detected during analysis.")
                    break

            # Final screenshot
            await page.screenshot(
                path=str(SCREENSHOT_DIR / "04_final.png"),
                full_page=True,
            )

            # Get final counts
            final_thinking = await page.locator(".fac-timeline__item").count()
            final_report = await page.locator(".fac-report-line").count()
            consensus = await page.locator(".fac-consensus-card").count()
            recs = await page.locator(".fac-recs-card").count()

            print(f"\n=== RESULTS ===")
            print(f"Thinking timeline items: {final_thinking}")
            print(f"Report lines: {final_report}")
            print(f"Consensus card: {'FOUND' if consensus else 'NOT FOUND'}")
            print(f"Recommendations card: {'FOUND' if recs else 'NOT FOUND'}")

            # Print thinking content to check batching
            if final_thinking > 0:
                print(f"\n=== THINKING CONTENT (first 10 items) ===")
                for i in range(min(final_thinking, 10)):
                    try:
                        title_el = page.locator(".fac-timeline__item").nth(i).locator(
                            ".fac-timeline__title"
                        )
                        desc_el = page.locator(".fac-timeline__item").nth(i).locator(
                            ".fac-timeline__desc"
                        )
                        title = await title_el.inner_text() if await title_el.count() > 0 else ""
                        desc = await desc_el.inner_text() if await desc_el.count() > 0 else ""
                        print(f"  {i+1}. [{title.strip()}] {desc[:100]}")
                    except Exception as e:
                        print(f"  {i+1}. (error: {e})")

            # Print report content
            if final_report > 0:
                print(f"\n=== REPORT CONTENT (first 10 lines) ===")
                for i in range(min(final_report, 10)):
                    try:
                        line_el = page.locator(".fac-report-line").nth(i)
                        line_class = await line_el.get_attribute("class") or ""
                        line_text = await line_el.inner_text()
                        section_marker = "【section】" if "section" in line_class else "  [normal]"
                        print(f"  {i+1}{section_marker} {line_text[:100]}")
                    except Exception as e:
                        print(f"  {i+1}. (error: {e})")

            # Analyze SSE events
            if sse_events:
                print(f"\n=== SSE EVENT ANALYSIS ===")
                thinking_events = [e for e in sse_events if e.get("type") == "thinking"]
                print(f"Total SSE events captured: {len(sse_events)}")
                print(f"Thinking events: {len(thinking_events)}")

                if thinking_events:
                    print(
                        f"Before fix: would be ~{sum(len(e.get('content','').split(chr(10))) for e in thinking_events)} lines"
                    )
                    print(
                        f"After fix: {len(thinking_events)} events, each being a complete block"
                    )

                    # Show first few thinking events
                    for i, ev in enumerate(thinking_events[:3]):
                        content = ev.get("content", "")
                        preview = content[:100].replace("\n", "\\n")
                        print(f"  Event {i+1}: {len(content)} chars, preview: {repr(preview)}...")

            # Console errors
            error_logs = [l for l in console_logs if "error" in l.lower()]
            if error_logs:
                print(f"\n=== CONSOLE ERRORS ===")
                for log in error_logs[:5]:
                    print(f"  {log}")

            print(f"\nScreenshots saved to: {SCREENSHOT_DIR}")
            print(f"Total screenshots: {len(list(SCREENSHOT_DIR.glob('*.png')))}")

        except Exception as e:
            print(f"Error: {e}")
            import traceback

            traceback.print_exc()
            await page.screenshot(
                path=str(SCREENSHOT_DIR / "error.png"), full_page=True
            )
        finally:
            await browser.close()


if __name__ == "__main__":
    print("=" * 60)
    print("AI Analysis Streaming Fix Test")
    print("=" * 60)
    asyncio.run(run_test())

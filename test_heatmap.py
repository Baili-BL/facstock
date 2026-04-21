#!/usr/bin/env python3
"""Test SectorHeatmap page loads and G2 treemap renders."""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 390, "height": 844})

        errors = []
        warnings = []
        page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else warnings.append(f"[{msg.type}] {msg.text}") if msg.type == "warning" else None)
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))

        resp = await page.goto("http://localhost:5177/sectors/heatmap", wait_until="domcontentloaded", timeout=15000)
        print(f"Status: {resp.status}")

        # Wait for data to load and chart to render
        await page.wait_for_timeout(6000)

        # Check page title
        title = await page.text_content(".kq-bar__title")
        print(f"Page title: {title}")

        # Check if loading state is gone
        loading = await page.query_selector(".kq-loading")
        empty = await page.query_selector(".kq-empty")
        treemap_wrap = await page.query_selector(".kq-g2-treemap")
        print(f"Loading: {loading is not None}, Empty: {empty is not None}, Treemap wrap: {treemap_wrap is not None}")

        # Check the container content
        container_html = await page.inner_html(".kq-g2-treemap") if treemap_wrap else "N/A"
        print(f"Treemap wrap HTML length: {len(container_html)}")
        if container_html and len(container_html) < 200:
            print(f"Treemap HTML: {container_html}")

        # Count SVG elements anywhere on page
        all_svgs = await page.query_selector_all("svg")
        print(f"Total SVG elements on page: {len(all_svgs)}")

        # Check for G2 canvas
        canvases = await page.query_selector_all("canvas")
        print(f"Canvas elements: {len(canvases)}")

        # Check rects inside the treemap
        if treemap_wrap:
            rects = await page.query_selector_all(".kq-g2-treemap rect")
            print(f"Rects in treemap: {len(rects)}")

        # Check console errors/warnings
        if errors:
            print("Console errors:")
            for e in errors:
                print(f"  {e}")
        if warnings:
            print("Console warnings (first 5):")
            for w in warnings[:5]:
                print(f"  {w}")
        if not errors and not warnings:
            print("No console errors or warnings")

        await browser.close()

asyncio.run(main())

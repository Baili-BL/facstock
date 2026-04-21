#!/usr/bin/env python3
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 390, 'height': 844})

        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append(f'[{m.type}] {m.text}') if m.type == 'error' else None)

        resp = await page.goto('http://localhost:5177/sectors/heatmap', wait_until='domcontentloaded', timeout=15000)
        await page.wait_for_timeout(7000)

        title = await page.text_content('.kq-bar__title')
        loading = await page.query_selector('.kq-loading')
        empty = await page.query_selector('.kq-empty')
        wrap = await page.query_selector('.kq-treemap-wrap')
        rects = await page.query_selector_all('rect.st-map__cell')
        labels = await page.query_selector_all('.st-map__label')

        # Get label text sample
        label_texts = []
        if labels:
            for lbl in labels[:5]:
                txt = await lbl.inner_text()
                label_texts.append(txt.strip().replace('\n', ' '))
            label_texts.append('...')

        result = {
            'status': resp.status,
            'title': title,
            'loading': loading is not None,
            'empty': empty is not None,
            'wrap': wrap is not None,
            'rects': len(rects),
            'labels': len(labels),
            'label_samples': label_texts,
            'errors': errors,
        }

        with open('/tmp/heatmap_result.json', 'w') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(json.dumps(result, ensure_ascii=False, indent=2))
        await browser.close()

asyncio.run(main())

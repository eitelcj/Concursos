"""Local-only browser smoke tests; run against test API with sandbox test password."""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

p = argparse.ArgumentParser()
p.add_argument('--url', default='http://127.0.0.1:19022')
p.add_argument('--out', default='/mnt/data/radar-v2-0-2/visual')
p.add_argument('--password', default='testing7')
p.add_argument(
    '--chromium', default=None, help='Caminho do Chrome/Chromium; por padrão usa navegador Playwright instalado'
)
args = p.parse_args()
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as play:
    browser = play.chromium.launch(
        **({'executable_path': args.chromium} if args.chromium else {}),
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage'],
    )
    for viewport, label in [({'width': 1440, 'height': 900}, 'desktop'), ({'width': 390, 'height': 844}, 'mobile')]:
        page = browser.new_page(viewport=viewport, device_scale_factor=1)
        page.goto(args.url, wait_until='networkidle', timeout=15000)
        page.locator('[name=password]').fill(args.password)
        page.locator('#loginForm button[type=submit]').click()
        page.locator('#appView').wait_for(state='visible')
        for tab in ('home', 'settings', 'sources'):
            page.locator(f'[data-tab="{tab}"]').click()
            page.locator(f'#{tab}').wait_for(state='visible')
            page.screenshot(path=str(out / f'{label}_{tab}.png'), full_page=True)
            bbox = page.locator('.content').bounding_box()
            sidebar = page.locator('.sidebar').bounding_box()
            rootwidth = page.evaluate('document.documentElement.scrollWidth')
            assert bbox['y'] < 40, (label, tab, bbox)
            assert rootwidth <= viewport['width'] + 1, (label, tab, 'horizontal overflow', rootwidth)
            if label == 'desktop':
                assert sidebar['height'] >= viewport['height'] - 5
            print(
                label,
                tab,
                'content_y',
                round(bbox['y']),
                'scrollwidth',
                rootwidth,
                'favicon',
                page.locator('link[rel="icon"]').count(),
            )
        page.close()
    browser.close()

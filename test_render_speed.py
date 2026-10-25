import os
import time

from playwright.sync_api import sync_playwright

TOKEN = os.environ.get("BROWSERLESS_TOKEN")
if not TOKEN:
    raise SystemExit("Set BROWSERLESS_TOKEN first")

URL = f"wss://production-sfo.browserless.io?token={TOKEN}&timeout=120000"

HTML = (
    "<html><body style='background:#0a0e1a;color:white;"
    "font-family:sans-serif;padding:60px'><h1>Test Slide</h1>"
    "<p>This is a test card.</p></body></html>"
)

start = time.time()
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(URL)
    try:
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        for i in range(10):
            page.set_content(HTML, wait_until="networkidle")
            png = page.screenshot(type="png")
            print(f"Slide {i + 1}: {len(png)} bytes")
    finally:
        browser.close()

elapsed = time.time() - start
print(f"\nTOTAL TIME: {elapsed:.1f} seconds")
if elapsed > 120:
    print("WARNING: Exceeds 2-minute free tier limit!")
else:
    print("OK: Within 2-minute limit.")

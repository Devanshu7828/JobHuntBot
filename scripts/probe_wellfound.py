import os
import warnings
from playwright.sync_api import sync_playwright

warnings.filterwarnings("ignore")
STEALTH = "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=False,
                                args=["--disable-blink-features=AutomationControlled"])
    configs = [
        ("minimal", {}),
        ("viewport", {"viewport": {"width": 1366, "height": 900}}),
        ("locale_us", {"locale": "en-US"}),
        ("stealth_script", {}),
        ("viewport+stealth", {"viewport": {"width": 1366, "height": 900}}),
    ]
    for label, extra in configs:
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
            ignore_https_errors=True,
            **{k: v for k, v in extra.items() if k != "stealth_script"},
        )
        if "stealth" in label:
            ctx.add_init_script(STEALTH)
        page = ctx.new_page()
        page.goto("https://wellfound.com/role/r/qa-engineer", timeout=30000)
        page.wait_for_timeout(6000)
        count = page.evaluate(
            '() => document.querySelectorAll(\'a[href*="/jobs/"]\').length'
        )
        print(label, count)
        ctx.close()
    browser.close()

"""Probe Wellfound listings."""
from playwright.sync_api import sync_playwright

STEALTH = "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True,
                                args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
        ignore_https_errors=True,
    )
    ctx.add_init_script(STEALTH)
    page = ctx.new_page()

    for url in [
        "https://wellfound.com/jobs?location=India",
        "https://wellfound.com/role/r/qa-engineer",
    ]:
        resp = page.goto(url, timeout=30000)
        page.wait_for_timeout(8000)
        links = page.query_selector_all('a[href*="/jobs/"]')
        print(url, "status", resp.status if resp else None, "links", len(links))
        for l in links[:8]:
            href = l.get_attribute("href") or ""
            if href in ("/jobs", "/jobs/"):
                continue
            print(" ", l.inner_text()[:50].replace("\n", " "), "|", href[:70])

    browser.close()

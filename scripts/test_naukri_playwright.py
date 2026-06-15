"""Quick debug script for Naukri Playwright scraping."""
import re
import yaml
from playwright.sync_api import sync_playwright

SEARCH_URL = "https://www.naukri.com/sdet-jobs-in-pune"
STEALTH_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
)


def run_attempt(name: str, headless: bool, channel: str = None):
    api_calls = []
    with sync_playwright() as p:
        launch_kwargs = {
            "headless": headless,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        if channel:
            launch_kwargs["channel"] = channel

        browser = p.chromium.launch(**launch_kwargs)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-IN",
            ignore_https_errors=True,
            viewport={"width": 1366, "height": 900},
        )
        ctx.add_init_script(STEALTH_SCRIPT)
        page = ctx.new_page()

        def cap(response):
            if "jobapi" in response.url:
                api_calls.append((response.status, response.url[:120]))

        page.on("response", cap)
        home = page.goto("https://www.naukri.com", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        result = page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)

        html = page.content()
        cards = page.query_selector_all(
            "div.cust-job-tuple, article.jobTuple, div.srp-jobtuple"
        )
        print(f"\n=== {name} ===")
        print("home:", home.status if home else None)
        print("search:", result.status if result else None)
        print("cards:", len(cards))
        print("html len:", len(html))
        print("access denied:", "access denied" in html.lower())
        print("jobDetails has data:", bool(re.search(r'"jobDetails":\[\{', html)))
        print("api calls:", api_calls[:5])
        if cards:
            title = page.query_selector("a.title, a[href*='job-listings']")
            print("sample:", title.inner_text() if title else None)
        browser.close()


if __name__ == "__main__":
    run_attempt("chromium-headless", headless=True)
    run_attempt("chromium-headed", headless=False)
    for ch in ("msedge", "chrome"):
        try:
            run_attempt(f"channel-{ch}", headless=True, channel=ch)
        except Exception as e:
            print(f"\n=== channel-{ch} === FAILED:", e)

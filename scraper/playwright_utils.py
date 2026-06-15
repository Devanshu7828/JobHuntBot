"""Shared Playwright helpers for JS-rendered job portals."""
from scraper.base_scraper import BaseScraper

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

STEALTH_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
)


def get_platform_cfg(config: dict, platform: str) -> dict:
    return config.get("platforms", {}).get(platform, {})


def launch_browser(playwright, config: dict, platform: str):
    """Launch Edge/Chrome; bundled Chromium is often blocked by Indian job CDNs."""
    cfg = get_platform_cfg(config, platform)
    headless = cfg.get("headless", True)
    channel_pref = cfg.get("browser_channel", "msedge")

    launch_kwargs = {
        "headless": headless,
        "args": ["--disable-blink-features=AutomationControlled"],
    }
    channels = []
    if channel_pref:
        channels.append(channel_pref)
    for fallback in ("msedge", "chrome"):
        if fallback not in channels:
            channels.append(fallback)
    channels.append(None)

    last_error = None
    for channel in channels:
        try:
            kwargs = dict(launch_kwargs)
            if channel:
                kwargs["channel"] = channel
            browser = playwright.chromium.launch(**kwargs)
            return browser, channel or "chromium"
        except Exception as e:
            last_error = e

    raise RuntimeError(f"Could not launch browser: {last_error}")


def new_stealth_context(browser, config: dict, platform: str = ""):
    cfg = get_platform_cfg(config, platform) if platform else {}
    ctx_kwargs = {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "viewport": {"width": 1366, "height": 900},
        "ignore_https_errors": not config.get("verify_ssl", True),
    }
    locale = cfg.get("locale", "en-IN")
    if locale:
        ctx_kwargs["locale"] = locale
    context = browser.new_context(**ctx_kwargs)
    context.add_init_script(STEALTH_SCRIPT)
    return context


class PlaywrightMixin(BaseScraper):
    """Mixin for scrapers that need a real browser."""

    platform_name = "playwright"

    def _pw_cfg(self) -> dict:
        return get_platform_cfg(self.config, self.platform_name)

    def _max_keywords(self, default: int = 3) -> int:
        return self._pw_cfg().get("max_keywords", default)

    def _max_locations(self, default: int = 5) -> int:
        return self._pw_cfg().get("max_locations", default)

    def _page_timeout(self) -> int:
        return self._pw_cfg().get("page_timeout_ms", 30000)

    def _require_playwright(self) -> bool:
        if PLAYWRIGHT_AVAILABLE:
            return True
        self.log(
            "Playwright not installed. Run: py -m pip install playwright "
            "&& py -m playwright install chromium"
        )
        return False

"""
Naukri.com job scraper — uses Playwright with installed Edge/Chrome.

Naukri's CDN (Akamai) blocks bundled headless Chromium (403). Using the
system Edge/Chrome channel avoids that and loads the JS-rendered job list.
"""
import json
import re
from bs4 import BeautifulSoup
from scraper.base_scraper import BaseScraper, Job

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

STEALTH_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
)


class NaukriScraper(BaseScraper):

    BASE_URL = "https://www.naukri.com"
    JOB_CARD_SELECTOR = (
        "div.cust-job-tuple, article.jobTuple, div.srp-jobtuple, div[class*='jobTuple']"
    )

    def __init__(self, config: dict):
        super().__init__(config)
        naukri_cfg = config.get("platforms", {}).get("naukri", {})
        self.headless = naukri_cfg.get("headless", True)
        self.browser_channel = naukri_cfg.get("browser_channel", "msedge")
        self.page_timeout_ms = naukri_cfg.get("page_timeout_ms", 30000)
        self.max_keywords = naukri_cfg.get("max_keywords", 3)
        self.max_locations = naukri_cfg.get("max_locations", 5)

    def _slug(self, text: str) -> str:
        slug = text.lower().strip()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"\s+", "-", slug)
        return slug

    def _build_search_url(self, keyword: str, location: str) -> str:
        kw = self._slug(keyword)
        loc = self._slug(location)
        sf = self.config.get("search", {}).get("salary_filter", {})
        salary_qs = ""
        if sf.get("enabled", False):
            min_lpa = float(sf.get("min_lpa", 3))
            if min_lpa <= 6:
                salary_qs = "?ctcFilter=3to6&ctcFilter=6to10&ctcFilter=10to15"
            elif min_lpa <= 10:
                salary_qs = "?ctcFilter=6to10&ctcFilter=10to15&ctcFilter=15to25"
            else:
                salary_qs = "?ctcFilter=10to15&ctcFilter=15to25"
        if loc == "remote":
            base = f"{self.BASE_URL}/{kw}-jobs"
        else:
            base = f"{self.BASE_URL}/{kw}-jobs-in-{loc}"
        return base + salary_qs

    def scrape(self) -> list:
        if not PLAYWRIGHT_AVAILABLE:
            self.log(
                "Playwright not installed. Run: py -m pip install playwright "
                "&& py -m playwright install chromium"
            )
            return []

        jobs = []
        seen_urls = set()
        keywords = self.keywords[: self.max_keywords]
        locations = self._unique_locations(self.locations[: self.max_locations])
        searches = [(k, l) for k in keywords for l in locations]
        per_search = max(6, self.max_jobs // max(1, len(searches)))

        with sync_playwright() as playwright:
            browser, channel_used = self._launch_browser(playwright)
            self.log(f"Browser: {channel_used} (headless={self.headless})")

            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1366, "height": 900},
                locale="en-IN",
                ignore_https_errors=not self.verify_ssl,
            )
            context.add_init_script(STEALTH_SCRIPT)
            page = context.new_page()

            try:
                # Warm up session — reduces Akamai 403 on first request
                warmup = page.goto(self.BASE_URL, wait_until="domcontentloaded",
                                   timeout=self.page_timeout_ms)
                if warmup and warmup.status == 403:
                    self.log("Naukri blocked by CDN (403). Try browser_channel: msedge or headless: false")
                    return []
                page.wait_for_timeout(1500)

                for keyword, location in searches:
                    self.log(f"Searching: '{keyword}' in '{location}'")
                    fetched = self._search(page, keyword, location)[:per_search]
                    for job in fetched:
                        if job.url not in seen_urls:
                            seen_urls.add(job.url)
                            jobs.append(job)
                    self.random_delay(2, 3)
                    if len(jobs) >= self.max_jobs:
                        break
            finally:
                context.close()
                browser.close()

        self.log(f"Total jobs found: {len(jobs)}")
        return jobs[: self.max_jobs]

    def _launch_browser(self, playwright):
        """Launch Edge/Chrome channel; bundled Chromium is blocked by Naukri CDN."""
        launch_kwargs = {
            "headless": self.headless,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        channels = []
        if self.browser_channel:
            channels.append(self.browser_channel)
        for fallback in ("msedge", "chrome"):
            if fallback not in channels:
                channels.append(fallback)
        channels.append(None)  # bundled chromium last resort

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
                continue

        raise RuntimeError(f"Could not launch browser for Naukri: {last_error}")

    def _unique_locations(self, locations: list) -> list:
        seen = set()
        unique = []
        for loc in locations:
            key = loc.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(loc)
        return unique

    def _search(self, page, keyword: str, location: str) -> list:
        url = self._build_search_url(keyword, location)
        api_jobs = []

        def capture_api(response):
            if "jobapi" not in response.url or "search" not in response.url:
                return
            if response.status != 200:
                return
            try:
                payload = response.json()
                parsed = self._parse_api_payload(payload, location)
                if parsed:
                    api_jobs.extend(parsed)
            except Exception:
                pass

        page.on("response", capture_api)

        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=self.page_timeout_ms)
            if response and response.status == 403:
                self.log("Naukri CDN blocked this search (403).")
                return []

            try:
                page.wait_for_selector(self.JOB_CARD_SELECTOR, timeout=12000)
            except PlaywrightTimeout:
                page.wait_for_timeout(3000)

            if self._page_blocked(page):
                self.log("Naukri blocked this request (captcha/WAF). Skipping.")
                return []

            if api_jobs:
                return api_jobs

            return self._parse_html(page.content(), keyword, location)
        except PlaywrightTimeout:
            self.log(f"Timed out loading Naukri page: {keyword} / {location}")
            return api_jobs or []
        except Exception as e:
            self.log(f"Error fetching Naukri jobs: {e}")
            return api_jobs or []
        finally:
            page.remove_listener("response", capture_api)

    def _page_blocked(self, page) -> bool:
        html = page.content()
        html_lower = html.lower()
        if len(html) < 2000 and "access denied" in html_lower:
            return True
        blocked_markers = (
            "unusual traffic",
            "please verify you are a human",
            "are you a robot",
        )
        return any(marker in html_lower for marker in blocked_markers)

    def _parse_api_payload(self, payload: dict, fallback_location: str) -> list:
        details = payload.get("jobDetails") or payload.get("jobs") or []
        jobs = []
        for item in details:
            try:
                title = item.get("title") or item.get("jobTitle") or ""
                company = item.get("companyName") or item.get("company") or ""
                job_id = str(item.get("jobId") or item.get("id") or "")
                job_url = item.get("jdURL") or item.get("jobUrl") or ""
                if job_url and not job_url.startswith("http"):
                    job_url = self.BASE_URL + job_url
                if not job_url and job_id:
                    job_url = f"{self.BASE_URL}/job-listings-{job_id}"

                placeholders = item.get("placeholders") or []
                experience = ""
                salary = "Not disclosed"
                job_location = fallback_location
                for ph in placeholders:
                    ph_type = (ph.get("type") or "").lower()
                    label = ph.get("label") or ""
                    if ph_type == "experience":
                        experience = label
                    elif ph_type == "salary":
                        salary = label
                    elif ph_type == "location":
                        job_location = label

                description = item.get("jobDescription") or item.get("description") or ""
                skills = item.get("tagsAndSkills") or item.get("skills") or []
                if isinstance(skills, str):
                    skills = [s.strip() for s in skills.split(",") if s.strip()]

                if title:
                    jobs.append(Job(
                        title=title,
                        company=company,
                        location=job_location,
                        url=job_url,
                        platform="Naukri",
                        description=description,
                        salary=salary,
                        experience=experience,
                        skills=skills if isinstance(skills, list) else [],
                        job_id=job_id,
                    ))
            except Exception as e:
                self.log(f"Error parsing API job: {e}")
        return jobs

    def _parse_html(self, html: str, keyword: str, location: str) -> list:
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        cards = (
            soup.select("div.cust-job-tuple")
            or soup.select("article.jobTuple")
            or soup.select("div.srp-jobtuple")
            or soup.select("div[class*='jobTuple']")
        )

        for card in cards:
            try:
                title_tag = (
                    card.select_one("a.title")
                    or card.select_one("a[title]")
                    or card.select_one("h2 a")
                    or card.select_one("a[href*='job-listings']")
                )
                if not title_tag:
                    continue

                title = title_tag.get_text(strip=True)
                job_url = title_tag.get("href", "")
                if job_url and not job_url.startswith("http"):
                    job_url = self.BASE_URL + job_url

                company_tag = (
                    card.select_one("a.comp-name")
                    or card.select_one("a.subTitle")
                    or card.select_one("span.comp-name")
                    or card.select_one("div.comp-name")
                )
                company = company_tag.get_text(strip=True) if company_tag else ""

                exp_tag = card.select_one("span.expwdth") or card.select_one("li.experience")
                experience = exp_tag.get_text(strip=True) if exp_tag else ""

                sal_tag = card.select_one("span.salwdth") or card.select_one("li.salary")
                salary = sal_tag.get_text(strip=True) if sal_tag else "Not disclosed"

                loc_tag = card.select_one("span.locWdth") or card.select_one("li.location")
                job_location = loc_tag.get_text(strip=True) if loc_tag else location

                desc_tag = card.select_one("div.job-desc") or card.select_one("div.collapse")
                description = desc_tag.get_text(strip=True) if desc_tag else ""

                skills_tags = card.select("ul.tags-gt li") or card.select("div.tags span")
                skills = [s.get_text(strip=True) for s in skills_tags if s.get_text(strip=True)]

                job_id = ""
                id_match = re.search(r"jobId=(\d+)", job_url) or re.search(
                    r"job-listings-(\d+)", job_url
                )
                if id_match:
                    job_id = id_match.group(1)

                if title:
                    jobs.append(Job(
                        title=title,
                        company=company,
                        location=job_location,
                        url=job_url,
                        platform="Naukri",
                        description=description,
                        salary=salary,
                        experience=experience,
                        skills=skills,
                        job_id=job_id,
                    ))
            except Exception as e:
                self.log(f"Error parsing card: {e}")

        if not jobs:
            embedded = self._parse_embedded_json(html, location)
            if embedded:
                return embedded
            self.log(f"No job cards found on page: {keyword} / {location}")

        return jobs

    def _parse_embedded_json(self, html: str, fallback_location: str) -> list:
        match = re.search(r'"jobDetails"\s*:\s*(\[[\s\S]*?\])\s*,\s*"fatFooter"', html)
        if not match:
            return []
        try:
            details = json.loads(match.group(1))
            return self._parse_api_payload({"jobDetails": details}, fallback_location)
        except json.JSONDecodeError:
            return []

"""Instahyre.com — Playwright scraper for curated India tech jobs."""
import re
from bs4 import BeautifulSoup
from scraper.base_scraper import Job
from scraper.keyword_utils import instahyre_slug_variants
from scraper.playwright_utils import (
    PlaywrightMixin, launch_browser, new_stealth_context, sync_playwright,
)


class InstahyreScraper(PlaywrightMixin):

    platform_name = "instahyre"
    BASE_URL = "https://www.instahyre.com"

    def _slug(self, text: str) -> str:
        slug = text.lower().strip()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"\s+", "-", slug)
        return slug

    def _build_urls(self, keyword: str, location: str) -> list:
        loc = self._slug(location)
        urls = []
        for kw in instahyre_slug_variants(keyword):
            if loc == "remote":
                urls.append(f"{self.BASE_URL}/{kw}-jobs/")
            else:
                urls.append(f"{self.BASE_URL}/{kw}-jobs-in-{loc}/")
        return urls

    def scrape(self) -> list:
        if not self._require_playwright():
            return []

        jobs = []
        seen = set()
        keywords = self.keywords[: self._max_keywords()]
        locations = self._unique_locations(self.locations[: self._max_locations()])

        with sync_playwright() as playwright:
            browser, channel = launch_browser(playwright, self.config, self.platform_name)
            self.log(f"Browser: {channel}")
            context = new_stealth_context(browser, self.config)
            page = context.new_page()

            try:
                page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=self._page_timeout())
                page.wait_for_timeout(1500)

                for keyword in keywords:
                    for location in locations:
                        self.log(f"Searching: '{keyword}' in '{location}'")
                        fetched = self._search(page, keyword, location)
                        for job in fetched:
                            if job.url not in seen:
                                seen.add(job.url)
                                jobs.append(job)
                        self.random_delay(2, 3)
                        if len(jobs) >= self.max_jobs:
                            break
                    if len(jobs) >= self.max_jobs:
                        break
            finally:
                context.close()
                browser.close()

        self.log(f"Total jobs found: {len(jobs)}")
        return jobs[: self.max_jobs]

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
        jobs = []
        seen = set()
        for url in self._build_urls(keyword, location):
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=self._page_timeout())
                if response and response.status == 404:
                    continue
                page.wait_for_timeout(4000)
                for job in self._parse(page.content(), location):
                    if job.url not in seen:
                        seen.add(job.url)
                        jobs.append(job)
                if jobs:
                    break
            except Exception as e:
                self.log(f"Error fetching Instahyre jobs: {e}")
        return jobs

    def _parse(self, html: str, fallback_location: str) -> list:
        soup = BeautifulSoup(html, "lxml")
        jobs = []
        seen = set()

        for link in soup.select('a[href*="/job-"]'):
            href = link.get("href", "")
            if href in seen or "instahyre.com" not in href and not href.startswith("/job-"):
                continue

            text = link.get_text("\n", strip=True)
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            if not lines:
                continue

            title = lines[0]
            company = ""
            job_location = fallback_location
            for line in lines[1:4]:
                if " - " in line and not company:
                    company = line.split(" - ")[0].strip()
                if "available in" in line.lower():
                    job_location = line.replace("Job available in", "").strip()

            job_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
            seen.add(href)

            job_id = ""
            m = re.search(r"/job-(\d+)-", href)
            if m:
                job_id = m.group(1)

            jobs.append(Job(
                title=title,
                company=company,
                location=job_location,
                url=job_url,
                platform="Instahyre",
                job_id=job_id,
            ))

        return jobs

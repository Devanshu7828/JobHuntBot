"""Wellfound (AngelList) — Playwright scraper for startup jobs."""
import re
import urllib.parse
from scraper.base_scraper import Job
from scraper.keyword_utils import matches_job_text, search_terms
from scraper.playwright_utils import (
    PlaywrightMixin, launch_browser, new_stealth_context, sync_playwright,
)


class WellfoundScraper(PlaywrightMixin):

    platform_name = "wellfound"
    BASE_URL = "https://wellfound.com"

    def scrape(self) -> list:
        if not self._require_playwright():
            return []

        jobs = []
        seen = set()
        role_paths = ["qa-engineer", "sdet", "test-engineer"]
        search_list = search_terms(self.keywords)[:2]

        with sync_playwright() as playwright:
            browser, channel = launch_browser(playwright, self.config, self.platform_name)
            self.log(f"Browser: {channel}")
            context = new_stealth_context(browser, self.config, self.platform_name)
            page = context.new_page()

            try:
                for role in role_paths:
                    self.log(f"Searching role: '{role}'")
                    fetched = self._search_role(page, role)
                    for job in fetched:
                        if job.url not in seen:
                            seen.add(job.url)
                            jobs.append(job)
                    self.random_delay(2, 3)
                    if len(jobs) >= self.max_jobs:
                        break

                for keyword in search_list:
                    if len(jobs) >= self.max_jobs:
                        break
                    self.log(f"Searching: '{keyword}'")
                    fetched = self._search(page, keyword)
                    for job in fetched:
                        if job.url not in seen:
                            seen.add(job.url)
                            jobs.append(job)
                    self.random_delay(2, 3)
            finally:
                context.close()
                browser.close()

        self.log(f"Total jobs found: {len(jobs)}")
        return jobs[: self.max_jobs]

    def _search_role(self, page, role: str) -> list:
        url = f"{self.BASE_URL}/role/r/{role}"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=self._page_timeout())
            page.wait_for_timeout(6000)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            return self._parse_page(page, apply_keyword_filter=False)
        except Exception as e:
            self.log(f"Error fetching Wellfound role '{role}': {e}")
            return []

    def _search(self, page, keyword: str) -> list:
        params = urllib.parse.urlencode({"query": keyword, "location": "India"})
        url = f"{self.BASE_URL}/jobs?{params}"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=self._page_timeout())
            page.wait_for_timeout(6000)
            return self._parse_page(page, apply_keyword_filter=True)
        except Exception as e:
            self.log(f"Error fetching Wellfound jobs: {e}")
            return []

    def _parse_page(self, page, apply_keyword_filter: bool = True) -> list:
        """Extract job links via JS — more reliable than Playwright selectors on SPA pages."""
        jobs = []
        seen = set()

        entries = page.evaluate(
            """() => Array.from(document.querySelectorAll('a[href*="/jobs/"]')).map(a => ({
                href: a.getAttribute('href') || '',
                title: (a.innerText || a.textContent || '').trim()
            }))"""
        )

        for entry in entries:
            href = entry.get("href", "")
            if href in ("/jobs", "/jobs/") or href in seen:
                continue
            if not re.search(r"/jobs/\d+", href):
                continue

            title = (entry.get("title") or "").strip()
            if not title or len(title) < 4:
                slug = href.split("/jobs/")[-1].replace("-", " ")
                title = slug.title()

            text = f"{title} {href}"
            if apply_keyword_filter and self.keywords and not matches_job_text(text, self.keywords):
                continue

            job_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
            seen.add(href)

            job_id = ""
            m = re.search(r"/jobs/(\d+)", href)
            if m:
                job_id = m.group(1)

            jobs.append(Job(
                title=title,
                company="",
                location="India / Remote",
                url=job_url,
                platform="Wellfound",
                job_id=job_id,
            ))

        return jobs

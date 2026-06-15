"""Shine.com — HTML job search for India."""
import re
import requests
from bs4 import BeautifulSoup
from scraper.base_scraper import BaseScraper, Job


class ShineScraper(BaseScraper):

    BASE_URL = "https://www.shine.com"

    def scrape(self) -> list:
        jobs = []
        seen = set()
        for keyword in self.keywords[: self._max_kw()]:
            for location in self.locations[: self._max_loc()]:
                self.log(f"Searching: '{keyword}' in '{location}'")
                fetched = self._search(keyword, location)
                for job in fetched:
                    if job.url not in seen:
                        seen.add(job.url)
                        jobs.append(job)
                self.random_delay(2, 3)
                if len(jobs) >= self.max_jobs:
                    break
            if len(jobs) >= self.max_jobs:
                break

        self.log(f"Total jobs found: {len(jobs)}")
        return jobs[: self.max_jobs]

    def _max_kw(self) -> int:
        return self.config.get("platforms", {}).get("shine", {}).get("max_keywords", 3)

    def _max_loc(self) -> int:
        return self.config.get("platforms", {}).get("shine", {}).get("max_locations", 3)

    def _slug(self, text: str) -> str:
        slug = text.lower().strip()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"\s+", "-", slug)
        return slug

    def _search(self, keyword: str, location: str) -> list:
        kw = self._slug(keyword)
        loc = self._slug(location)
        url = f"{self.BASE_URL}/job-search/{kw}-jobs-in-{loc}"
        try:
            response = requests.get(
                url, headers=self.get_headers(), timeout=20, verify=self.get_verify_ssl()
            )
            response.raise_for_status()
            return self._parse(response.text, location)
        except Exception as e:
            self.log(f"Error fetching Shine jobs: {e}")
            return []

    def _parse(self, html: str, fallback_location: str) -> list:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []
        seen_urls = set()

        for link in soup.select('a[href*="/jobs/"]'):
            href = link.get("href", "")
            if "/job-search/" in href or href in seen_urls:
                continue
            title = link.get_text(" ", strip=True)
            if not title or len(title) < 5:
                continue

            job_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
            seen_urls.add(href)

            company = ""
            parts = href.strip("/").split("/")
            if len(parts) >= 3:
                company = parts[-2].replace("-", " ").title()

            job_id = parts[-1] if parts and parts[-1].isdigit() else ""

            jobs.append(Job(
                title=title,
                company=company,
                location=fallback_location,
                url=job_url,
                platform="Shine",
                job_id=job_id,
            ))

        return jobs

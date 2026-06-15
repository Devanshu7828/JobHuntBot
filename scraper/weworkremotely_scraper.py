"""We Work Remotely — HTML search for remote jobs."""
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from scraper.base_scraper import BaseScraper, Job
from scraper.keyword_utils import search_terms


class WeWorkRemotelyScraper(BaseScraper):

    BASE_URL = "https://weworkremotely.com"

    def scrape(self) -> list:
        jobs = []
        seen = set()
        for keyword in search_terms(self.keywords)[:4]:
            self.log(f"Searching: '{keyword}'")
            fetched = self._search(keyword)
            for job in fetched:
                if job.url not in seen:
                    seen.add(job.url)
                    jobs.append(job)
            self.random_delay(2, 3)
            if len(jobs) >= self.max_jobs:
                break

        self.log(f"Total jobs found: {len(jobs)}")
        return jobs[: self.max_jobs]

    def _search(self, keyword: str) -> list:
        params = urllib.parse.urlencode({"term": keyword})
        url = f"{self.BASE_URL}/remote-jobs/search?{params}"
        try:
            response = requests.get(
                url, headers=self.get_headers(), timeout=20, verify=self.get_verify_ssl()
            )
            response.raise_for_status()
            return self._parse(response.text)
        except Exception as e:
            self.log(f"Error fetching WWR jobs: {e}")
            return []

    def _parse(self, html: str) -> list:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        for card in soup.select("li.new-listing-container"):
            try:
                title_tag = card.select_one("span.new-listing__header__title__text")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                if not title or title.lower() in ("promoted", "view jobs"):
                    continue

                company = ""
                for span in card.select("span"):
                    cls = " ".join(span.get("class", []))
                    if "company" in cls and "title" not in cls:
                        company = span.get_text(strip=True)
                        break
                if not company:
                    parts = card.get_text(" | ", strip=True).split(" | ")
                    for i, part in enumerate(parts):
                        if part == title and i + 1 < len(parts):
                            company = parts[i + 1]
                            break

                region = card.select_one("span.region")
                location = region.get_text(strip=True) if region else "Remote"

                link = card.find("a", href=re.compile(r"^/company/"))
                job_url = f"{self.BASE_URL}{link['href']}" if link else self.BASE_URL

                jobs.append(Job(
                    title=title,
                    company=company,
                    location=location,
                    url=job_url,
                    platform="We Work Remotely",
                ))
            except Exception as e:
                self.log(f"Error parsing WWR card: {e}")

        return jobs

"""
LinkedIn job scraper — uses LinkedIn's public jobs search (no login needed).
"""
import requests
from bs4 import BeautifulSoup
from scraper.base_scraper import BaseScraper, Job
import urllib.parse


class LinkedInScraper(BaseScraper):

    BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def scrape(self) -> list:
        jobs = []
        for keyword in self.keywords[:3]:
            for location in self.locations[:3]:
                self.log(f"Searching: '{keyword}' in '{location}'")
                fetched = self._search(keyword, location)
                jobs.extend(fetched)
                self.random_delay(2, 4)
                if len(jobs) >= self.max_jobs:
                    break
            if len(jobs) >= self.max_jobs:
                break
        self.log(f"Total jobs found: {len(jobs)}")
        return jobs[:self.max_jobs]

    def _search(self, keyword: str, location: str) -> list:
        params = {
            "keywords": keyword,
            "location": location,
            "f_TPR": "r604800",   # last 7 days
            "f_E": "3,4",         # associate + mid-senior level
            "start": 0,
            "count": 25,
        }
        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"
        try:
            response = requests.get(
                url, headers=self.get_headers(), timeout=15, verify=self.get_verify_ssl()
            )
            response.raise_for_status()
            return self._parse(response.text)
        except Exception as e:
            self.log(f"Error fetching LinkedIn jobs: {e}")
            return []

    def _parse(self, html: str) -> list:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []
        job_cards = soup.find_all("div", class_="base-card")

        for card in job_cards:
            try:
                title_tag = card.find("h3", class_="base-search-card__title")
                title = title_tag.get_text(strip=True) if title_tag else ""

                company_tag = card.find("h4", class_="base-search-card__subtitle")
                company = company_tag.get_text(strip=True) if company_tag else ""

                loc_tag = card.find("span", class_="job-search-card__location")
                location = loc_tag.get_text(strip=True) if loc_tag else ""

                link_tag = card.find("a", class_="base-card__full-link")
                url = link_tag.get("href", "").split("?")[0] if link_tag else ""

                date_tag = card.find("time")
                posted_date = date_tag.get("datetime", "") if date_tag else ""

                job_id = url.split("-")[-1] if url else ""

                if title:
                    jobs.append(Job(
                        title=title,
                        company=company,
                        location=location,
                        url=url,
                        platform="LinkedIn",
                        posted_date=posted_date,
                        job_id=job_id
                    ))
            except Exception as e:
                self.log(f"Error parsing LinkedIn card: {e}")

        return jobs

"""
Indeed India job scraper — uses BeautifulSoup to parse search results.
"""
import requests
from bs4 import BeautifulSoup
from scraper.base_scraper import BaseScraper, Job
import urllib.parse


class IndeedScraper(BaseScraper):

    BASE_URL = "https://in.indeed.com/jobs"

    def scrape(self) -> list:
        jobs = []
        for keyword in self.keywords[:3]:  # limit to top 3 keywords for Indeed
            for location in self.locations[:3]:
                self.log(f"Searching: '{keyword}' in '{location}'")
                fetched = self._search(keyword, location)
                jobs.extend(fetched)
                self.random_delay(3, 5)
                if len(jobs) >= self.max_jobs:
                    break
            if len(jobs) >= self.max_jobs:
                break
        self.log(f"Total jobs found: {len(jobs)}")
        return jobs[:self.max_jobs]

    def _search(self, keyword: str, location: str) -> list:
        params = {
            "q": keyword,
            "l": location,
            "fromage": 14,  # last 14 days
            "sort": "date",
        }
        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"
        try:
            response = requests.get(
                url, headers=self.get_headers(), timeout=15, verify=self.get_verify_ssl()
            )
            response.raise_for_status()
            return self._parse(response.text, keyword, location)
        except Exception as e:
            self.log(f"Error fetching Indeed jobs: {e}")
            return []

    def _parse(self, html: str, keyword: str, location: str) -> list:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []
        job_cards = soup.find_all("div", class_="job_seen_beacon")

        for card in job_cards:
            try:
                # Indeed changed h2 → h3 for job titles in 2024–2025 layout
                title_tag = card.select_one("h2.jobTitle, h3.jobTitle, a.jcs-JobTitle")
                title = ""
                if title_tag:
                    span = title_tag.select_one("span[title]")
                    title = (span.get("title") or span.get_text(strip=True)) if span else title_tag.get_text(strip=True)

                company_tag = (
                    card.select_one("[data-testid='company-name']")
                    or card.select_one("span.css-1h7lukg")
                    or card.select_one("span.companyName")
                )
                company = company_tag.get_text(strip=True) if company_tag else ""

                loc_tag = (
                    card.select_one("[data-testid='text-location']")
                    or card.select_one("div.companyLocation")
                )
                job_location = loc_tag.get_text(strip=True) if loc_tag else location

                salary_tag = card.select_one(".salary-snippet-container, .salaryOnly, [data-testid='attribute_snippet_testid']")
                salary = salary_tag.get_text(strip=True) if salary_tag else "Not disclosed"

                link_tag = card.select_one("a[data-jk], a.jcs-JobTitle")
                job_id = link_tag.get("data-jk", "") if link_tag else ""
                job_url = f"https://in.indeed.com/viewjob?jk={job_id}" if job_id else ""

                snippet_tag = card.select_one(".job-snippet, [data-testid='job-snippet']")
                description = snippet_tag.get_text(strip=True) if snippet_tag else ""

                if title:
                    jobs.append(Job(
                        title=title,
                        company=company,
                        location=job_location,
                        url=job_url,
                        platform="Indeed",
                        description=description,
                        salary=salary,
                        job_id=job_id
                    ))
            except Exception as e:
                self.log(f"Error parsing Indeed card: {e}")

        return jobs

"""Foundit.in (formerly Monster India) — middleware JSON API."""
import requests
from scraper.base_scraper import BaseScraper, Job


class FounditScraper(BaseScraper):

    API_URL = "https://www.foundit.in/middleware/jobsearch"
    BASE_URL = "https://www.foundit.in"

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
                self.random_delay(1, 2)
                if len(jobs) >= self.max_jobs:
                    break
            if len(jobs) >= self.max_jobs:
                break

        self.log(f"Total jobs found: {len(jobs)}")
        return jobs[: self.max_jobs]

    def _max_kw(self) -> int:
        return self.config.get("platforms", {}).get("foundit", {}).get("max_keywords", 3)

    def _max_loc(self) -> int:
        return self.config.get("platforms", {}).get("foundit", {}).get("max_locations", 3)

    def _search(self, keyword: str, location: str) -> list:
        params = {"sort": 1, "limit": 20, "query": keyword, "locations": location}
        headers = {
            **self.get_headers(),
            "Accept": "application/json",
            "Referer": f"{self.BASE_URL}/srp/results?query={keyword}&locations={location}",
        }
        try:
            response = requests.get(
                self.API_URL, params=params, headers=headers,
                timeout=20, verify=self.get_verify_ssl(),
            )
            response.raise_for_status()
            payload = response.json()
            items = payload.get("jobSearchResponse", {}).get("data", [])
            return self._parse_items(items)
        except Exception as e:
            self.log(f"Error fetching Foundit jobs: {e}")
            return []

    def _parse_items(self, items: list) -> list:
        jobs = []
        for item in items:
            try:
                title = item.get("title", "")
                company = item.get("companyName", "")
                job_id = str(item.get("jobId") or item.get("id") or "")
                job_url = item.get("seoJdUrl") or item.get("jdUrl") or item.get("redirectUrl") or ""
                if job_url and not job_url.startswith("http"):
                    job_url = f"{self.BASE_URL}{job_url}"

                locations = item.get("locations") or []
                job_location = ", ".join(locations) if isinstance(locations, list) else str(locations)

                exp = item.get("exp") or ""
                if not exp:
                    min_exp = item.get("minimumExperience")
                    max_exp = item.get("maximumExperience")
                    if min_exp is not None and max_exp is not None:
                        exp = f"{min_exp}-{max_exp} yrs"

                salary = item.get("salary") or "Not disclosed"
                skills = item.get("skills") or []

                if title:
                    jobs.append(Job(
                        title=title,
                        company=company,
                        location=job_location,
                        url=job_url,
                        platform="Foundit",
                        description=item.get("jobDescription") or item.get("description") or item.get("jdText") or "",
                        salary=salary,
                        experience=exp,
                        skills=skills if isinstance(skills, list) else [],
                        job_id=job_id,
                    ))
            except Exception as e:
                self.log(f"Error parsing Foundit item: {e}")
        return jobs

"""Remotive.com — public JSON API for remote jobs."""
import requests
from scraper.base_scraper import BaseScraper, Job
from scraper.keyword_utils import matches_job_text


class RemotiveScraper(BaseScraper):

    API_URL = "https://remotive.com/api/remote-jobs"

    def scrape(self) -> list:
        jobs = []
        try:
            response = requests.get(
                self.API_URL,
                headers=self.get_headers(),
                timeout=20,
                verify=self.get_verify_ssl(),
            )
            response.raise_for_status()
            payload = response.json()
            all_jobs = payload.get("jobs", [])
            for item in all_jobs:
                title = item.get("title", "")
                text = f"{title} {item.get('category', '')} {' '.join(item.get('tags', []))} {item.get('description', '')[:300]}"
                if self.keywords and not matches_job_text(text, self.keywords):
                    continue
                jobs.append(Job(
                    title=title,
                    company=item.get("company_name", ""),
                    location=item.get("candidate_required_location", "Remote") or "Remote",
                    url=item.get("url", ""),
                    platform="Remotive",
                    description=item.get("description", "")[:2000],
                    salary=item.get("salary") or "Not disclosed",
                    job_id=str(item.get("id", "")),
                    posted_date=(item.get("publication_date") or "")[:10],
                ))
                if len(jobs) >= self.max_jobs:
                    break
        except Exception as e:
            self.log(f"Error fetching Remotive jobs: {e}")

        self.log(f"Total jobs found: {len(jobs)}")
        return jobs[: self.max_jobs]

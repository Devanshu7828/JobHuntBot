"""RemoteOK.com — public JSON API for remote jobs."""
import requests
from scraper.base_scraper import BaseScraper, Job
from scraper.keyword_utils import matches_job_text


class RemoteOKScraper(BaseScraper):

    API_URL = "https://remoteok.com/api"

    def scrape(self) -> list:
        jobs = []
        try:
            response = requests.get(
                self.API_URL,
                headers={**self.get_headers(), "User-Agent": "JobHuntBot/1.0 (job search assistant)"},
                timeout=20,
                verify=self.get_verify_ssl(),
            )
            response.raise_for_status()
            payload = response.json()
            for item in payload:
                if not isinstance(item, dict) or not item.get("position"):
                    continue
                title = item.get("position", "")
                tags = item.get("tags") or []
                text = f"{title} {' '.join(tags)} {item.get('description', '')[:500]}"
                if self.keywords and not matches_job_text(text, self.keywords):
                    continue

                job_url = item.get("url") or item.get("apply_url") or ""
                if job_url and not job_url.startswith("http"):
                    job_url = f"https://remoteok.com{job_url}"

                salary = "Not disclosed"
                if item.get("salary_min") or item.get("salary_max"):
                    salary = f"{item.get('salary_min', '')}-{item.get('salary_max', '')}"

                jobs.append(Job(
                    title=title,
                    company=item.get("company", ""),
                    location=item.get("location") or "Remote",
                    url=job_url,
                    platform="RemoteOK",
                    description=(item.get("description") or "")[:2000],
                    salary=salary,
                    job_id=str(item.get("id", "")),
                    posted_date=(item.get("date") or "")[:10],
                    skills=tags if isinstance(tags, list) else [],
                ))
                if len(jobs) >= self.max_jobs:
                    break
        except Exception as e:
            self.log(f"Error fetching RemoteOK jobs: {e}")

        self.log(f"Total jobs found: {len(jobs)}")
        return jobs[: self.max_jobs]

"""
Base scraper — all platform scrapers inherit from this.
Handles common browser setup, request headers, retries.
"""
import time
import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Job:
    """Represents a single job listing."""
    title: str
    company: str
    location: str
    url: str
    platform: str
    description: str = ""
    salary: str = "Not disclosed"
    experience: str = ""
    skills: list = field(default_factory=list)
    posted_date: str = ""
    job_id: str = ""
    match_score: int = 0
    matched_skills: list = field(default_factory=list)
    missing_skills: list = field(default_factory=list)

    def to_dict(self):
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "platform": self.platform,
            "description": self.description,
            "salary": self.salary,
            "experience": self.experience,
            "skills": self.skills,
            "posted_date": self.posted_date,
            "job_id": self.job_id,
            "match_score": self.match_score,
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills
        }


class BaseScraper:
    """Base class for all job scrapers."""

    # Rotate user agents to avoid detection
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    ]

    def __init__(self, config: dict):
        self.config = config
        self.keywords = config["search"]["keywords"]
        self.locations = config["search"]["locations"]
        self.max_jobs = config["search"]["max_jobs_per_platform"]
        self.verify_ssl = config.get("verify_ssl", True)
        self.jobs = []

    def get_verify_ssl(self) -> bool:
        """Return whether to verify SSL certs (disable on corporate networks)."""
        return self.verify_ssl

    def get_headers(self):
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            # Omit "br" — requests cannot decode Brotli without brotli/brotlicffi installed
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def random_delay(self, min_sec=1, max_sec=3):
        """Polite delay between requests to avoid rate limiting."""
        time.sleep(random.uniform(min_sec, max_sec))

    def scrape(self) -> list:
        """Override in each platform scraper. Returns list of Job objects."""
        raise NotImplementedError("Each scraper must implement scrape()")

    def log(self, message: str):
        print(f"[{self.__class__.__name__}] {message}")

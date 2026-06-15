"""Probe Shine job card structure."""
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Encoding": "gzip, deflate",
}

r = requests.get("https://www.shine.com/job-search/qa-automation-jobs-in-pune", headers=HEADERS, timeout=20, verify=False)
soup = BeautifulSoup(r.text, "html.parser")

# Job detail links
job_links = soup.select('a[href*="/jobs/"]')
print("Shine /jobs/ links:", len(job_links))
for a in job_links[:5]:
    if "/job-search/" in a.get("href", ""):
        continue
    print(" ", a.get_text(" ", strip=True)[:60], a.get("href", "")[:90])

# WWR structure
r2 = requests.get("https://weworkremotely.com/categories/remote-qa-jobs", headers=HEADERS, timeout=20, verify=False)
soup2 = BeautifulSoup(r2.text, "html.parser")
for item in soup2.select("li.new-listing-container")[:3]:
    title = item.select_one("span.title")
    company = item.select_one("span.company")
    region = item.select_one("span.region")
    link = item.select_one("a[href]")
    print("WWR:", title.get_text(strip=True) if title else "?",
          "|", company.get_text(strip=True) if company else "?",
          "|", link.get("href") if link else "?")

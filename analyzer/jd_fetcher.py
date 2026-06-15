"""
Fetch full job descriptions when scrapers only return title/location.
"""
import re
import requests
from bs4 import BeautifulSoup


def enrich_job_description(job, verify_ssl: bool = True, timeout: int = 15, config: dict = None) -> str:
    """Return description text — fetch from URL if missing on the job object."""
    if job.description and len(job.description.strip()) > 80:
        return job.description.strip()

    fetched = ""
    platform = (job.platform or "").lower()
    url = job.url or ""

    try:
        if "linkedin" in platform:
            fetched = _fetch_linkedin(job, verify_ssl, timeout)
        elif "naukri" in platform:
            fetched = _fetch_naukri(url, verify_ssl, timeout, config)
        elif "indeed" in platform:
            fetched = _fetch_indeed(url, verify_ssl, timeout)
        elif "foundit" in platform or "monster" in platform:
            fetched = _fetch_foundit(job, verify_ssl, timeout)
        elif url:
            fetched = _fetch_generic(url, verify_ssl, timeout)
    except Exception:
        fetched = ""

    if fetched:
        job.description = fetched[:4000]
    elif not job.description:
        # Synthetic JD from title + skills for tailoring when fetch fails
        job.description = _synthetic_jd(job)

    return job.description


def _headers():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    }


def _linkedin_job_id(job) -> str:
    if job.job_id and str(job.job_id).isdigit():
        return str(job.job_id)
    url = job.url or ""
    m = re.search(r"(\d{8,})", url)
    return m.group(1) if m else ""


def _fetch_linkedin(job, verify_ssl: bool, timeout: int) -> str:
    job_id = _linkedin_job_id(job)
    if not job_id:
        return ""
    api = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    r = requests.get(api, headers=_headers(), timeout=timeout, verify=verify_ssl)
    if r.status_code != 200:
        return ""
    soup = BeautifulSoup(r.text, "html.parser")
    desc = soup.select_one("div.description, div.show-more-less-html__markup, article")
    if desc:
        return desc.get_text(" ", strip=True)
    return soup.get_text(" ", strip=True)[:3000]


def _parse_naukri_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for sel in [
        "div.job-description",
        "div.dang-inner-html",
        "section.job-desc",
        "div[class*='jobDescription']",
        "div.styles_jd-desc__",
    ]:
        tag = soup.select_one(sel)
        if tag:
            text = tag.get_text(" ", strip=True)
            if len(text) > 50:
                return text
    return ""


def _fetch_naukri(url: str, verify_ssl: bool, timeout: int, config: dict = None) -> str:
    if not url:
        return ""
    r = requests.get(url, headers=_headers(), timeout=timeout, verify=verify_ssl)
    if r.status_code == 200:
        text = _parse_naukri_html(r.text)
        if text:
            return text
    return _fetch_naukri_playwright(url, config)


def _fetch_naukri_playwright(url: str, config: dict = None) -> str:
    """Naukri often blocks plain HTTP — use Edge via Playwright as fallback."""
    try:
        from playwright.sync_api import sync_playwright
        from scraper.playwright_utils import launch_browser, new_stealth_context, get_platform_cfg
    except ImportError:
        return ""

    cfg = config or {}
    naukri_cfg = get_platform_cfg(cfg, "naukri")
    timeout_ms = naukri_cfg.get("page_timeout_ms", 30000)

    try:
        with sync_playwright() as pw:
            browser, _ = launch_browser(pw, cfg, "naukri")
            context = new_stealth_context(browser, cfg, "naukri")
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(1500)
            html = page.content()
            browser.close()
            return _parse_naukri_html(html)
    except Exception:
        return ""


def _fetch_indeed(url: str, verify_ssl: bool, timeout: int) -> str:
    if not url:
        return ""
    r = requests.get(url, headers=_headers(), timeout=timeout, verify=verify_ssl)
    if r.status_code != 200:
        return ""
    soup = BeautifulSoup(r.text, "html.parser")
    tag = soup.select_one("#jobDescriptionText, div.jobsearch-JobComponent-description")
    return tag.get_text(" ", strip=True) if tag else ""


def _fetch_foundit(job, verify_ssl: bool, timeout: int) -> str:
    job_id = job.job_id or ""
    if not job_id:
        m = re.search(r"(\d{6,})", job.url or "")
        job_id = m.group(1) if m else ""
    if not job_id:
        return ""
    api = f"https://www.foundit.in/middleware/jobdetail/{job_id}"
    headers = {**_headers(), "Accept": "application/json", "Referer": "https://www.foundit.in/"}
    r = requests.get(api, headers=headers, timeout=timeout, verify=verify_ssl)
    if r.status_code != 200:
        return ""
    data = r.json()
    detail = data.get("jobDetailResponse", data.get("data", data))
    if isinstance(detail, dict):
        return (
            detail.get("description")
            or detail.get("jobDescription")
            or detail.get("jdText")
            or ""
        )
    return ""


def _fetch_generic(url: str, verify_ssl: bool, timeout: int) -> str:
    r = requests.get(url, headers=_headers(), timeout=timeout, verify=verify_ssl)
    if r.status_code != 200:
        return ""
    soup = BeautifulSoup(r.text, "html.parser")
    for sel in [
        "[class*='description']",
        "[class*='job-desc']",
        "article",
        "main",
    ]:
        tag = soup.select_one(sel)
        if tag:
            text = tag.get_text(" ", strip=True)
            if len(text) > 100:
                return text[:3000]
    return ""


def _synthetic_jd(job) -> str:
    parts = [
        job.title,
        job.company,
        job.location,
        job.experience,
        " ".join(job.skills or []),
        " ".join(job.matched_skills or []),
    ]
    return " ".join(p for p in parts if p).strip()

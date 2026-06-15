"""
Salary filter — parse Indian job salaries (LPA / lakhs / annual INR) and
keep jobs whose disclosed range overlaps the configured band.
"""
import re
from typing import Optional, Tuple


def _to_lpa(amount: float) -> float:
    """Convert parsed amount to lakhs per annum."""
    if amount >= 100000:  # annual INR (e.g. 1400000)
        return amount / 100000.0
    return amount  # already in lakhs


def parse_salary_range(text: str) -> Optional[Tuple[float, float]]:
    """
    Parse min/max LPA from salary strings or JD snippets.
    Returns (min_lpa, max_lpa) or None if not parseable.
    """
    if not text:
        return None

    raw = text.strip().lower()
    if not raw or raw in {"not disclosed", "n/a", "na", "0-0 inr", "undisclosed"}:
        return None
    if "not disclosed" in raw and not re.search(r"\d", raw):
        return None

    # Explicit LPA / Lacs / Lakhs (e.g. "14-20 LPA", "18-33 Lacs PA")
    for pattern in [
        r"(\d+(?:\.\d+)?)\s*[-–to]+\s*(\d+(?:\.\d+)?)\s*(?:lpa|lac|lakh|lacs|lakhs)",
        r"(\d+(?:\.\d+)?)\s*(?:lpa|lac|lakh|lacs|lakhs)\s*[-–to]+\s*(\d+(?:\.\d+)?)\s*(?:lpa|lac|lakh|lacs|lakhs)",
        r"(\d+(?:\.\d+)?)\s*[-–to]+\s*(\d+(?:\.\d+)?)\s*(?:lpa|lac|lakh|lacs|lakhs)\s*pa",
    ]:
        m = re.search(pattern, raw)
        if m:
            return float(m.group(1)), float(m.group(2))

    # Single LPA value
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:lpa|lac|lakh|lacs|lakhs)", raw)
    if m:
        v = float(m.group(1))
        return v, v

    # INR annual with rupee symbol or commas (₹14,00,000 - ₹20,00,000)
    amounts = []
    for token in re.findall(r"₹?\s*([\d,]+(?:\.\d+)?)", raw):
        try:
            amounts.append(float(token.replace(",", "")))
        except ValueError:
            continue
    if len(amounts) >= 2:
        a, b = _to_lpa(amounts[0]), _to_lpa(amounts[1])
        return min(a, b), max(a, b)
    if len(amounts) == 1:
        v = _to_lpa(amounts[0])
        if v >= 3:  # ignore tiny noise values
            return v, v

    return None


def job_salary_range(job) -> Optional[Tuple[float, float]]:
    """Parse salary from the listing field only (not full JD text)."""
    salary = (getattr(job, "salary", "") or "").strip()
    if not salary:
        return None
    return parse_salary_range(salary)


def salary_overlaps_band(
    job_range: Tuple[float, float],
    min_lpa: float,
    max_lpa: float,
) -> bool:
    """True when job salary range overlaps [min_lpa, max_lpa]."""
    job_min, job_max = job_range
    return job_min <= max_lpa and job_max >= min_lpa


def filter_by_salary(jobs: list, config: dict) -> list:
    """Filter jobs to configured LPA band."""
    search = config.get("search", {})
    sf = search.get("salary_filter", {})
    if not sf.get("enabled", False):
        return jobs

    min_lpa = float(sf.get("min_lpa", 14))
    max_lpa = float(sf.get("max_lpa", 20))
    include_undisclosed = sf.get("include_undisclosed", True)

    kept = []
    for job in jobs:
        parsed = job_salary_range(job)
        if parsed is None:
            if include_undisclosed:
                kept.append(job)
            continue
        if salary_overlaps_band(parsed, min_lpa, max_lpa):
            kept.append(job)
    return kept

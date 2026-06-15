"""
Dry-run validation — test each job portal scraper individually.
Usage: py scripts/test_all_scrapers.py
"""
import os
import sys
import warnings

import yaml

warnings.filterwarnings("ignore")
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())

from main import SCRAPER_MAP, load_config  # noqa: E402


def main():
    config = load_config()
    # Keep tests fast
    config["search"]["max_jobs_per_platform"] = 10
    for name in SCRAPER_MAP:
        cfg = config["platforms"].setdefault(name, {})
        cfg.setdefault("max_keywords", 1)
        cfg.setdefault("max_locations", 1)
    config["search"]["keywords"] = config["search"]["keywords"][:1]
    config["search"]["locations"] = config["search"]["locations"][:1]

    print("=" * 60)
    print("JobHuntBot — Scraper Dry Run")
    print("=" * 60)

    results = []
    for name, ScraperClass in SCRAPER_MAP.items():
        enabled = config["platforms"].get(name, {}).get("enabled", True)
        if not enabled:
            print(f"[SKIP] {name:16s} disabled in config")
            results.append((name, "SKIP", 0))
            continue
        try:
            jobs = ScraperClass(config).scrape()
            status = "OK" if jobs else "WARN (0 jobs)"
            print(f"[{status.split()[0]:4s}] {name:16s} -> {len(jobs)} jobs")
            for j in jobs[:2]:
                print(f"       • {j.title[:50]} @ {j.company[:30]}")
            results.append((name, status, len(jobs)))
        except Exception as e:
            print(f"[FAIL] {name:16s} -> {e}")
            results.append((name, "FAIL", 0))

    print("=" * 60)
    ok = sum(1 for _, s, n in results if s == "OK" or (s.startswith("WARN") and n >= 0))
    with_jobs = sum(1 for _, _, n in results if n > 0)
    print(f"Platforms tested: {len(results)} | Returning jobs: {with_jobs}")
    print("=" * 60)
    return 0 if with_jobs >= 5 else 1


if __name__ == "__main__":
    raise SystemExit(main())

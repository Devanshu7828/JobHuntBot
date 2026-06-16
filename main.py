"""
JobHuntBot — Main Pipeline Orchestrator
═══════════════════════════════════════

Daily workflow:
  1. Scrape jobs from all enabled platforms
  2. Deduplicate (against DB + within run)
  3. Score each job against your skills
  4. Tailor resume per high-match job (EthicsGuard validated)
  5. Generate cover letter per high-match job
  6. Render PDFs (resume + cover letter)
  7. Persist everything in SQLite
  8. Generate HTML report
  9. Open report in browser

Usage:
  python main.py                       # full run
  python main.py --platform naukri     # single platform
  python main.py --dry-run             # use saved jobs, skip scraping
  python main.py --min-score 60        # override min match
  python main.py --no-pdf              # skip PDF generation (faster)
  python main.py --tailor-top 10       # tailor only top N jobs
"""
import os
import sys
import json
import argparse
import webbrowser
from datetime import date, datetime

import yaml
import urllib3

from scraper.naukri_scraper import NaukriScraper
from scraper.linkedin_scraper import LinkedInScraper
from scraper.indeed_scraper import IndeedScraper
from scraper.hirist_scraper import HiristScraper
from scraper.instahyre_scraper import InstahyreScraper
from scraper.shine_scraper import ShineScraper
from scraper.foundit_scraper import FounditScraper
from scraper.wellfound_scraper import WellfoundScraper
from scraper.remotive_scraper import RemotiveScraper
from scraper.remoteok_scraper import RemoteOKScraper
from scraper.weworkremotely_scraper import WeWorkRemotelyScraper
from scraper.base_scraper import Job
from analyzer.jd_scorer import JDScorer
from analyzer.jd_fetcher import enrich_job_description
from analyzer.salary_filter import filter_by_salary
from analyzer.resume_tailor import ResumeTailor
from analyzer.cover_letter import generate_cover_letter
from rendering.resume_pdf import render_resume_pdf, render_cover_letter_pdf
from report.report_generator import generate_report
from persistence import database as db
from utils.logger import get_logger


log = get_logger("pipeline")


# ───────────────────────────────────────────────────────────────────────────
# CONFIG
# ───────────────────────────────────────────────────────────────────────────

def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_base_resume(config: dict) -> dict:
    path = config["resume"]["base_resume_path"]
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ───────────────────────────────────────────────────────────────────────────
# DISCOVERY
# ───────────────────────────────────────────────────────────────────────────

SCRAPER_MAP = {
    "naukri":            NaukriScraper,
    "linkedin":          LinkedInScraper,
    "indeed":            IndeedScraper,
    "hirist":            HiristScraper,
    "instahyre":         InstahyreScraper,
    "shine":             ShineScraper,
    "foundit":           FounditScraper,
    "wellfound":         WellfoundScraper,
    "remotive":          RemotiveScraper,
    "remoteok":          RemoteOKScraper,
    "weworkremotely":    WeWorkRemotelyScraper,
}


def run_scrapers(config: dict, platform_filter: str = None) -> list:
    all_jobs = []
    for name, ScraperClass in SCRAPER_MAP.items():
        if not config["platforms"].get(name, {}).get("enabled", True):
            log.info(f"[SKIP] {name} — disabled in config")
            continue
        if platform_filter and name != platform_filter:
            continue

        log.info(f"━━━ Scraping {name.upper()} ━━━")
        started = datetime.utcnow().isoformat()
        try:
            scraper = ScraperClass(config)
            jobs = scraper.scrape()
            log.info(f"   ✓ {name}: found {len(jobs)} jobs")
            all_jobs.extend(jobs)
            db.log_scrape_run(name, started, datetime.utcnow().isoformat(),
                              len(jobs), [], "SUCCESS")
        except Exception as e:
            log.error(f"   ✗ {name} scraper failed: {e}")
            db.log_scrape_run(name, started, datetime.utcnow().isoformat(),
                              0, [str(e)], "FAILED")
    return all_jobs


# ───────────────────────────────────────────────────────────────────────────
# DEDUPLICATION
# ───────────────────────────────────────────────────────────────────────────

def _is_job_specific_resume(resume_path: str, master_resume_pdf: str = "") -> bool:
    """True when the PDF is a per-job tailored file, not the shared master resume."""
    if not resume_path:
        return False
    if master_resume_pdf and os.path.normcase(os.path.abspath(resume_path)) == os.path.normcase(
        os.path.abspath(master_resume_pdf)
    ):
        return False
    normalized = resume_path.replace("\\", "/").lower()
    return "/resumes/" in normalized or normalized.endswith("_resume.pdf")


def deduplicate(jobs: list) -> list:
    """Remove duplicates within the current run (DB dedup happens at save)."""
    seen = set()
    unique = []
    for job in jobs:
        key = f"{job.title.lower().strip()}|{job.company.lower().strip()}"
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


# ───────────────────────────────────────────────────────────────────────────
# TAILORING (PER JOB)
# ───────────────────────────────────────────────────────────────────────────

def tailor_for_job(job, tailor: ResumeTailor, candidate: dict, base_resume: dict,
                   make_pdf: bool = True, master_resume_pdf: str = "",
                   resume_cfg: dict = None) -> dict:
    """
    Tailor resume + cover letter for a single job.
    Returns dict with paths and ethics status.
    """
    resume_cfg = resume_cfg or {}
    resume_dir = resume_cfg.get("output_dir", "output/resumes")
    cover_dir = resume_cfg.get("cover_letter_dir") or resume_dir.replace(
        "/resumes", "/cover_letters"
    ).replace("\\resumes", "\\cover_letters")
    os.makedirs(resume_dir, exist_ok=True)
    os.makedirs(cover_dir, exist_ok=True)

    safe_company = "".join(c if c.isalnum() else "_" for c in job.company)[:30]
    safe_title   = "".join(c if c.isalnum() else "_" for c in job.title)[:40]
    file_stem = f"{safe_company}_{safe_title}_{date.today().isoformat()}"

    resume_pdf_path  = os.path.join(resume_dir, f"{file_stem}_Resume.pdf")
    cover_pdf_path   = os.path.join(cover_dir, f"{file_stem}_CoverLetter.pdf")
    cover_txt_path   = os.path.join(cover_dir, f"{file_stem}_CoverLetter.txt")

    # Resume tailoring
    tailored, ethics_ok, violations = tailor.tailor(job, base_resume)

    # Cover letter
    letter_text = generate_cover_letter(job, candidate, base_resume,
                                         output_path=cover_txt_path)

    # PDFs
    if make_pdf:
        try:
            render_resume_pdf(tailored, resume_pdf_path)
            render_cover_letter_pdf(letter_text, cover_pdf_path)
        except Exception as e:
            log.warning(f"PDF rendering failed for {job.company}: {e}")
            resume_pdf_path = master_resume_pdf if master_resume_pdf else ""
            cover_pdf_path = ""
    elif master_resume_pdf:
        # No PDF generation — use your master ATS resume
        resume_pdf_path = master_resume_pdf

    return {
        "tailored": tailored,
        "ethics_passed": ethics_ok,
        "violations": violations,
        "resume_pdf": resume_pdf_path,
        "cover_pdf": cover_pdf_path,
        "cover_text": letter_text,
    }


# ───────────────────────────────────────────────────────────────────────────
# MAIN
# ───────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="JobHuntBot — QA Job Search Automation")
    parser.add_argument("--config", default="config.yaml",
                        help="Path to config YAML (e.g. profiles/poonam/config.yaml)")
    parser.add_argument("--platform", help="Single platform: naukri, linkedin, indeed, hirist, instahyre, shine, foundit, wellfound, remotive, remoteok, weworkremotely")
    parser.add_argument("--dry-run", action="store_true", help="Skip scraping, use saved data")
    parser.add_argument("--min-score", type=int, help="Override min match score")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation")
    parser.add_argument("--tailor-top", type=int, default=None,
                        help="Tailor top N jobs only (overrides tailor_all when set)")
    parser.add_argument("--no-tailor-all", action="store_true",
                        help="Only tailor top N jobs instead of every job in report")
    args = parser.parse_args()

    log.info("═" * 60)
    log.info("  JobHuntBot Pipeline Starting")
    log.info("═" * 60)

    # Load config
    config = load_config(args.config)
    log.info(f"Config: {args.config}")
    if not config.get("verify_ssl", True):
        urllib3.disable_warnings()
    import warnings
    warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)
    try:
        from requests import RequestsDependencyWarning
        warnings.filterwarnings("ignore", category=RequestsDependencyWarning)
    except ImportError:
        pass
    base_resume = load_base_resume(config)
    candidate = config["candidate"]
    master_resume_pdf = config.get("resume", {}).get("master_resume_pdf", "")
    if master_resume_pdf and not os.path.isfile(master_resume_pdf):
        log.warning(f"Master resume PDF not found: {master_resume_pdf}")
        master_resume_pdf = ""
    elif master_resume_pdf:
        log.info(f"Master resume: {master_resume_pdf}")
    min_score = args.min_score or config["scoring"]["min_score_to_include"]
    tailor_top = args.tailor_top if args.tailor_top is not None else config.get("resume", {}).get("tailor_top", 5)
    if args.no_tailor_all:
        config.setdefault("resume", {})["tailor_all"] = False

    # Init DB
    db.init_db()
    log.info(f"Database initialized: {db.DB_PATH}")

    # Step 1: Discovery
    if args.dry_run:
        log.info("[DRY RUN] Loading saved jobs from DB...")
        rows = db.get_recent_jobs(days=1)
        all_jobs = [
            Job(
                title=r["title"], company=r["company"], location=r["location"],
                url=r["url"], platform=r["source"], description=r["description"] or "",
                salary=r["salary"] or "Not disclosed", experience=r["experience"] or "",
                skills=json.loads(r["skills"] or "[]"),
                posted_date=r["posted_date"] or "",
                job_id=r["external_id"] or "",
                match_score=r["match_score"],
                matched_skills=json.loads(r["matched_skills"] or "[]"),
                missing_skills=json.loads(r["missing_skills"] or "[]"),
            )
            for r in rows
        ]
    else:
        all_jobs = run_scrapers(config, args.platform)

    log.info(f"Total raw jobs collected: {len(all_jobs)}")

    # Step 2: Deduplication (in-run + DB check)
    unique_jobs = deduplicate(all_jobs)
    log.info(f"After in-run dedup: {len(unique_jobs)}")

    fresh_jobs = []
    if not args.dry_run:
        fresh_jobs = [j for j in unique_jobs if not db.is_duplicate(j)]
        log.info(f"After DB dedup: {len(fresh_jobs)} new jobs")

    # Step 3: Score every job from this run (report is not limited to DB-new only)
    log.info("Scoring jobs against your profile...")
    scorer = JDScorer(config)
    scored = scorer.score_all(unique_jobs)
    filtered = scorer.filter_by_min_score(scored, min_score)
    log.info(f"Jobs above {min_score}% match: {len(filtered)}")

    # Step 3b: Salary band filter (14–20 LPA by default)
    sf = config.get("search", {}).get("salary_filter", {})
    if sf.get("enabled", False):
        before = len(filtered)
        filtered = filter_by_salary(filtered, config)
        log.info(
            f"After salary filter ({sf.get('min_lpa', 14)}-{sf.get('max_lpa', 20)} LPA): "
            f"{len(filtered)} (removed {before - len(filtered)})"
        )

    # Step 4: Persist only new jobs that pass the score threshold
    saved_count = 0
    job_db_ids = {}
    fresh_keys = {
        f"{j.title.lower().strip()}|{j.company.lower().strip()}" for j in fresh_jobs
    }
    for job in filtered:
        key = f"{job.title.lower().strip()}|{job.company.lower().strip()}"
        if args.dry_run or key in fresh_keys:
            row_id = db.save_job(job)
            if row_id:
                saved_count += 1
                job_db_ids[id(job)] = row_id
    log.info(f"Saved {saved_count} new jobs to DB")

    # Step 5: Tailor resumes for every job in the report (JD-aware PDFs)
    resume_cfg = config.get("resume", {})
    tailor_all = resume_cfg.get("tailor_all", True)
    tailor_max = resume_cfg.get("tailor_max", 50)
    fetch_jd = resume_cfg.get("fetch_job_descriptions", True)

    if tailor_all:
        jobs_to_tailor = filtered[:tailor_max]
        log.info(f"Tailoring resumes for all {len(jobs_to_tailor)} jobs in report (max {tailor_max})...")
    else:
        jobs_to_tailor = filtered[:tailor_top] if tailor_top > 0 else []
        log.info(f"Tailoring resumes for top {len(jobs_to_tailor)} jobs...")

    tailor = ResumeTailor(config["resume"]["base_resume_path"])
    tailored_results = {}

    for i, job in enumerate(jobs_to_tailor, 1):
        try:
            if fetch_jd:
                enrich_job_description(job, verify_ssl=config.get("verify_ssl", True), config=config)

            log.info(f"  [{i}/{len(jobs_to_tailor)}] {job.match_score}% | {job.company} — {job.title}")
            result = tailor_for_job(job, tailor, candidate, base_resume,
                                     make_pdf=not args.no_pdf,
                                     master_resume_pdf=master_resume_pdf,
                                     resume_cfg=resume_cfg)
            tailored_results[id(job)] = result

            # Track in DB
            db_job_id = job_db_ids.get(id(job))
            if db_job_id:
                db.save_resume_version(
                    db_job_id, result["tailored"], result["resume_pdf"],
                    result["ethics_passed"], result["violations"]
                )
                db.record_application(
                    db_job_id,
                    status="PENDING",
                    method="manual",  # smart-assist by default
                    resume_path=result["resume_pdf"],
                    cover_letter_path=result["cover_pdf"],
                )

            if not result["ethics_passed"]:
                log.warning(f"     ⚠ Ethics violations: {len(result['violations'])}")
        except Exception as e:
            log.error(f"     ✗ Tailoring failed: {e}")

    # Step 6: Generate HTML report
    log.info("Generating HTML dashboard...")
    today_str = date.today().strftime("%Y-%m-%d")
    report_dir = config["report"]["output_dir"]
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"JobReport_{today_str}.html")

    # Attach PDF paths — only mark as "tailored" when a job-specific PDF was generated
    for job in filtered:
        result = tailored_results.get(id(job))
        job.tailored_resume_path = ""
        job.master_resume_path = master_resume_pdf if master_resume_pdf else ""
        job.cover_letter_path = ""
        if result:
            resume_pdf = result.get("resume_pdf") or ""
            if resume_pdf and os.path.isfile(resume_pdf) and _is_job_specific_resume(resume_pdf, master_resume_pdf):
                job.tailored_resume_path = resume_pdf
            cover_pdf = result.get("cover_pdf") or ""
            if cover_pdf and os.path.isfile(cover_pdf):
                job.cover_letter_path = cover_pdf
            job.ethics_passed = result["ethics_passed"]

    generate_report(filtered, report_path, candidate["name"], master_resume_pdf=master_resume_pdf)

    # Step 7: Persist raw JSON for traceability
    raw_path = os.path.join(report_dir, f"jobs_{today_str}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump([j.to_dict() for j in filtered], f, indent=2, ensure_ascii=False)

    # Summary
    high = [j for j in filtered if j.match_score >= 75]
    stats = db.get_application_stats()

    log.info("═" * 60)
    log.info("  Pipeline Complete")
    log.info("═" * 60)
    log.info(f"  Total qualified jobs    : {len(filtered)}")
    log.info(f"  High-match (75%+)       : {len(high)}")
    log.info(f"  Tailored resumes        : {len(tailored_results)}")
    log.info(f"  Applications tracked    : {stats.get('PENDING', 0)} pending, "
             f"{stats.get('APPLIED', 0)} applied")
    log.info(f"  Report                  : {report_path}")
    log.info("═" * 60)

    if high:
        log.info("Top 5 matches:")
        for job in high[:5]:
            log.info(f"  {job.match_score}% | {job.title} @ {job.company}  ({job.platform})")

    if config["report"].get("open_browser_after_run", True):
        webbrowser.open(f"file:///{os.path.abspath(report_path)}")


if __name__ == "__main__":
    main()

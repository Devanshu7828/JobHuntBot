# JobHuntBot — Automated QA Job Discovery, Tailoring & Tracking

End-to-end pipeline that finds QA jobs across major portals, scores them against
your profile, generates **tailored resumes + cover letters** (with anti-fabrication
EthicsGuard), tracks applications in SQLite, and produces a daily HTML dashboard.

## What It Does Every Day

```
1. Scrapes:    Naukri + LinkedIn + Indeed → ~150-300 raw jobs
2. Dedups:     in-run + against your SQLite DB (no repeat applications)
3. Scores:     0-100% match using weighted skill/experience/location matrix
4. Tailors:    customizes summary + skill ordering per JD (EthicsGuard validated)
5. Generates:  per-job tailored resume PDF + cover letter PDF
6. Tracks:     applications in SQLite (status, dates, resume version)
7. Reports:    interactive HTML dashboard with filters and tailored PDFs
```

## Architecture

```
JobHuntBot/
├── main.py                    # Pipeline orchestrator
├── config.yaml                # Your search profile + scoring weights
│
├── scraper/                   # Discovery layer
│   ├── base_scraper.py
│   ├── naukri_scraper.py
│   ├── linkedin_scraper.py
│   └── indeed_scraper.py
│
├── analyzer/                  # Intelligence layer
│   ├── jd_scorer.py           # 0-100% match scoring
│   ├── resume_tailor.py       # JD-aware resume customization
│   ├── ethics_guard.py        # Anti-fabrication validator
│   └── cover_letter.py        # Template-based cover letter
│
├── rendering/                 # PDF rendering
│   └── resume_pdf.py          # reportlab-based, ATS-friendly
│
├── persistence/               # SQLite-backed tracking
│   └── database.py            # jobs / applications / resume versions
│
├── report/                    # HTML dashboard generator
│   └── report_generator.py
│
├── utils/
│   └── logger.py              # Centralized rotating logger
│
├── resume/
│   └── base_resume.json       # Your structured master resume
│
├── data/                      # SQLite database
├── output/                    # Generated PDFs + reports
├── logs/                      # Rotating logs
├── scripts/
│   ├── run_daily.bat          # Double-click to run manually
│   └── schedule_windows.ps1   # Register Windows scheduled task
│
└── .github/workflows/
    └── daily-run.yml          # GitHub Actions daily cron
```

## Setup

### 1. Install Python 3.11
Download from https://www.python.org/downloads/ — check **"Add Python to PATH"**.

### 2. Install dependencies
```powershell
cd "C:\Users\rajakd\OneDrive - AMDOCS\Desktop\JobHuntBot"
py -m pip install -r requirements.txt
py -m playwright install chromium
```

**Naukri** uses Playwright with your installed **Microsoft Edge** (`browser_channel: msedge` in `config.yaml`). Edge is already on Windows — no extra browser install needed. If Naukri shows "Access Denied", set `headless: false` under `platforms.naukri`.

### 3. Configure your profile

**Included profile (Poonam — Data Analyst):**
```powershell
py main.py --config profiles/poonam/config.yaml
```
Or double-click `profiles/poonam/run.bat`.

**Your own profile:** copy `config.example.yaml` → `config.yaml` and `resume/base_resume.example.json` → `resume/base_resume.json`, then edit both. Personal `config.yaml` and `resume/base_resume.json` are gitignored.

### 4. Run
```bash
py main.py --config profiles/poonam/config.yaml
# or, with your local config.yaml:
py main.py
```

The HTML report auto-opens in your browser. Tailored PDFs live in `output/resumes/`.

## Usage

```bash
# Full run (all platforms)
python main.py

# Single platform
python main.py --platform naukri

# Use yesterday's data (no scraping)
python main.py --dry-run

# Override min match score
python main.py --min-score 60

# Faster run (no PDF generation)
python main.py --no-pdf

# Tailor only top 10 jobs
python main.py --tailor-top 10
```

## Schedule Daily Runs (Windows)

```powershell
# Register a daily 7:00 AM task (run as Admin)
.\scripts\schedule_windows.ps1

# To trigger right now
schtasks /run /tn JobHuntBot

# To remove
schtasks /delete /tn JobHuntBot /f
```

## EthicsGuard — The Anti-Lying Layer

Every tailored resume is validated against the base resume:

| Rule | Severity | Action |
|------|----------|--------|
| Fabricated skill | CRITICAL | Rollback to safe base resume |
| New/fake company | CRITICAL | Rollback |
| Inflated experience years | CRITICAL | Rollback |
| Fake certification | HIGH | Rollback |
| Unverified metric ("increased by 300%") | MEDIUM | Logged warning |

If a tailored resume fails validation, the report shows a warning and the
system uses your **original truthful resume with skill reordering only**.

## How Scoring Works

| Factor | Weight |
|--------|--------|
| Primary skills (Selenium, Java, TestNG, REST Assured) | 50% |
| Secondary skills (UFT, ALM, STLC, etc.) | 20% |
| Experience range fit (3-6 years) | 20% |
| Location match (Pune / Remote / your prefs) | 10% |

Adjust weights in `config.yaml` → `scoring:` section.

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| LinkedIn anti-bot | Conservative scraping rates, no auto-login |
| Naukri ToS | Use public search API only, respect rate limits |
| Scraper HTML changes | Daily logs + `scrape_logs` table flag failures |
| LLM hallucination | We don't use LLM yet — template-only tailoring |
| Captcha | Skip captcha-blocked sites, route to manual queue |
| Account bans | This is **smart-assist**, not auto-apply: you click Submit |

## Roadmap

- [x] Phase 1 MVP: scrapers + scorer + report + SQLite
- [x] EthicsGuard validator
- [x] PDF resume + cover letter rendering
- [x] Application tracking DB
- [x] Windows + GitHub Actions scheduling
- [ ] Phase 2: spaCy-based JD parser (deeper skill extraction)
- [ ] Phase 3: Playwright scrapers for Glassdoor + Monster
- [ ] Phase 4: LLM-powered tailoring (Claude/GPT-4) with EthicsGuard kept
- [ ] Phase 5: Semi-auto submit for Greenhouse/Lever boards
- [ ] Phase 6: Response-rate analytics dashboard

## Daily Output

After each run you get:
- `output/jobs/JobReport_YYYY-MM-DD.html` — interactive dashboard
- `output/jobs/jobs_YYYY-MM-DD.json` — raw data
- `output/resumes/<Company>_<Title>_<Date>_Resume.pdf` — tailored resumes
- `output/cover_letters/<Company>_<Title>_<Date>_CoverLetter.pdf` — cover letters
- `data/job_bot.db` — SQLite tracking everything
- `logs/jobhunt_YYYY-MM-DD.log` — detailed run log

## Legal & Ethical Notes

- This is a **discovery + preparation** tool, not a mass auto-applier
- You review each application before clicking Submit
- Respects platform rate limits and ToS where possible
- EthicsGuard prevents the bot from ever lying on your resume
- For commercial use, review each platform's ToS independently

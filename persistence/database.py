"""
SQLite-backed persistence layer.

Tracks:
- jobs: every discovered job (deduplicated)
- applications: status of each application (PENDING/APPLIED/FAILED/MANUAL)
- resume_versions: tailored resume PDFs per job
- scrape_logs: run history with error tracking
"""
import sqlite3
import json
import os
from datetime import datetime
from contextlib import contextmanager
from typing import Optional


DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "job_bot.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,
    external_id     TEXT,
    title           TEXT NOT NULL,
    company         TEXT NOT NULL,
    location        TEXT,
    url             TEXT,
    description     TEXT,
    skills          TEXT,
    experience      TEXT,
    salary          TEXT,
    posted_date     TEXT,
    match_score     INTEGER DEFAULT 0,
    matched_skills  TEXT,
    missing_skills  TEXT,
    scraped_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_company_title ON jobs(company, title);
CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(match_score);
CREATE INDEX IF NOT EXISTS idx_jobs_scraped ON jobs(scraped_at);

CREATE TABLE IF NOT EXISTS applications (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id             INTEGER NOT NULL,
    status             TEXT NOT NULL DEFAULT 'PENDING',
    method             TEXT,
    resume_path        TEXT,
    cover_letter_path  TEXT,
    applied_at         TEXT,
    error_message      TEXT,
    response_status    TEXT DEFAULT 'no_response',
    notes              TEXT,
    created_at         TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at         TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES jobs(id),
    UNIQUE(job_id)
);

CREATE TABLE IF NOT EXISTS resume_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL,
    tailored_json   TEXT,
    pdf_path        TEXT,
    ethics_passed   INTEGER DEFAULT 1,
    violations      TEXT,
    generated_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS scrape_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT,
    started_at      TEXT,
    finished_at     TEXT,
    jobs_found      INTEGER DEFAULT 0,
    errors          TEXT,
    status          TEXT
);
"""


def init_db(db_path: str = DB_PATH):
    """Create database file and tables if they don't exist."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def get_conn(db_path: str = DB_PATH):
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─── Job operations ────────────────────────────────────────────────────────

def save_job(job, db_path: str = DB_PATH) -> Optional[int]:
    """Insert a job. Returns the row id, or None if duplicate."""
    with get_conn(db_path) as conn:
        try:
            cursor = conn.execute(
                """INSERT INTO jobs
                   (source, external_id, title, company, location, url, description,
                    skills, experience, salary, posted_date, match_score,
                    matched_skills, missing_skills)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job.platform,
                    job.job_id or f"{job.company}_{job.title}",
                    job.title,
                    job.company,
                    job.location,
                    job.url,
                    job.description,
                    json.dumps(job.skills) if job.skills else "[]",
                    job.experience,
                    job.salary,
                    job.posted_date,
                    job.match_score,
                    json.dumps(job.matched_skills) if job.matched_skills else "[]",
                    json.dumps(job.missing_skills) if job.missing_skills else "[]",
                ),
            )
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None


def is_duplicate(job, db_path: str = DB_PATH) -> bool:
    """Check if a job already exists by (company, title) fuzzy match."""
    with get_conn(db_path) as conn:
        row = conn.execute(
            """SELECT id FROM jobs
               WHERE LOWER(company) = LOWER(?)
               AND LOWER(title) = LOWER(?)
               LIMIT 1""",
            (job.company.strip(), job.title.strip()),
        ).fetchone()
        return row is not None


def get_recent_jobs(days: int = 7, db_path: str = DB_PATH) -> list:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM jobs
               WHERE scraped_at >= datetime('now', ?)
               ORDER BY match_score DESC""",
            (f"-{days} days",),
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Application operations ────────────────────────────────────────────────

def record_application(
    job_id: int,
    status: str = "PENDING",
    method: str = "manual",
    resume_path: str = "",
    cover_letter_path: str = "",
    error_message: str = "",
    db_path: str = DB_PATH,
) -> int:
    with get_conn(db_path) as conn:
        cursor = conn.execute(
            """INSERT OR REPLACE INTO applications
               (job_id, status, method, resume_path, cover_letter_path,
                applied_at, error_message, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                job_id,
                status,
                method,
                resume_path,
                cover_letter_path,
                datetime.utcnow().isoformat() if status == "APPLIED" else None,
                error_message,
            ),
        )
        return cursor.lastrowid


def update_application_status(job_id: int, status: str, db_path: str = DB_PATH):
    with get_conn(db_path) as conn:
        conn.execute(
            """UPDATE applications
               SET status = ?, updated_at = CURRENT_TIMESTAMP
               WHERE job_id = ?""",
            (status, job_id),
        )


def get_application_stats(db_path: str = DB_PATH) -> dict:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"""
        ).fetchall()
        return {row["status"]: row["cnt"] for row in rows}


# ─── Resume version tracking ───────────────────────────────────────────────

def save_resume_version(
    job_id: int,
    tailored_json: dict,
    pdf_path: str,
    ethics_passed: bool = True,
    violations: list = None,
    db_path: str = DB_PATH,
) -> int:
    with get_conn(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO resume_versions
               (job_id, tailored_json, pdf_path, ethics_passed, violations)
               VALUES (?, ?, ?, ?, ?)""",
            (
                job_id,
                json.dumps(tailored_json),
                pdf_path,
                1 if ethics_passed else 0,
                json.dumps(violations or []),
            ),
        )
        return cursor.lastrowid


# ─── Scrape logs ───────────────────────────────────────────────────────────

def log_scrape_run(
    source: str,
    started_at: str,
    finished_at: str,
    jobs_found: int,
    errors: list = None,
    status: str = "SUCCESS",
    db_path: str = DB_PATH,
):
    with get_conn(db_path) as conn:
        conn.execute(
            """INSERT INTO scrape_logs
               (source, started_at, finished_at, jobs_found, errors, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source, started_at, finished_at, jobs_found, json.dumps(errors or []), status),
        )

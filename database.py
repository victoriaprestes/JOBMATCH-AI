import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data/jobs.db")

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            title TEXT NOT NULL,
            location TEXT,
            work_mode TEXT,
            salary INTEGER DEFAULT 0,
            url TEXT,
            description TEXT NOT NULL,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'Nova',
            created_at TEXT NOT NULL
        )
        """)

def add_job(company, title, location, work_mode, salary, url, description, notes=""):
    with connect() as conn:
        conn.execute("""
        INSERT INTO jobs (company, title, location, work_mode, salary, url, description, notes, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Nova', ?)
        """, (company, title, location, work_mode, salary, url, description, notes, datetime.now().isoformat(timespec="seconds")))

def get_jobs():
    with connect() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()]

def update_status(job_id, status, notes):
    with connect() as conn:
        conn.execute("UPDATE jobs SET status=?, notes=? WHERE id=?", (status, notes, job_id))

def delete_job(job_id):
    with connect() as conn:
        conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))

def export_jobs():
    return get_jobs()

def import_jobs(frame):
    required = {"company", "title", "description"}
    if not required.issubset(set(frame.columns)):
        raise ValueError("O CSV precisa conter company, title e description.")
    count = 0
    for _, row in frame.iterrows():
        add_job(
            str(row["company"]), str(row["title"]),
            str(row.get("location", "")), str(row.get("work_mode", "Não informado")),
            int(row.get("salary", 0) or 0), str(row.get("url", "")),
            str(row["description"]), str(row.get("notes", ""))
        )
        count += 1
    return count

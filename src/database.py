import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data/jobs.db")
STATUSES = ["Salva", "Candidatura enviada", "Entrevista", "Teste", "Recusada", "Encerrada"]

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL, title TEXT NOT NULL, location TEXT,
            work_mode TEXT, salary INTEGER DEFAULT 0, url TEXT,
            description TEXT NOT NULL, notes TEXT,
            status TEXT NOT NULL DEFAULT 'Salva', created_at TEXT NOT NULL,
            source TEXT, external_id TEXT, benefits TEXT
        )""")
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
        for name, declaration in {
            "source": "TEXT", "external_id": "TEXT", "benefits": "TEXT"
        }.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {declaration}")
        conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_source_external
                        ON jobs(source, external_id)
                        WHERE source IS NOT NULL AND external_id IS NOT NULL""")

def save_automatic_job(job):
    source = str(job.get("source") or "")
    external_id = str(job.get("external_id") or job.get("url") or "")
    if not source or not external_id:
        raise ValueError("A vaga não tem identificador de origem válido.")
    with connect() as conn:
        conn.execute("""INSERT OR IGNORE INTO jobs
            (company,title,location,work_mode,salary,url,description,notes,status,created_at,source,external_id,benefits)
            VALUES (?,?,?,?,?,?,?,'','Salva',?,?,?,?)""",
            (job.get("company") or "Empresa não informada", job.get("title") or "Cargo",
             job.get("location") or "", job.get("work_mode") or "Não informado",
             int(job.get("salary_min_brl_monthly") or 0), job.get("url") or "",
             job.get("description") or "", datetime.now().isoformat(timespec="seconds"),
             source, external_id, job.get("benefits") or ""))

def get_jobs():
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM jobs ORDER BY created_at DESC")]

def update_job(job_id, status, notes):
    if status not in STATUSES:
        raise ValueError("Status inválido.")
    with connect() as conn:
        conn.execute("UPDATE jobs SET status=?, notes=? WHERE id=?", (status, notes, job_id))

def delete_job(job_id):
    with connect() as conn:
        conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))

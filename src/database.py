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
        conn.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL, title TEXT NOT NULL, location TEXT,
            work_mode TEXT, salary INTEGER DEFAULT 0, url TEXT,
            description TEXT NOT NULL, notes TEXT,
            status TEXT NOT NULL DEFAULT 'Nova', created_at TEXT NOT NULL
        )""")

def add_job(company, title, location, work_mode, salary, url, description, notes=""):
    with connect() as conn:
        conn.execute("""INSERT INTO jobs
            (company,title,location,work_mode,salary,url,description,notes,status,created_at)
            VALUES (?,?,?,?,?,?,?,?, 'Nova', ?)""",
            (company,title,location,work_mode,salary,url,description,notes,
             datetime.now().isoformat(timespec="seconds")))

def get_jobs():
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM jobs ORDER BY created_at DESC")]

def update_status(job_id, status, notes):
    with connect() as conn:
        conn.execute("UPDATE jobs SET status=?, notes=? WHERE id=?", (status,notes,job_id))

def delete_job(job_id):
    with connect() as conn:
        conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))

def export_jobs():
    return get_jobs()

def import_jobs(frame):
    required={"company","title","description"}
    if not required.issubset(frame.columns):
        raise ValueError("O CSV precisa conter company, title e description.")
    count=0
    for _,r in frame.iterrows():
        def val(k, default=""):
            v=r.get(k,default)
            return default if v is None or str(v).lower()=="nan" else v
        add_job(str(val("company")),str(val("title")),str(val("location")),
                str(val("work_mode","Não informado")),int(float(val("salary",0) or 0)),
                str(val("url")),str(val("description")),str(val("notes")))
        count+=1
    return count

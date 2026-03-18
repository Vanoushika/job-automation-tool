import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from src.database.db import JobDatabase

app = FastAPI(title="Job Automation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JOBS_FILE = Path("jobs_output.json")
db = JobDatabase()


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_jobs_json() -> list:
    if not JOBS_FILE.exists():
        return []
    with open(JOBS_FILE) as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def save_jobs_json(jobs: list):
    with open(JOBS_FILE, "w") as f:
        json.dump(jobs, f, indent=2, default=str)


def get_jobs_source(
    tier=None, job_type=None, applied=None, search=None
) -> list:
    """Read from MongoDB if connected, else fall back to JSON file."""
    if db.connected:
        return db.get_jobs(tier=tier, job_type=job_type, applied=applied, search=search)

    jobs = load_jobs_json()
    if tier and tier != "all":
        jobs = [j for j in jobs if j.get("tier") == tier.upper()]
    if job_type and job_type != "all":
        jobs = [j for j in jobs if j.get("job_type") == job_type]
    if applied is not None:
        jobs = [j for j in jobs if j.get("applied") == applied]
    if search:
        q = search.lower()
        jobs = [j for j in jobs if
                q in j.get("company", "").lower() or
                q in j.get("role", "").lower()]
    jobs.sort(key=lambda x: x.get("best_score") or 0, reverse=True)
    return jobs


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/jobs")
def get_jobs(
    tier: Optional[str] = None,
    job_type: Optional[str] = None,
    applied: Optional[bool] = None,
    search: Optional[str] = None,
):
    return get_jobs_source(tier=tier, job_type=job_type, applied=applied, search=search)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    jobs = get_jobs_source()
    for job in jobs:
        if job.get("id") == job_id:
            return job
    raise HTTPException(status_code=404, detail="Job not found")


@app.post("/api/jobs/{job_id}/apply")
def mark_applied(job_id: str):
    if db.connected:
        success = db.mark_applied(job_id)
        if success:
            return {"status": "success"}
        raise HTTPException(status_code=404, detail="Job not found")

    # JSON fallback
    jobs = load_jobs_json()
    for job in jobs:
        if job.get("id") == job_id:
            job["applied"] = True
            save_jobs_json(jobs)
            return {"status": "success"}
    raise HTTPException(status_code=404, detail="Job not found")


@app.get("/api/stats")
def get_stats():
    if db.connected:
        return db.get_stats()

    jobs = load_jobs_json()
    return {
        "total":     len(jobs),
        "tier_a":    len([j for j in jobs if j.get("tier") == "A"]),
        "tier_b":    len([j for j in jobs if j.get("tier") == "B"]),
        "tier_c":    len([j for j in jobs if j.get("tier") == "C"]),
        "tier_d":    len([j for j in jobs if j.get("tier") == "D"]),
        "applied":   len([j for j in jobs if j.get("applied")]),
        "full_time": len([j for j in jobs if j.get("job_type") == "full_time"]),
        "contract":  len([j for j in jobs if j.get("job_type") == "contract"]),
    }


@app.post("/api/run")
def trigger_run():
    subprocess.Popen(
        [sys.executable, "run_daily.py", "--no-email"],
        cwd=Path(__file__).resolve().parent.parent.parent,
    )
    return {"status": "started", "message": "Pipeline running — refresh in ~2 min"}


@app.get("/api/sources")
def get_sources():
    jobs = get_jobs_source()
    return sorted({j.get("source", "") for j in jobs if j.get("source")})


@app.get("/health")
def health():
    return {"status": "ok", "db": "mongodb" if db.connected else "json"}

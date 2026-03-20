import json
import base64
import subprocess
import sys
import os
import time
from pathlib import Path
from typing import Optional

import requests as http_requests
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
GITHUB_PAT    = os.getenv("GITHUB_PAT", "")
GITHUB_REPO   = "Vanoushika/job-automation-tool"
GITHUB_BRANCH = "data"
db = JobDatabase()

# In-memory cache so we don't hit GitHub API on every request
_cache: list = []
_cache_time: float = 0
CACHE_TTL = 300  # refresh from GitHub every 5 minutes


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_jobs_json() -> list:
    if not JOBS_FILE.exists():
        return []
    with open(JOBS_FILE) as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def fetch_jobs_from_github() -> list:
    """Fetch latest jobs from GitHub data branch (fallback when local file is missing)."""
    if not GITHUB_PAT:
        return []
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/jobs_output.json?ref={GITHUB_BRANCH}"
        r = http_requests.get(url, headers={"Authorization": f"token {GITHUB_PAT}"}, timeout=15)
        if r.status_code == 200:
            content = base64.b64decode(r.json()["content"]).decode()
            jobs = json.loads(content)
            # Preserve applied status from local cache
            local = {j["id"]: j for j in load_jobs_json()}
            for job in jobs:
                if local.get(job["id"], {}).get("applied"):
                    job["applied"] = True
            save_jobs_json(jobs)
            print(f"[API] Loaded {len(jobs)} jobs from GitHub data branch")
            return jobs
        print(f"[API] GitHub fetch returned {r.status_code}")
    except Exception as e:
        print(f"[API] GitHub fetch failed: {e}")
    return []


def save_jobs_json(jobs: list):
    with open(JOBS_FILE, "w") as f:
        json.dump(jobs, f, indent=2, default=str)


def get_fresh_jobs() -> list:
    """Return jobs, syncing from GitHub every 5 minutes."""
    global _cache, _cache_time
    if GITHUB_PAT and (time.time() - _cache_time > CACHE_TTL):
        jobs = fetch_jobs_from_github()
        if jobs:
            _cache = jobs
            _cache_time = time.time()
            return jobs
    if _cache:
        return _cache
    return load_jobs_json()


def get_jobs_source(
    tier=None, job_type=None, applied=None, search=None
) -> list:
    """Read from MongoDB if connected, else sync from GitHub data branch."""
    if db.connected:
        return db.get_jobs(tier=tier, job_type=job_type, applied=applied, search=search)

    jobs = get_fresh_jobs()
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

    jobs = get_fresh_jobs()
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

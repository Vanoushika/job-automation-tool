"""
run_daily.py — Entry point for the daily job fetch + ATS scoring pipeline.

Usage:
    python run_daily.py                  # Run once now
    python run_daily.py --scheduler      # Run on schedule (9 AM daily)
    python run_daily.py --no-email       # Run without sending email
"""
import json
import sys
import argparse
import base64
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.utils.config import (
    validate, load_resume,
    RESUME_AI_PATH, RESUME_FULLSTACK_PATH,
    TARGET_JOBS, DAILY_RUN_HOUR, DAILY_RUN_MINUTE,
    NOTIFY_EMAIL,
)
from src.scrapers.aggregator import JobAggregator
from src.scoring.ats_scorer import ATSScorer


def fetch_existing_jobs() -> dict:
    """Fetch previously seen jobs from GitHub data branch. Returns dict keyed by job id."""
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        # Fall back to local file
        path = Path("jobs_output.json")
        if path.exists():
            try:
                jobs = json.loads(path.read_text())
                return {j["id"]: j for j in jobs if j.get("id")}
            except Exception:
                pass
        return {}
    try:
        url = "https://api.github.com/repos/Vanoushika/job-automation-tool/contents/jobs_output.json?ref=data"
        req = urllib.request.Request(url, headers={"Authorization": f"token {token}"})
        with urllib.request.urlopen(req) as r:
            content = base64.b64decode(json.load(r)["content"]).decode()
            jobs = json.loads(content)
            return {j["id"]: j for j in jobs if j.get("id")}
    except Exception:
        return {}


def run_pipeline(send_email: bool = True) -> list:
    print(f"\n{'='*60}")
    print(f"  Job Automation Pipeline — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    # Load resumes
    try:
        resume_ai = load_resume(RESUME_AI_PATH)
        resume_fullstack = load_resume(RESUME_FULLSTACK_PATH)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    scorer = ATSScorer()
    aggregator = JobAggregator()

    # Full pipeline: scrape → dedupe → filter → score → 100 FT + 20 W2
    top_jobs = aggregator.pipeline(
        scorer=scorer,
        resume_ai=resume_ai,
        resume_fullstack=resume_fullstack,
        ft_target=100,
        contract_target=20,
    )

    if not top_jobs:
        print("\n[Pipeline] No jobs found today. Try again later.")
        return []

    # Load previously seen jobs to preserve first_seen dates and posted_dates
    existing = fetch_existing_jobs()
    now_iso  = datetime.now(timezone.utc).isoformat()
    now      = datetime.now(timezone.utc)

    # Staleness filter:
    # - SimplifyJobs relists jobs indefinitely — drop any job we've seen before from that source
    # - All other sources: drop jobs first seen 3+ days ago
    three_days_ago = now - timedelta(days=3)
    fresh_jobs = []
    stale_count = 0
    for job in top_jobs:
        prev = existing.get(job["id"])
        if prev:
            if job.get("source") == "SimplifyJobs":
                # SimplifyJobs shows same jobs forever — once seen, never show again
                stale_count += 1
                continue
            try:
                fs = datetime.fromisoformat(prev.get("first_seen", now_iso))
                if fs.tzinfo is None:
                    fs = fs.replace(tzinfo=timezone.utc)
                if fs < three_days_ago:
                    stale_count += 1
                    continue
            except Exception:
                pass
        fresh_jobs.append(job)
    top_jobs = fresh_jobs
    if stale_count:
        print(f"[Pipeline] Dropped {stale_count} stale jobs → {len(top_jobs)} remaining")

    if not top_jobs:
        print("\n[Pipeline] No fresh jobs found today. Try again later.")
        return []

    # Print results to console
    _print_summary(top_jobs)

    def _is_recently_posted(posted_date_str: str, hours: int = 48) -> bool:
        """True if the job was posted within the last N hours."""
        if not posted_date_str:
            return False
        try:
            pd = datetime.fromisoformat(posted_date_str)
            if pd.tzinfo is None:
                pd = pd.replace(tzinfo=timezone.utc)
            return (now - pd).total_seconds() < hours * 3600
        except Exception:
            return False

    for job in top_jobs:
        prev = existing.get(job["id"])
        if prev:
            # Preserve original posted_date and first_seen
            if prev.get("posted_date"):
                job["posted_date"] = prev["posted_date"]
            job["first_seen"] = prev.get("first_seen", prev.get("posted_date", now_iso))
        else:
            job["first_seen"] = now_iso

        # is_new = wasn't in the previous pipeline run's output
        # This is the only reliable signal — SimplifyJobs always fakes "posted today"
        job["is_new"] = prev is None

    output_path = Path("jobs_output.json")
    with open(output_path, "w") as f:
        json.dump(top_jobs, f, indent=2, default=str)
    new_count = sum(1 for j in top_jobs if j.get("is_new"))
    print(f"\n[Pipeline] Saved {len(top_jobs)} jobs ({new_count} new) to {output_path}")

    # Save to MongoDB (when MONGODB_URI is set)
    try:
        from src.database.db import JobDatabase
        db = JobDatabase()
        if db.connected:
            saved = db.save_jobs(top_jobs)
            print(f"[Pipeline] Saved {saved} jobs to MongoDB")

    except Exception as e:
        print(f"[Pipeline] MongoDB save error: {e}")

    # Send email
    if send_email:
        try:
            from src.utils.email_sender import send_daily_email
            send_daily_email(top_jobs, NOTIFY_EMAIL)
        except Exception as e:
            print(f"[Pipeline] Email failed: {e}")

    return top_jobs


def _print_summary(jobs: list):
    ft_jobs = [j for j in jobs if j.get("job_type") == "full_time"]
    w2_jobs = [j for j in jobs if j.get("job_type") in ("contract", "w2")]

    print(f"\n{'─'*60}")
    print(f"  RESULTS: {len(ft_jobs)} Full-Time  +  {len(w2_jobs)} W2/Contract  =  {len(jobs)} total")
    print(f"{'─'*60}")

    for section_label, section_jobs in [("FULL-TIME", ft_jobs), ("W2 / CONTRACT", w2_jobs)]:
        if not section_jobs:
            continue
        tiers = {"A": [], "B": [], "C": [], "D": []}
        for job in section_jobs:
            tiers.setdefault(job.get("tier", "D"), []).append(job)

        print(f"\n── {section_label} ──")
        icons = {"A": "🔥", "B": "⭐", "C": "✅", "D": "📋"}
        for tier_label, tier_jobs in tiers.items():
            if not tier_jobs:
                continue
            print(f"\n  {icons.get(tier_label, '')} Tier {tier_label} — {len(tier_jobs)} jobs")
            for j in tier_jobs[:4]:
                score = j.get("best_score", 0)
                print(f"     {j['company']} — {j['role']} ({score:.0f}%) [{j['source']}]")
            if len(tier_jobs) > 4:
                print(f"     ... and {len(tier_jobs) - 4} more")


def start_scheduler():
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
    except ImportError:
        print("[Scheduler] Install apscheduler: pip install apscheduler")
        sys.exit(1)

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_pipeline,
        "cron",
        hour=DAILY_RUN_HOUR,
        minute=DAILY_RUN_MINUTE,
        id="daily_job_fetch",
    )
    print(f"[Scheduler] Job scheduled daily at {DAILY_RUN_HOUR:02d}:{DAILY_RUN_MINUTE:02d}")
    print("[Scheduler] Press Ctrl+C to stop\n")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n[Scheduler] Stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job Automation Pipeline")
    parser.add_argument("--scheduler", action="store_true", help="Run on daily schedule")
    parser.add_argument("--no-email", action="store_true", help="Skip email notification")
    args = parser.parse_args()

    validate()

    if args.scheduler:
        start_scheduler()
    else:
        run_pipeline(send_email=not args.no_email)

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
from datetime import datetime
from pathlib import Path

from src.utils.config import (
    validate, load_resume,
    RESUME_AI_PATH, RESUME_FULLSTACK_PATH,
    TARGET_JOBS, DAILY_RUN_HOUR, DAILY_RUN_MINUTE,
    NOTIFY_EMAIL,
)
from src.scrapers.aggregator import JobAggregator
from src.scoring.ats_scorer import ATSScorer


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

    # Full pipeline: scrape → dedupe → filter → score → 50 FT + 20 W2
    top_jobs = aggregator.pipeline(
        scorer=scorer,
        resume_ai=resume_ai,
        resume_fullstack=resume_fullstack,
        ft_target=50,
        contract_target=20,
    )

    if not top_jobs:
        print("\n[Pipeline] No jobs found today. Try again later.")
        return []

    # Print results to console
    _print_summary(top_jobs)

    # Save to JSON (always — local backup), preserving original posted_date
    output_path = Path("jobs_output.json")
    existing_dates = {}
    if output_path.exists():
        try:
            existing = json.loads(output_path.read_text())
            existing_dates = {j["id"]: j.get("posted_date") for j in existing if j.get("id")}
        except Exception:
            pass
    for job in top_jobs:
        if job["id"] in existing_dates and existing_dates[job["id"]]:
            job["posted_date"] = existing_dates[job["id"]]
    with open(output_path, "w") as f:
        json.dump(top_jobs, f, indent=2, default=str)
    print(f"\n[Pipeline] Saved {len(top_jobs)} jobs to {output_path}")

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

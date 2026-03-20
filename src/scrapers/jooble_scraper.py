import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict
import os
from .base import BaseScraper


class JoobleScraper(BaseScraper):
    """
    Free API — aggregates from LinkedIn, Indeed, Glassdoor, 140+ sources.
    Get free API key at: https://jooble.org/api/about
    Generous free tier (500+ requests/day).
    """
    source_name = "Jooble"
    BASE_URL = "https://jooble.org/api"

    SEARCHES = [
        # Role-level searches
        "software engineer new grad",
        "software engineer entry level",
        "full stack engineer entry level",
        "backend engineer new grad",
        "frontend engineer entry level",
        # Tech-stack specific — higher ATS scores since keywords are in title
        "React developer entry level",
        "Python developer new grad",
        "TypeScript developer entry level",
        "Node.js developer entry level",
        "React Node full stack new grad",
        "Python Django developer entry level",
        "machine learning engineer new grad",
        "data engineer Python entry level",
        "iOS Swift developer entry level",
        "Android Kotlin developer entry level",
        "Java developer entry level",
        "AWS cloud engineer entry level",
        "DevOps engineer entry level",
        "API developer Python entry level",
    ]

    def __init__(self):
        self.api_key = os.getenv("JOOBLE_API_KEY", "")

    def fetch_jobs(self) -> List[Dict]:
        if not self.api_key:
            print("[Jooble] Skipped — JOOBLE_API_KEY not set")
            return []

        print("[Jooble] Fetching from LinkedIn/Indeed/Glassdoor via Jooble...")
        jobs = []
        seen_ids = set()

        for query in self.SEARCHES:
            try:
                r = requests.post(
                    f"{self.BASE_URL}/{self.api_key}",
                    json={
                        "keywords": query,
                        "location": "United States",
                        "resultsOnPage": 20,
                        "page": 1,
                    },
                    timeout=15,
                )
                r.raise_for_status()
                for item in r.json().get("jobs", []):
                    job_id = item.get("id") or item.get("link", "")
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)
                    job = self._transform(item)
                    if job:
                        jobs.append(job)
            except Exception as e:
                print(f"[Jooble] Error ({query}): {e}")

        print(f"[Jooble] Found {len(jobs)} jobs from LinkedIn/Indeed/Glassdoor")
        return jobs

    def _transform(self, item: Dict) -> Dict:
        try:
            company  = item.get("company", "").strip()
            role     = item.get("title", "").strip()
            location = item.get("location", "").strip()
            apply_url = item.get("link", "").strip()
            snippet = item.get("snippet", "").strip()
            description = f"{role} at {company}. {snippet}" if snippet else f"{role} at {company}"
            posted_date = self._parse_date(item.get("updated", ""))

            if not company or not role or not apply_url:
                return None

            return self._make_job(
                company=company,
                role=role,
                location=location,
                apply_url=apply_url,
                description=description,
                posted_date=posted_date,
                job_type="full_time",
            )
        except Exception as e:
            print(f"[Jooble] Transform error: {e}")
            return None

    def _parse_date(self, date_str: str) -> datetime:
        """Parse Jooble date format."""
        if not date_str:
            return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            # Jooble returns format like "2026-03-19T08:10:00"
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

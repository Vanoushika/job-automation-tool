import requests
from datetime import datetime, timezone
from typing import List, Dict
import os
from .base import BaseScraper


class AdzunaScraper(BaseScraper):
    """
    Free API — needs ADZUNA_APP_ID + ADZUNA_APP_KEY (free signup at adzuna.com).
    250 requests/day on free tier. Searches real US job postings.
    Sign up: https://developer.adzuna.com/
    """
    source_name = "Adzuna"
    BASE_URL = "https://api.adzuna.com/v1/api/jobs/us/search"

    # Full-time entry-level searches (max_days_old=1 — today only)
    FT_SEARCHES = [
        "software engineer entry level",
        "backend engineer new grad",
        "software developer junior",
        "full stack engineer entry level",
        "python developer entry level",
        "frontend engineer entry level",
        "react developer new grad",
        "machine learning engineer entry level",
        "data engineer entry level",
        "android developer entry level",
    ]

    # W2 contract searches (search term signals contract intent)
    CONTRACT_SEARCHES = [
        "software engineer contract",
        "python developer contract",
        "full stack developer contract",
        "java developer contract",
        "react developer contract",
    ]

    def __init__(self):
        self.app_id = os.getenv("ADZUNA_APP_ID", "")
        self.app_key = os.getenv("ADZUNA_APP_KEY", "")

    def fetch_jobs(self) -> List[Dict]:
        if not self.app_id or not self.app_key:
            print("[Adzuna] Skipped — ADZUNA_APP_ID / ADZUNA_APP_KEY not set")
            return []

        print("[Adzuna] Fetching...")
        jobs = []
        seen_ids = set()

        searches = (
            [(q, False, 1) for q in self.FT_SEARCHES] +
            [(q, True,  1) for q in self.CONTRACT_SEARCHES]
        )

        for query, is_contract, max_days in searches:
            try:
                r = requests.get(
                    f"{self.BASE_URL}/1",
                    params={
                        "app_id": self.app_id,
                        "app_key": self.app_key,
                        "results_per_page": 20,
                        "what": query,
                        "where": "United States",
                        "max_days_old": max_days,
                        "category": "it-jobs",
                    },
                    timeout=15,
                )
                r.raise_for_status()
                for item in r.json().get("results", []):
                    item_id = item.get("id")
                    if item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)
                    job = self._transform(item, is_contract)
                    if job:
                        jobs.append(job)
            except Exception as e:
                print(f"[Adzuna] Error ({query}): {e}")

        ft = len([j for j in jobs if j["job_type"] == "full_time"])
        ct = len([j for j in jobs if j["job_type"] == "contract"])
        print(f"[Adzuna] Found {len(jobs)} jobs ({ft} full-time, {ct} contract)")
        return jobs

    def _transform(self, item: Dict, is_contract: bool = False) -> Dict:
        try:
            company = item.get("company", {}).get("display_name", "")
            role = item.get("title", "")
            location = item.get("location", {}).get("display_name", "")
            apply_url = item.get("redirect_url", "")
            description = item.get("description", "")[:4000]
            posted_date = self._parse_date(item.get("created", ""))

            # Adzuna returns contract_type field; also use search intent
            contract_type = (item.get("contract_type") or "").lower()
            job_type = "contract" if (is_contract or "contract" in contract_type) else "full_time"

            if not company or not role or not apply_url:
                return None

            return self._make_job(
                company=company,
                role=role,
                location=location,
                apply_url=apply_url,
                description=description,
                posted_date=posted_date,
                job_type=job_type,
            )
        except Exception as e:
            print(f"[Adzuna] Transform error: {e}")
            return None

    # Local area searches — any role, today only
    LOCAL_LOCATIONS = ["Youngstown OH", "Pittsburgh PA", "Cleveland OH"]
    LOCAL_QUERIES   = ["software developer", "data analyst IT"]

    def fetch_local_jobs(self) -> List[Dict]:
        """Fetch today's jobs in Youngstown/Pittsburgh/Cleveland — any role, scored against resume."""
        if not self.app_id or not self.app_key:
            return []

        print("[Adzuna Local] Fetching Youngstown-area jobs...")
        jobs = []
        seen_ids: set = set()

        for location in self.LOCAL_LOCATIONS:
            for query in self.LOCAL_QUERIES:
                try:
                    r = requests.get(
                        f"{self.BASE_URL}/1",
                        params={
                            "app_id":            self.app_id,
                            "app_key":           self.app_key,
                            "results_per_page":  20,
                            "what":              query,
                            "where":             location,
                            "max_days_old":      1,
                            "sort_by":           "date",
                        },
                        timeout=15,
                    )
                    r.raise_for_status()
                    for item in r.json().get("results", []):
                        item_id = item.get("id")
                        if item_id in seen_ids:
                            continue
                        seen_ids.add(item_id)
                        job = self._transform(item)
                        if job:
                            job["section"] = "local"
                            job["source"]  = "Local"
                            jobs.append(job)
                except Exception as e:
                    print(f"[Adzuna Local] Error ({query}, {location}): {e}")

        print(f"[Adzuna Local] Found {len(jobs)} local candidates")
        return jobs

    def _parse_date(self, date_str: str) -> datetime:
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)

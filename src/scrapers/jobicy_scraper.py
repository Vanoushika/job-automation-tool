import requests
from datetime import datetime, timezone
from typing import List, Dict
from bs4 import BeautifulSoup
from .base import BaseScraper


class JobicyScraper(BaseScraper):
    """
    Free API — no key needed.
    Covers remote jobs including W2 contract roles.
    Docs: https://jobicy.com/jobs-rss-feed
    """
    source_name = "Jobicy"
    BASE_URL = "https://jobicy.com/api/v2/remote-jobs"

    SEARCH_TAGS = ["software-engineer", "python", "backend", "full-stack", "data-engineer"]

    def fetch_jobs(self) -> List[Dict]:
        print(f"[Jobicy] Fetching...")
        jobs = []
        seen_ids = set()

        for tag in self.SEARCH_TAGS:
            try:
                r = requests.get(
                    self.BASE_URL,
                    params={"count": 50, "tag": tag},
                    timeout=15,
                )
                r.raise_for_status()
                for item in r.json().get("jobs", []):
                    item_id = item.get("id")
                    if item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)
                    job = self._transform(item)
                    if job:
                        jobs.append(job)
            except Exception as e:
                print(f"[Jobicy] Error ({tag}): {e}")

        print(f"[Jobicy] Found {len(jobs)} jobs")
        return jobs

    def _transform(self, item: Dict) -> Dict:
        try:
            description = BeautifulSoup(
                item.get("jobDescription", ""), "html.parser"
            ).get_text(separator=" ")[:4000]

            # Jobicy job types: "full-time", "contract", "freelance", "part-time"
            raw_types = item.get("jobType", ["full-time"])
            type_str = " ".join(raw_types).lower() if isinstance(raw_types, list) else str(raw_types).lower()

            if "part" in type_str:
                return None  # skip part-time

            if "contract" in type_str or "freelance" in type_str or "w2" in type_str:
                job_type = "contract"
            else:
                job_type = "full_time"

            posted_date = self._parse_date(item.get("publishedAt", ""))

            return self._make_job(
                company=item.get("companyName", ""),
                role=item.get("jobTitle", ""),
                location=item.get("jobGeo", "Remote"),
                apply_url=item.get("url", ""),
                description=description,
                posted_date=posted_date,
                job_type=job_type,
            )
        except Exception as e:
            print(f"[Jobicy] Transform error: {e}")
            return None

    def _parse_date(self, date_str: str) -> datetime:
        try:
            # Format: "2026-03-17 10:30:00" or ISO
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
                try:
                    return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)

import requests
from datetime import datetime, timezone
from typing import List, Dict
from bs4 import BeautifulSoup
from .base import BaseScraper


class MuseScraper(BaseScraper):
    """
    Free API — no key needed.
    The Muse has entry-level full-time roles at real companies.
    Docs: https://www.themuse.com/developers/api/v2
    """
    source_name = "TheMuse"
    BASE_URL = "https://www.themuse.com/api/public/jobs"

    CATEGORIES = [
        "Software Engineer",
        "Data Science",
        "DevOps & Sysadmin",
        "IT & Support",
    ]
    LEVELS = ["Entry Level", "Mid Level"]

    def fetch_jobs(self) -> List[Dict]:
        print(f"[TheMuse] Fetching...")
        jobs = []
        seen_ids = set()

        for category in self.CATEGORIES:
            for level in self.LEVELS:
                for page in range(0, 3):  # 3 pages × 20 items = 60 per category
                    try:
                        r = requests.get(
                            self.BASE_URL,
                            params={
                                "category": category,
                                "level": level,
                                "page": page,
                                "descending": "True",
                            },
                            timeout=15,
                        )
                        r.raise_for_status()
                        data = r.json()
                        results = data.get("results", [])
                        if not results:
                            break
                        for item in results:
                            item_id = item.get("id")
                            if item_id in seen_ids:
                                continue
                            seen_ids.add(item_id)
                            job = self._transform(item)
                            if job:
                                jobs.append(job)
                    except Exception as e:
                        print(f"[TheMuse] Error ({category}/{level}/p{page}): {e}")
                        break

        print(f"[TheMuse] Found {len(jobs)} jobs")
        return jobs

    def _transform(self, item: Dict) -> Dict:
        try:
            company = item.get("company", {}).get("name", "")
            role = item.get("name", "")
            locations = item.get("locations", [])
            location = locations[0].get("name", "Remote") if locations else "Remote"
            apply_url = item.get("refs", {}).get("landing_page", "")
            contents_html = item.get("contents", "")
            description = BeautifulSoup(contents_html, "html.parser").get_text(separator=" ")[:4000]
            posted_date = self._parse_date(item.get("publication_date", ""))

            # TheMuse is predominantly full-time permanent roles
            job_type = "full_time"

            if not apply_url or not company or not role:
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
            print(f"[TheMuse] Transform error: {e}")
            return None

    def _parse_date(self, date_str: str) -> datetime:
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)

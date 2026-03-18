import requests
from datetime import datetime, timezone
from typing import List, Dict
from bs4 import BeautifulSoup
from .base import BaseScraper


class RemotiveScraper(BaseScraper):
    """
    Free API — no key needed.
    Covers remote full-time and contract software engineering roles.
    Docs: https://remotive.com/api
    """
    source_name = "Remotive"
    BASE_URL = "https://remotive.com/api/remote-jobs"

    CATEGORIES = ["software-dev", "devops-sysadmin"]

    # Only pass these title filters to stay relevant
    ROLE_KEYWORDS = [
        "engineer", "developer", "software", "backend", "frontend",
        "fullstack", "full stack", "full-stack", "python", "java",
        "golang", "typescript", "react", "node", "data engineer",
        "ml engineer", "ai engineer", "platform",
    ]

    def fetch_jobs(self) -> List[Dict]:
        print(f"[Remotive] Fetching...")
        jobs = []
        for category in self.CATEGORIES:
            try:
                r = requests.get(
                    self.BASE_URL,
                    params={"category": category, "limit": 100},
                    timeout=15,
                )
                r.raise_for_status()
                for item in r.json().get("jobs", []):
                    if not self._is_relevant(item.get("title", "")):
                        continue
                    job = self._transform(item)
                    if job:
                        jobs.append(job)
            except Exception as e:
                print(f"[Remotive] Error ({category}): {e}")
        print(f"[Remotive] Found {len(jobs)} relevant jobs")
        return jobs

    def _is_relevant(self, title: str) -> bool:
        title_lower = title.lower()
        return any(kw in title_lower for kw in self.ROLE_KEYWORDS)

    def _transform(self, item: Dict) -> Dict:
        try:
            description = BeautifulSoup(
                item.get("description", ""), "html.parser"
            ).get_text(separator=" ")[:4000]

            job_type_raw = item.get("job_type", "full_time").lower()
            if "contract" in job_type_raw or "freelance" in job_type_raw:
                job_type = "contract"
            elif "part" in job_type_raw:
                return None  # skip part-time
            else:
                job_type = "full_time"

            posted_date = self._parse_date(item.get("publication_date", ""))

            return self._make_job(
                company=item.get("company_name", ""),
                role=item.get("title", ""),
                location=item.get("candidate_required_location", "Remote"),
                apply_url=item.get("url", ""),
                description=description,
                posted_date=posted_date,
                job_type=job_type,
            )
        except Exception as e:
            print(f"[Remotive] Transform error: {e}")
            return None

    def _parse_date(self, date_str: str) -> datetime:
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)

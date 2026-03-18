from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime, timezone
import hashlib


class BaseScraper(ABC):
    source_name: str = "Unknown"

    @abstractmethod
    def fetch_jobs(self) -> List[Dict]:
        pass

    def _make_job(
        self,
        company: str,
        role: str,
        location: str,
        apply_url: str,
        description: str = "",
        posted_date: Optional[datetime] = None,
        job_type: str = "full_time",
    ) -> Dict:
        job = {
            "company": company.strip(),
            "role": role.strip(),
            "location": location.strip(),
            "apply_url": apply_url.strip(),
            "description": description.strip(),
            "posted_date": posted_date.isoformat() if posted_date else None,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "source": self.source_name,
            "job_type": job_type,  # full_time | contract | w2
            "ats_score_ai": None,
            "ats_score_fullstack": None,
            "best_score": None,
            "best_resume": None,
            "tier": None,
            "applied": False,
        }
        job["id"] = self._hash_job(job)
        return job

    def _hash_job(self, job: Dict) -> str:
        key = f"{job['company'].lower()}|{job['role'].lower()}|{job['location'].lower()}"
        return hashlib.md5(key.encode()).hexdigest()

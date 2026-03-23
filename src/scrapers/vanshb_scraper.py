import re
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from .base import BaseScraper


class VanshbScraper(BaseScraper):
    """
    Parses the vanshb03/New-Grad-Positions GitHub repo (2026 roles).
    Same HTML table format as SimplifyJobs.
    🛂 = no sponsorship — filtered out. 🇺🇸 = citizenship required — filtered out.
    """
    source_name = "SimplifyJobs"  # same branding — both are curated new-grad lists
    URL = "https://raw.githubusercontent.com/vanshb03/New-Grad-Positions/dev/README.md"

    def fetch_jobs(self) -> List[Dict]:
        print("[Vanshb] Fetching 2026 new-grad positions...")
        try:
            r = requests.get(self.URL, timeout=15)
            r.raise_for_status()
            jobs = self._parse(r.text)
            print(f"[Vanshb] Found {len(jobs)} jobs")
            return jobs
        except Exception as e:
            print(f"[Vanshb] Error: {e}")
            return []

    def _parse(self, content: str) -> List[Dict]:
        soup = BeautifulSoup(content, "lxml")
        jobs = []
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue
                job = self._parse_row(cells)
                if job:
                    jobs.append(job)
        return jobs

    def _parse_row(self, cells) -> Optional[Dict]:
        try:
            company_cell = cells[0]
            raw_text = company_cell.get_text(strip=True)

            # Filter out no-sponsorship and citizenship-required listings
            if "🛂" in raw_text or "🇺🇸" in raw_text:
                return None

            company_link = company_cell.find("a")
            company = company_link.get_text(strip=True) if company_link else raw_text
            company = re.sub(r"^[\U0001F300-\U0001FFFF\s🔥🛂🇺🇸🎓]+", "", company).strip()

            role = cells[1].get_text(strip=True)
            if not role or role in ("Role", "Position"):
                return None
            if "🔒" in role or "🔒" in company:
                return None

            location = cells[2].get_text(separator=", ", strip=True)
            apply_url = self._extract_apply_url(cells[3])
            if not apply_url:
                return None

            age_text = cells[4].get_text(strip=True) if len(cells) > 4 else "0d"
            posted_date = self._parse_age(age_text)

            job_type = "full_time"
            if any(w in role.lower() for w in ["contract", "w2", "freelance", "temp"]):
                job_type = "contract"

            if not company or not role:
                return None

            return self._make_job(
                company=company,
                role=role,
                location=location,
                apply_url=apply_url,
                description="",
                posted_date=posted_date,
                job_type=job_type,
            )
        except Exception:
            return None

    def _extract_apply_url(self, cell) -> Optional[str]:
        for a in cell.find_all("a", href=True):
            href = a["href"]
            if "simplify.jobs" in href:
                continue
            if href.startswith("http"):
                return href
        a = cell.find("a", href=True)
        return a["href"] if a else None

    def _parse_age(self, age_str: str) -> datetime:
        now = datetime.now(timezone.utc)
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        age_str = age_str.strip().lower()
        m = re.match(r"(\d+)d", age_str)
        if m:
            return today_midnight - timedelta(days=int(m.group(1)))
        m = re.match(r"(\d+)h", age_str)
        if m:
            return now - timedelta(hours=int(m.group(1)))
        return today_midnight

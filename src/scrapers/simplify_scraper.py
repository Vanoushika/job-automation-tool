import re
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from .base import BaseScraper


class SimplifyScraper(BaseScraper):
    """
    Parses the SimplifyJobs/New-Grad-Positions GitHub repo.
    Format: HTML table inside README.md (not markdown pipe tables).
    Age column uses format: '0d', '1d', '7d', etc.
    """
    source_name = "SimplifyJobs"
    URL = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md"

    def fetch_jobs(self) -> List[Dict]:
        print("[SimplifyJobs] Fetching...")
        try:
            r = requests.get(self.URL, timeout=15)
            r.raise_for_status()
            jobs = self._parse(r.text)
            print(f"[SimplifyJobs] Found {len(jobs)} jobs")
            return jobs
        except Exception as e:
            print(f"[SimplifyJobs] Error: {e}")
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
            # Cell 0: Company name (may have emoji flags/icons)
            company_cell = cells[0]
            raw_company_text = company_cell.get_text(strip=True)

            # 🛂 = company does NOT sponsor visas — skip for OPT candidates
            if "🛂" in raw_company_text:
                return None
            # 🇺🇸 = US citizenship required — skip
            if "🇺🇸" in raw_company_text:
                return None

            company_link = company_cell.find("a")
            company = company_link.get_text(strip=True) if company_link else raw_company_text
            # Strip leading emoji / unicode flags
            company = re.sub(r"^[\U0001F300-\U0001FFFF\s🔥🛂🇺🇸🎓]+", "", company).strip()

            # Cell 1: Role
            role_cell_text = cells[1].get_text(strip=True)
            # 🔐 = citizenship/clearance required in role cell — skip
            if "🔐" in role_cell_text:
                return None
            # 🇺🇸 = US citizenship required (sometimes appears in role cell too)
            if "🇺🇸" in role_cell_text:
                return None
            role = role_cell_text
            if not role or role in ("Role", "Position"):
                return None

            # Skip closed listings (🔒)
            if "🔒" in role or "🔒" in company:
                return None

            # Cell 2: Location
            location = cells[2].get_text(separator=", ", strip=True)

            # Cell 3: Apply link — grab the FIRST href that's not a Simplify tracking link
            apply_url = self._extract_apply_url(cells[3])
            if not apply_url:
                return None

            # Cell 4: Age (e.g. '0d', '1d', '7d', '30d')
            age_text = cells[4].get_text(strip=True) if len(cells) > 4 else "0d"
            posted_date = self._parse_age(age_text)

            job_type = "full_time"
            role_lower = role.lower()
            if any(w in role_lower for w in ["contract", "w2", "freelance", "temp"]):
                job_type = "contract"

            if not company or not role:
                return None

            return self._make_job(
                company=company,
                role=role,
                location=location,
                apply_url=apply_url,
                description="",  # SimplifyJobs doesn't provide descriptions in the README
                posted_date=posted_date,
                job_type=job_type,
            )
        except Exception:
            return None

    def _extract_apply_url(self, cell) -> Optional[str]:
        """
        The application cell has multiple <a> tags.
        Prefer the direct company apply link (greenhouse, lever, workday, etc.)
        over the simplify.jobs tracking link.
        """
        for a in cell.find_all("a", href=True):
            href = a["href"]
            # Skip simplify.jobs tracking / reference links
            if "simplify.jobs" in href:
                continue
            if href.startswith("http"):
                return href
        # Fallback: take any link
        a = cell.find("a", href=True)
        return a["href"] if a else None

    def _parse_age(self, age_str: str) -> datetime:
        """
        Parse SimplifyJobs age format: '0d', '1d', '7d', '30d'.
        Returns UTC datetime.
        """
        now = datetime.now(timezone.utc)
        # Use start of day (midnight UTC) so jobs don't reset their time each pipeline run
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        age_str = age_str.strip().lower()

        m = re.match(r"(\d+)d", age_str)
        if m:
            days = int(m.group(1))
            return today_midnight - timedelta(days=days)

        # Also handle hour format if it ever appears: '3h'
        m = re.match(r"(\d+)h", age_str)
        if m:
            hours = int(m.group(1))
            return now - timedelta(hours=hours)

        return today_midnight

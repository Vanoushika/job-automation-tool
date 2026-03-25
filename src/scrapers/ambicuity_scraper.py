import re
import requests
from datetime import datetime, timezone, timedelta
from typing import List
from .vanshb_scraper import VanshbScraper


class AmbicuityScraper(VanshbScraper):
    """
    Parses ambicuity/New-Grad-Jobs GitHub repo — 150+ company APIs, updates every 5 min.
    Same markdown table format as SimplifyJobs/Vanshb.
    """
    source_name = "SimplifyJobs"
    URL = "https://raw.githubusercontent.com/ambicuity/New-Grad-Jobs/main/README.md"

    def fetch_jobs(self) -> List[dict]:
        print("[Ambicuity] Fetching new-grad positions...")
        try:
            r = requests.get(self.URL, timeout=15)
            r.raise_for_status()
            jobs = self._parse(r.text)
            print(f"[Ambicuity] Found {len(jobs)} jobs")
            return jobs
        except Exception as e:
            print(f"[Ambicuity] Error: {e}")
            return []

    def _parse_age(self, age_str: str) -> datetime:
        """Handle 'Today', '1 day ago', '5 days ago' as well as '0d', '1d' formats."""
        now = datetime.now(timezone.utc)
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        s = age_str.strip().lower()

        if s in ("today", "0d", "0 days ago"):
            return today_midnight

        # "N days ago" / "N day ago"
        m = re.match(r"(\d+)\s*days?\s*ago", s)
        if m:
            return today_midnight - timedelta(days=int(m.group(1)))

        # "Nd" shorthand (vanshb style)
        m = re.match(r"(\d+)d", s)
        if m:
            return today_midnight - timedelta(days=int(m.group(1)))

        # "Nh ago"
        m = re.match(r"(\d+)\s*h(?:ours?)?\s*ago", s)
        if m:
            return now - timedelta(hours=int(m.group(1)))

        return today_midnight

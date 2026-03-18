import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from .base import BaseScraper


class IndeedRSSScraper(BaseScraper):
    """
    Uses Indeed's public RSS feed — no API key, no Selenium.
    Specifically targets W2 contract / entry-level contract roles.
    """
    source_name = "Indeed"
    BASE_URL = "https://www.indeed.com/rss"

    # Searches tuned for entry-level W2 contract roles
    SEARCHES = [
        {"q": "software engineer w2 contract entry level",       "jt": "contract"},
        {"q": "software developer w2 contract new grad",         "jt": "contract"},
        {"q": "full stack developer contract w2 junior",         "jt": "contract"},
        {"q": "python developer w2 contract entry level",        "jt": "contract"},
        {"q": "backend developer w2 contract junior",            "jt": "contract"},
        {"q": "java developer w2 contract entry level",          "jt": "contract"},
        {"q": "react developer w2 contract junior",              "jt": "contract"},
    ]

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }

    def fetch_jobs(self) -> List[Dict]:
        print("[Indeed] Fetching W2/contract jobs...")
        jobs = []
        seen_urls = set()

        for search in self.SEARCHES:
            try:
                params = {
                    "q": search["q"],
                    "l": "United States",
                    "jt": search.get("jt", "contract"),
                    "sort": "date",
                    "fromage": "3",      # Posted in last 3 days
                    "limit": "20",
                }
                r = requests.get(
                    self.BASE_URL,
                    params=params,
                    headers=self.HEADERS,
                    timeout=15,
                )
                if r.status_code != 200:
                    continue

                parsed = self._parse_rss(r.text, seen_urls)
                jobs.extend(parsed)
            except Exception as e:
                print(f"[Indeed] Error ({search['q'][:30]}): {e}")

        print(f"[Indeed] Found {len(jobs)} W2/contract jobs")
        return jobs

    def _parse_rss(self, xml_text: str, seen_urls: set) -> List[Dict]:
        jobs = []
        try:
            root = ET.fromstring(xml_text)
            channel = root.find("channel")
            if channel is None:
                return []

            for item in channel.findall("item"):
                try:
                    title_raw = item.findtext("title", "").strip()
                    link = item.findtext("link", "").strip()
                    pub_date = item.findtext("pubDate", "").strip()
                    description_html = item.findtext("description", "").strip()

                    if not link or link in seen_urls:
                        continue
                    seen_urls.add(link)

                    # Parse "Job Title - Company - Location" from RSS title
                    company, role, location = self._parse_title(title_raw)
                    if not role:
                        continue

                    # Strip HTML from description
                    description = re.sub(r"<[^>]+>", " ", description_html)
                    description = re.sub(r"\s+", " ", description).strip()[:3000]

                    posted_date = self._parse_pub_date(pub_date)

                    job = self._make_job(
                        company=company,
                        role=role,
                        location=location,
                        apply_url=link,
                        description=description,
                        posted_date=posted_date,
                        job_type="contract",
                    )
                    jobs.append(job)
                except Exception:
                    continue
        except ET.ParseError:
            pass
        return jobs

    def _parse_title(self, title: str):
        """
        Indeed RSS title format: "Job Title - Company Name - City, State"
        or "Job Title - City, State"
        """
        parts = [p.strip() for p in title.split(" - ")]
        if len(parts) >= 3:
            return parts[1], parts[0], parts[2]
        elif len(parts) == 2:
            return "", parts[0], parts[1]
        return "", title, "United States"

    def _parse_pub_date(self, date_str: str) -> datetime:
        """Parse RSS pubDate format: 'Mon, 17 Mar 2026 12:00:00 GMT'"""
        try:
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z").replace(
                tzinfo=timezone.utc
            )
        except Exception:
            return datetime.now(timezone.utc)

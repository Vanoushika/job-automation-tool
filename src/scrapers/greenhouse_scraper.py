import requests
from datetime import datetime, timezone
from typing import List, Dict
from .base import BaseScraper


# Top tech companies that hire new grads and use Greenhouse ATS
# These are publicly queryable without authentication
GREENHOUSE_COMPANIES = [
    "stripe", "databricks", "doordash", "discord", "figma", "notion",
    "ramp", "plaid", "brex", "robinhood", "coinbase", "reddit",
    "pinterest", "lyft", "twilio", "shopify", "squareup",
    "retool", "rippling", "benchling", "scale", "anyscale",
    "modal", "cohere", "perplexity", "together", "weights-and-biases",
    "huggingface", "groq", "mistral", "anthropic", "openai",
    "vercel", "linear", "loom", "mercury", "column",
    "lattice", "carta", "airtable", "gusto", "chime",
    "cloudflare", "fastly", "hashicorp", "datadog", "newrelic",
    "mongodb", "cockroachlabs", "yugabyte", "planetscale",
    "segment", "mixpanel", "amplitude", "braze", "iterable",
    "asana", "miro", "canva", "grammarly", "duolingo",
    "instacart", "shipt", "gopuff", "stytch", "clerk",
    "supabase", "neon", "turso", "fly",
]

ENTRY_SIGNALS = [
    "new grad", "new graduate", "entry level", "entry-level", "junior",
    "associate engineer", "university grad", "early career",
    "0-2 years", "0-1 year", "recent graduate", "2025", "2026",
]

SENIOR_SIGNALS = [
    "senior", " sr.", " sr ", "staff ", "principal", "lead ",
    "manager", "director", "vp ", "head of", "architect",
]


class GreenhouseScraper(BaseScraper):
    """
    Queries public Greenhouse job boards for tech companies directly.
    Gets jobs before they appear on LinkedIn/Indeed — no API key needed.
    """
    source_name = "Greenhouse"

    def fetch_jobs(self) -> List[Dict]:
        print("[Greenhouse] Fetching from company boards directly...")
        jobs = []
        success = 0
        for company in GREENHOUSE_COMPANIES:
            try:
                result = self._fetch_company(company)
                jobs.extend(result)
                if result:
                    success += 1
            except Exception:
                pass
        print(f"[Greenhouse] {len(jobs)} jobs from {success}/{len(GREENHOUSE_COMPANIES)} companies")
        return jobs

    def _fetch_company(self, company: str) -> List[Dict]:
        url = f"https://boards.greenhouse.io/v1/boards/{company}/jobs"
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                return []
            data = r.json()
            jobs = []
            for item in data.get("jobs", []):
                job = self._transform(item, company)
                if job:
                    jobs.append(job)
            return jobs
        except Exception:
            return []

    def _transform(self, item: Dict, company_slug: str) -> Dict:
        title = item.get("title", "").strip()
        title_lower = title.lower()

        # Skip senior/staff/lead roles
        if any(s in title_lower for s in SENIOR_SIGNALS):
            return None

        # Only keep entry-level / new grad roles
        is_entry = any(s in title_lower for s in ENTRY_SIGNALS)
        # Also keep generic SWE roles (companies often don't label new-grad explicitly)
        is_swe = any(kw in title_lower for kw in [
            "software engineer", "software developer", "swe",
            "backend engineer", "frontend engineer", "full stack",
            "ml engineer", "data engineer", "platform engineer",
        ])
        if not (is_entry or is_swe):
            return None

        location_data = item.get("location", {})
        location = location_data.get("name", "United States") if isinstance(location_data, dict) else str(location_data)

        apply_url = item.get("absolute_url", "")
        if not apply_url:
            return None

        # Parse updated_at timestamp
        updated_str = item.get("updated_at", "")
        try:
            posted_date = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
        except Exception:
            posted_date = datetime.now(timezone.utc)

        # Use company slug as display name — real name comes from API if available
        company_name = company_slug.replace("-", " ").title()

        return self._make_job(
            company=company_name,
            role=title,
            location=location,
            apply_url=apply_url,
            description=f"{title} at {company_name}",
            posted_date=posted_date,
            job_type="full_time",
        )

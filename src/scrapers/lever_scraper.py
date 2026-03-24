import requests
from datetime import datetime, timezone
from typing import List, Dict, Optional
from .base import BaseScraper


# Tech companies that use Lever ATS and hire new grads
LEVER_COMPANIES = [
    "netflix", "airbnb", "lyft", "pinterest", "twitter", "snap",
    "figma", "notion", "linear", "loom", "mercury", "ramp",
    "brex", "plaid", "stripe", "openai", "anthropic", "cohere",
    "scale-ai", "weights-biases", "huggingface", "replicate",
    "vercel", "netlify", "render", "railway",
    "segment", "mixpanel", "amplitude", "braze",
    "asana", "miro", "canva", "grammarly", "duolingo",
    "instacart", "doordash", "lyft", "waymo", "cruise",
    "robinhood", "coinbase", "kraken", "gemini",
    "airtable", "retool", "zapier", "make",
    "gusto", "rippling", "lattice", "carta",
    "benchling", "ginkgo", "recursion",
    "anyscale", "modal", "together-ai",
    "perplexity-ai", "mistral", "groq",
    "discord", "twitch", "reddit",
    "datadog", "honeycomb", "grafana-labs",
    "hashicorp", "pulumi", "temporal",
    "cockroachdb", "planetscale", "neon",
    "supabase", "appwrite",
    "headway", "calm", "noom",
    "faire", "attentive", "klaviyo",
    "podium", "qualtrics", "domo",
    "thumbtack", "houzz", "offerpad",
    "wealthfront", "betterment", "acorns",
]

ENTRY_SIGNALS = [
    "new grad", "new graduate", "entry level", "entry-level",
    "junior", "associate", "university grad", "early career",
    "0-2 years", "recent graduate", "2025", "2026",
]

SENIOR_SIGNALS = [
    "senior", " sr.", " sr ", "staff ", "principal", "lead ",
    "manager", "director", "vp ", "head of", "intern", "internship",
]

EXPERIENCE_SIGNALS = [
    "2-8 yoe", "3-5 yoe", "5+ yoe", "8+ yoe",
    "3+ years", "5+ years", "7+ years", "10+ years",
]


class LeverScraper(BaseScraper):
    """
    Queries public Lever job boards directly for tech companies.
    Public API — no auth needed. Direct application URLs.
    """
    source_name = "Lever"

    def fetch_jobs(self) -> List[Dict]:
        print("[Lever] Fetching from company boards directly...")
        jobs = []
        success = 0
        for company in LEVER_COMPANIES:
            try:
                result = self._fetch_company(company)
                jobs.extend(result)
                if result:
                    success += 1
            except Exception:
                pass
        print(f"[Lever] {len(jobs)} jobs from {success}/{len(LEVER_COMPANIES)} companies")
        return jobs

    def _fetch_company(self, company: str) -> List[Dict]:
        url = f"https://api.lever.co/v0/postings/{company}?mode=json"
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                return []
            jobs = []
            for item in r.json():
                job = self._transform(item, company)
                if job:
                    jobs.append(job)
            return jobs
        except Exception:
            return []

    def _transform(self, item: Dict, company_slug: str) -> Optional[Dict]:
        title = item.get("text", "").strip()
        title_lower = title.lower()

        # Skip senior/intern roles
        if title_lower.startswith("sr ") or title_lower.startswith("sr."):
            return None
        if any(s in title_lower for s in SENIOR_SIGNALS):
            return None
        if any(s in title_lower for s in EXPERIENCE_SIGNALS):
            return None

        # Only keep SWE roles
        is_swe = any(kw in title_lower for kw in [
            "software engineer", "software developer", "swe",
            "backend engineer", "frontend engineer", "full stack",
            "ml engineer", "data engineer", "platform engineer",
            "developer", "engineer",
        ])
        if not is_swe:
            return None

        # Location
        categories = item.get("categories", {})
        location = categories.get("location", "") or item.get("workplaceType", "Remote")

        apply_url = item.get("applyUrl") or item.get("hostedUrl", "")
        if not apply_url:
            return None

        # Lever createdAt is milliseconds since epoch
        created_ms = item.get("createdAt", 0)
        try:
            posted_date = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
            age_days = (datetime.now(timezone.utc) - posted_date).days
            if age_days > 30:
                return None  # Skip stale postings
        except Exception:
            pass
        # Lever createdAt is a real posting date — surface it so the UI shows "2h ago" etc.

        company_name = item.get("company") or company_slug.replace("-", " ").title()

        # Build description from commitment + team info
        commitment = categories.get("commitment", "")
        team = categories.get("team", "")
        description = f"{title} at {company_name}"
        if team:
            description += f" — {team} team"
        if commitment:
            description += f" ({commitment})"

        return self._make_job(
            company=company_name,
            role=title,
            location=location,
            apply_url=apply_url,
            description=description,
            posted_date=posted_date,
            job_type="full_time",
        )

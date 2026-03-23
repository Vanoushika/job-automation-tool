from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from typing import List, Dict

from .simplify_scraper import SimplifyScraper
from .vanshb_scraper import VanshbScraper
from .remotive_scraper import RemotiveScraper
from .jobicy_scraper import JobicyScraper
from .muse_scraper import MuseScraper
from .adzuna_scraper import AdzunaScraper
from .jooble_scraper import JoobleScraper
from .greenhouse_scraper import GreenhouseScraper


NON_US_SIGNALS = [
    # UK / Ireland
    "united kingdom", " uk", "u.k.", "london", "manchester", "birmingham",
    "edinburgh", "glasgow", "bristol", "leeds", "england", "scotland", "wales",
    "ireland", "dublin", "cork",
    # Canada
    "canada", "ontario", "british columbia", "alberta", "quebec", "toronto",
    "vancouver", "calgary", "ottawa", "mississauga", "montreal",
    # India
    "india", "bangalore", "bengaluru", "hyderabad", "mumbai", "delhi",
    "chennai", "pune", "noida", "gurugram", "gurgaon",
    # Europe
    "germany", "berlin", "munich", "france", "paris", "netherlands", "amsterdam",
    "poland", "warsaw", "romania", "bucharest", "ukraine", "kyiv",
    "sweden", "stockholm", "denmark", "copenhagen", "finland", "helsinki",
    "spain", "madrid", "barcelona", "italy", "milan", "rome", "portugal",
    "lisbon", "czech", "prague", "austria", "vienna", "switzerland", "zurich",
    "europe", "eu only", "emea", "reykjavik", "reykjavík", "iceland",
    # Latin America
    "mexico", "mexico city", "brazil", "são paulo", "bogota", "colombia",
    "argentina", "buenos aires", "latam", "latin america",
    # Other
    "australia", "sydney", "melbourne", "singapore", "japan", "tokyo",
    "israel", "tel aviv", "new zealand", "china", "beijing", "shanghai",
    "south korea", "seoul", "taiwan", "taipei",
]


class JobAggregator:
    """
    Runs all scrapers in parallel, deduplicates, filters by date,
    and returns top N jobs sorted by ATS score.

    Priority strategy:
      1. Full-time roles (from all sources), sorted by ATS score
      2. If < target, fill remaining slots with best W2/contract roles
    """

    SCRAPERS = [
        SimplifyScraper,    # New-grad curated list (sponsorship-eligible only)
        VanshbScraper,      # Vanshb 2026 new-grad list (sponsorship-eligible only)
        GreenhouseScraper,  # Direct company job boards — jobs before they hit LinkedIn
        RemotiveScraper,
        JobicyScraper,
        MuseScraper,
        AdzunaScraper,      # W2/contract when ADZUNA_APP_ID + ADZUNA_APP_KEY are set
        JoobleScraper,      # LinkedIn/Indeed/Glassdoor via Jooble when JOOBLE_API_KEY is set
    ]

    def fetch_all_raw(self) -> List[Dict]:
        """Run all scrapers in parallel and merge results."""
        all_jobs: List[Dict] = []

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(scraper_cls().fetch_jobs): scraper_cls.__name__
                for scraper_cls in self.SCRAPERS
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    jobs = future.result()
                    all_jobs.extend(jobs)
                except Exception as e:
                    print(f"[Aggregator] {name} failed: {e}")

        print(f"[Aggregator] Total raw jobs collected: {len(all_jobs)}")
        return all_jobs

    def deduplicate(self, jobs: List[Dict]) -> List[Dict]:
        """Remove duplicates by job id (hash of company+role+location)."""
        seen = {}
        for job in jobs:
            jid = job.get("id", "")
            if jid not in seen:
                seen[jid] = job
        deduped = list(seen.values())
        print(f"[Aggregator] After dedup: {len(deduped)} unique jobs")
        return deduped

    def filter_tech_roles(self, jobs: List[Dict]) -> List[Dict]:
        """Keep only software/tech roles. Removes medical techs, fitness, admin, etc."""

        # Explicit block list — roles that contain these are never software jobs
        BLOCKED_ROLE_SIGNALS = [
            "radiology", "technologist", "radiologist", "eeg", "emg",
            "phlebotom", "nursing", "nurse ", "clinical", "patient care",
            "dental", "physician", "therapist", "medical assistant",
            "surgical tech", "lab tech", "imaging tech", "ultrasound",
            "x-ray", "mri tech", "ct tech", "pharmacy tech",
            "fitness", "personal trainer", "yoga", "wellness coach",
            "driver", "delivery driver", "warehouse", "forklift",
            "accountant", "bookkeeper", "tax preparer",
            "sales representative", "account executive", "sales manager",
            "marketing coordinator", "social media manager",
            "hr coordinator", "human resources", "recruiter",
            "administrative assistant", "office coordinator",
            "customer service representative",
        ]

        # Software/tech role keywords — specific enough to avoid false positives
        TECH_KEYWORDS = [
            "software engineer", "software developer", "software development",
            "frontend engineer", "backend engineer", "full stack", "fullstack", "full-stack",
            "web developer", "web engineer", "mobile developer", "mobile engineer",
            "ios developer", "ios engineer", "android developer", "android engineer",
            "devops engineer", "devops", "sre", "site reliability",
            "data engineer", "data scientist", "data analyst",
            "machine learning", "ml engineer", "ai engineer", "deep learning",
            "cloud engineer", "platform engineer", "infrastructure engineer",
            "security engineer", "database engineer", "analytics engineer",
            "qa engineer", "quality assurance engineer", "test automation engineer",
            "solutions architect", "software architect",
            "developer", "programmer", "swe", "sde",
            "python developer", "java developer", "react developer",
            "node developer", "typescript developer", "javascript developer",
            "computer science", "information technology",
            "golang", "rust", "kubernetes engineer", "docker",
        ]

        kept = []
        for j in jobs:
            role_lower = (j.get("role") or "").lower()
            # Block clearly non-tech roles first
            if any(b in role_lower for b in BLOCKED_ROLE_SIGNALS):
                continue
            # Then require at least one tech keyword
            if any(kw in role_lower for kw in TECH_KEYWORDS):
                kept.append(j)

        removed = len(jobs) - len(kept)
        if removed:
            print(f"[Aggregator] Removed {removed} non-tech roles → {len(kept)} remaining")
        return kept

    def filter_ineligible(self, jobs: List[Dict]) -> List[Dict]:
        """
        Remove jobs requiring security clearance or US citizenship.
        SimplifyJobs marks citizenship-required roles with 🇺🇸 in the title.
        """
        SENIOR_SIGNALS = [
            "senior ", "sr.", " sr ", "staff ", "principal ",
            "lead ", "tech lead", "engineering manager", "eng manager",
            "director", "vp of", "vice president", "head of engineering",
        ]
        # Experience-level signals in job title (e.g. "2-8 YOE", "5+ years")
        EXPERIENCE_SIGNALS = [
            "2-8 yoe", "3-5 yoe", "5+ yoe", "8+ yoe", "10+ yoe",
            "3+ years", "5+ years", "7+ years", "10+ years",
            "2-5 years", "3-7 years", "5-10 years",
        ]
        # Internship signals — not full-time permanent roles
        INTERN_SIGNALS = ["intern", "internship", " co-op", " coop"]

        pre = len(jobs)
        filtered = []
        for j in jobs:
            role_lower = (j.get("role") or "").lower()
            # Catch "Sr Software Engineer" (starts with sr) and mid-string " sr "
            if role_lower.startswith("sr ") or role_lower.startswith("sr."):
                continue
            if any(s in role_lower for s in SENIOR_SIGNALS):
                continue
            if any(s in role_lower for s in EXPERIENCE_SIGNALS):
                continue
            if any(s in role_lower for s in INTERN_SIGNALS):
                continue
            filtered.append(j)
        jobs = filtered
        senior_removed = pre - len(jobs)
        if senior_removed:
            print(f"[Aggregator] Removed {senior_removed} senior/intern/YOE jobs → {len(jobs)} remaining")

        PHD_ROLE_SIGNALS = [
            "phd", "ph.d", "research scientist", "doctoral",
        ]
        PHD_DESC_SIGNALS = [
            "phd required", "ph.d. required", "requires a phd", "require a phd",
            "doctoral degree required", "phd degree required", "must have a phd",
        ]

        pre = len(jobs)
        jobs = [
            j for j in jobs
            if not any(s in (j.get("role") or "").lower() for s in PHD_ROLE_SIGNALS)
            and not any(s in (j.get("description") or "").lower() for s in PHD_DESC_SIGNALS)
        ]
        phd_removed = pre - len(jobs)
        if phd_removed:
            print(f"[Aggregator] Removed {phd_removed} PhD/research-scientist jobs → {len(jobs)} remaining")

        CLEARANCE_SIGNALS = [
            "security clearance", "clearance required", "active clearance",
            "secret clearance", "top secret", "ts/sci", "sci clearance",
            "dod clearance", "public trust clearance", "government clearance",
        ]
        CITIZENSHIP_SIGNALS = [
            "🇺🇸",  # SimplifyJobs citizenship flag
            "us citizenship required", "u.s. citizenship required",
            "must be a us citizen", "must be a u.s. citizen",
            "us citizens only", "requires us citizenship",
        ]

        kept = []
        for job in jobs:
            role = (job.get("role") or "").lower()
            company = (job.get("company") or "").lower()
            desc = (job.get("description") or "").lower()
            combined = f"{role} {company} {desc}"

            if any(s in combined for s in CLEARANCE_SIGNALS):
                continue
            if any(s in f"{job.get('role', '')} {job.get('company', '')} {desc}" for s in CITIZENSHIP_SIGNALS):
                continue
            kept.append(job)

        removed = len(jobs) - len(kept)
        if removed:
            print(f"[Aggregator] Removed {removed} clearance/citizenship jobs → {len(kept)} remaining")
        return kept

    def filter_us_only(self, jobs: List[Dict]) -> List[Dict]:
        """
        Keep only US-based or Remote jobs.
        Excludes jobs with non-US location signals.
        Remote/Worldwide jobs are kept — they're generally open to US applicants.
        """
        kept = []
        for job in jobs:
            loc = (job.get("location") or "").lower().strip()
            # Check non-US signals FIRST — must happen before remote/anywhere check
            # so "Canada - Remote", "Remote - Brazil", "Ukraine Anywhere" are blocked
            if loc in ("uk", "u.k.", "gb", "united kingdom"):
                continue
            if any(signal in loc for signal in NON_US_SIGNALS):
                continue
            # Allow: remote (US), no location, "in-office", "n/a", or US location
            kept.append(job)
        print(f"[Aggregator] After US filter: {len(kept)} jobs")
        return kept

    def filter_by_date(self, jobs: List[Dict], max_days: int = 1) -> List[Dict]:
        """Keep jobs posted within the last max_days days.
        Jobs with no posted_date (Greenhouse, Vanshb) are always included —
        their staleness is controlled by the 4-day window in run_daily.py."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
        filtered = []
        for job in jobs:
            pd = job.get("posted_date")
            if not pd:
                filtered.append(job)  # No date = include (Greenhouse/curated sources)
                continue
            try:
                posted = datetime.fromisoformat(str(pd))
                if posted.tzinfo is None:
                    posted = posted.replace(tzinfo=timezone.utc)
                if posted >= cutoff:
                    filtered.append(job)
            except Exception:
                continue
        print(f"[Aggregator] After {max_days}-day filter: {len(filtered)} jobs")
        return filtered

    def split_by_type(self, jobs: List[Dict]):
        """Separate full-time from contract/W2 roles."""
        full_time = [j for j in jobs if j.get("job_type") == "full_time"]
        contract = [j for j in jobs if j.get("job_type") in ("contract", "w2")]
        return full_time, contract

    def get_top_jobs(
        self,
        scored_jobs: List[Dict],
        ft_target: int = 100,
        contract_target: int = 20,
        per_source_cap: int = 25,
    ) -> List[Dict]:
        """
        Return top ft_target full-time jobs + top contract_target W2/contract jobs.
        Applies a per-source cap so no single source dominates the results.
        """
        # Drop jobs with low scores — no description = no useful match
        scored_jobs = [j for j in scored_jobs if (j.get("best_score") or 0) >= 10]

        # Block known staffing agencies / job boards masquerading as employers
        BLOCKED_COMPANIES = {
            "synergisticit", "robert half", "jobright.ai", "cynet systems",
            "kforce", "tek systems", "teksystems", "staffmark", "randstad",
            "manpower", "adecco", "insight global", "apex systems",
            "softpath system", "mastech", "igate", "wipro", "infosys bpm",
            # Additional staffing agencies found in the wild
            "artech", "staffing the universe", "maintec technologies",
            "anagh technology", "eitacies", "acestack", "acestack llc",
            "libsys", "nava software solutions", "clifyx",
            "motion recruitment", "judge group", "beacon hill",
            "genesis10", "horizontal talent", "smart it staffing",
        }
        scored_jobs = [
            j for j in scored_jobs
            if (j.get("company") or "").lower().strip() not in BLOCKED_COMPANIES
        ]

        full_time, contract = self.split_by_type(scored_jobs)

        full_time.sort(key=lambda x: x.get("best_score") or 0, reverse=True)
        contract.sort(key=lambda x: x.get("best_score") or 0, reverse=True)

        # Per-source cap + per-company cap (max 2 per company to avoid spam)
        source_counts: Dict[str, int] = {}
        company_counts: Dict[str, int] = {}
        ft_capped = []
        for job in full_time:
            src = job.get("source", "unknown")
            company = (job.get("company") or "").lower().strip()
            if source_counts.get(src, 0) >= per_source_cap:
                continue
            if company_counts.get(company, 0) >= 2:
                continue
            ft_capped.append(job)
            source_counts[src] = source_counts.get(src, 0) + 1
            company_counts[company] = company_counts.get(company, 0) + 1
            if len(ft_capped) >= ft_target:
                break

        ft_result = ft_capped
        contract_result = contract[:contract_target]

        # Log per-source breakdown
        breakdown = {}
        for job in ft_result:
            src = job.get("source", "unknown")
            breakdown[src] = breakdown.get(src, 0) + 1
        print(f"[Aggregator] FT source breakdown: {breakdown}")
        print(
            f"[Aggregator] {len(ft_result)} full-time + "
            f"{len(contract_result)} W2/contract = {len(ft_result + contract_result)} total jobs"
        )
        return ft_result + contract_result

    def pipeline(
        self,
        scorer,
        resume_ai: str,
        resume_fullstack: str,
        ft_target: int = 100,
        contract_target: int = 20,
    ) -> List[Dict]:
        """
        Full pipeline:
          1. Fetch from all sources
          2. Deduplicate
          3. Filter by date (1 day, expand to 2 if needed)
          4. Keyword pre-score to pick best candidates for LLM scoring
          5. LLM score top candidates
          6. Return top `target` sorted by ATS score
        """
        raw = self.fetch_all_raw()
        deduped = self.deduplicate(raw)
        us_only = self.filter_us_only(deduped)
        tech_only = self.filter_tech_roles(us_only)
        eligible = self.filter_ineligible(tech_only)

        # Full-time: today only (posted within 24h)
        # Contract/W2: 2-day window — they're posted less frequently
        ft_pool = [j for j in eligible if j.get("job_type") == "full_time"]
        contract_pool = [j for j in eligible if j.get("job_type") in ("contract", "w2")]

        recent_ft = self.filter_by_date(ft_pool, max_days=1)
        recent_contract = self.filter_by_date(contract_pool, max_days=1)
        recent = recent_ft + recent_contract
        print(f"[Aggregator] Pool: {len(recent_ft)} FT (1d) + {len(recent_contract)} W2/contract (1d) = {len(recent)}")

        if not recent:
            print("[Aggregator] No recent jobs found.")
            return []

        # Keyword pre-score all candidates
        print(f"[Aggregator] Keyword pre-scoring {len(recent)} jobs...")
        for job in recent:
            scores = scorer.keyword_score(
                job.get("description") or f"{job['role']} at {job['company']}",
                resume_ai,
                resume_fullstack,
            )
            job["_kw_score"] = max(scores["ai"], scores["fullstack"])

        # Only LLM-score jobs in the ambiguous keyword range (40-75%).
        # Clear matches (>75%) and clear rejects (<40%) don't need LLM.
        # This keeps token usage under Groq's free tier limits (~500k TPD for 8b model).
        ambiguous = [j for j in recent if 40 <= j["_kw_score"] <= 75]
        clear_good = [j for j in recent if j["_kw_score"] > 75]
        clear_bad  = [j for j in recent if j["_kw_score"] < 40]

        # Cap ambiguous candidates to limit token usage
        top_candidates = ambiguous[:80]

        # LLM score ambiguous candidates
        print(f"[Aggregator] LLM scoring {len(top_candidates)} ambiguous candidates (skipping {len(clear_good)} clear matches, {len(clear_bad)} clear rejects)...")
        for job in top_candidates:
            desc = job.get("description") or f"{job['role']} at {job['company']} in {job['location']}"
            result = scorer.score(desc, resume_ai, resume_fullstack)
            job.update(result)

        # Jobs not LLM-scored get their keyword scores directly
        scored_ids = {j["id"] for j in top_candidates}
        for job in recent:
            if job["id"] not in scored_ids:
                kw = job["_kw_score"]
                job["ats_score_ai"] = kw
                job["ats_score_fullstack"] = kw
                job["best_score"] = kw
                job["best_resume"] = "Full-Stack"
                job["tier"] = scorer.assign_tier(kw)

        # Combine all scored jobs
        all_scored = top_candidates + [j for j in recent if j["id"] not in scored_ids]
        return self.get_top_jobs(all_scored, ft_target=ft_target, contract_target=contract_target)

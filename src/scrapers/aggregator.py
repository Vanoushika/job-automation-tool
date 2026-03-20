from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from typing import List, Dict

from .simplify_scraper import SimplifyScraper
from .remotive_scraper import RemotiveScraper
from .jobicy_scraper import JobicyScraper
from .muse_scraper import MuseScraper
from .adzuna_scraper import AdzunaScraper
from .jooble_scraper import JoobleScraper


NON_US_SIGNALS = [
    # UK
    "united kingdom", " uk", "u.k.", "london", "manchester", "birmingham",
    "edinburgh", "glasgow", "bristol", "leeds", "england", "scotland", "wales",
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
    "europe", "eu only", "emea",
    # Other
    "australia", "sydney", "melbourne", "singapore", "japan", "tokyo",
    "israel", "tel aviv", "brazil", "latam", "latin america", "new zealand",
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
        SimplifyScraper,
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
        """Keep only software/tech roles. Removes fitness instructors, coordinators, etc."""
        TECH_KEYWORDS = [
            "engineer", "developer", "dev ", "dev,", "programmer", "software",
            "frontend", "backend", "full stack", "fullstack", "full-stack",
            "devops", "sre", "data ", "machine learning", " ml ", "deep learning",
            "ai ", "cloud", "mobile", "ios", "android", "python", "java",
            "javascript", "typescript", "react", "node", "web ", "api ",
            "platform", "infrastructure", "security", "database", "analytics",
            "qa ", "quality assurance", "automation", "architect", "scientist",
            " tech", "computer science", "it ", "information technology",
            "golang", "rust", "scala", "kubernetes", "docker", "aws", "azure",
        ]
        kept = [
            j for j in jobs
            if any(kw in (j.get("role") or "").lower() for kw in TECH_KEYWORDS)
        ]
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
        pre = len(jobs)
        # Only apply senior filter to full-time — contract roles often inflate titles
        jobs = [
            j for j in jobs
            if j.get("job_type") in ("contract", "w2")
            or not any(s in (j.get("role") or "").lower() for s in SENIOR_SIGNALS)
        ]
        senior_removed = pre - len(jobs)
        if senior_removed:
            print(f"[Aggregator] Removed {senior_removed} senior/lead/staff full-time jobs → {len(jobs)} remaining")

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
            loc = (job.get("location") or "").lower()
            # Always allow remote / worldwide
            if "remote" in loc or "worldwide" in loc or "anywhere" in loc:
                kept.append(job)
                continue
            # Exclude known non-US locations
            if any(signal in loc for signal in NON_US_SIGNALS):
                continue
            kept.append(job)
        print(f"[Aggregator] After US filter: {len(kept)} jobs")
        return kept

    def filter_by_date(self, jobs: List[Dict], max_days: int = 1) -> List[Dict]:
        """Keep jobs posted within the last max_days days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
        filtered = []
        for job in jobs:
            pd = job.get("posted_date")
            if not pd:
                continue
            try:
                posted = datetime.fromisoformat(pd)
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
        recent_contract = self.filter_by_date(contract_pool, max_days=2)
        recent = recent_ft + recent_contract
        print(f"[Aggregator] Pool: {len(recent_ft)} FT (1d) + {len(recent_contract)} W2/contract (2d) = {len(recent)}")

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

        # Score enough candidates to fill both full-time AND contract lists
        # Separate top scorers from each type so both get LLM scored
        full_time_candidates = sorted(
            [j for j in recent if j.get("job_type") == "full_time"],
            key=lambda x: x["_kw_score"], reverse=True
        )[:ft_target + 50]

        contract_candidates = sorted(
            [j for j in recent if j.get("job_type") in ("contract", "w2")],
            key=lambda x: x["_kw_score"], reverse=True
        )[:contract_target + 10]

        top_candidates = full_time_candidates + contract_candidates
        # Dedupe in case any job appeared in both lists
        seen = set()
        top_candidates = [j for j in top_candidates if not (j["id"] in seen or seen.add(j["id"]))]

        # LLM score top candidates
        print(f"[Aggregator] LLM scoring {len(top_candidates)} top candidates...")
        for job in top_candidates:
            desc = job.get("description") or f"{job['role']} at {job['company']} in {job['location']}"
            result = scorer.score(desc, resume_ai, resume_fullstack)
            job.update(result)

        # Jobs that weren't LLM-scored get keyword scores
        scored_ids = {j["id"] for j in top_candidates}
        for job in recent:
            if job["id"] not in scored_ids:
                kw = job["_kw_score"]
                job["ats_score_ai"] = kw
                job["ats_score_fullstack"] = kw
                job["best_score"] = kw
                job["best_resume"] = "AI"
                job["tier"] = scorer.assign_tier(kw)

        # Combine all scored jobs
        all_scored = top_candidates + [j for j in recent if j["id"] not in scored_ids]
        return self.get_top_jobs(all_scored, ft_target=ft_target, contract_target=contract_target)

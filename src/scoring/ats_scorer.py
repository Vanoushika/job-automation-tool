import re
import time
import os
from typing import Dict, Optional
from groq import Groq


class ATSScorer:
    """
    Two-mode ATS scorer:
      1. keyword_score()  — fast, free, used for pre-filtering
      2. score()          — Groq LLM scoring with keyword fallback

    Rate limit: Groq free tier = 30 req/min.
    We sleep 2s between LLM calls to stay under the limit.
    """

    # ------------------------------------------------------------------ #
    # Weighted keyword sets — tweak these to match your actual resume      #
    # ------------------------------------------------------------------ #
    AI_KEYWORDS = {
        # Core AI/ML — high weight
        "llm": 5, "large language model": 5, "rag": 5, "retrieval augmented": 5,
        "vector database": 5, "embeddings": 5, "langchain": 5, "openai": 4,
        "groq": 4, "hugging face": 4, "transformer": 4, "fine-tuning": 4,
        "pytorch": 4, "tensorflow": 4, "machine learning": 4, "deep learning": 4,
        "nlp": 4, "natural language processing": 4, "generative ai": 5,
        "ai agent": 5, "agentic": 5, "claude": 4, "gpt": 4, "gemini": 3,
        # Infrastructure / deployment
        "mlops": 3, "model serving": 3, "inference": 3, "vector search": 4,
        "pinecone": 3, "weaviate": 3, "chroma": 3, "faiss": 3,
        # General tech
        "python": 3, "fastapi": 3, "rest api": 2, "aws": 2, "docker": 2,
        "kubernetes": 2, "mongodb": 2, "postgresql": 2, "redis": 2,
    }

    FULLSTACK_KEYWORDS = {
        # Frontend
        "react": 5, "next.js": 5, "typescript": 4, "javascript": 4,
        "vue": 3, "angular": 3, "tailwind": 3, "css": 2, "html": 2,
        # Backend
        "node.js": 5, "express": 4, "fastapi": 4, "django": 4, "flask": 4,
        "spring boot": 4, "java": 3, "golang": 3, "ruby on rails": 3,
        "graphql": 4, "rest api": 3, "microservices": 3,
        # Database
        "postgresql": 3, "mysql": 3, "mongodb": 3, "redis": 3,
        "sql": 3, "nosql": 2,
        # Cloud / DevOps
        "aws": 3, "gcp": 3, "azure": 3, "docker": 3, "kubernetes": 3,
        "ci/cd": 3, "github actions": 2,
        # General
        "python": 3, "full stack": 4, "fullstack": 4, "full-stack": 4,
        "backend": 3, "frontend": 3, "api development": 3,
    }

    # Title-level bonus keywords (matched against job title)
    NEW_GRAD_SIGNALS = [
        "new grad", "entry level", "entry-level", "junior", "associate",
        "0-2 years", "0-1 year", "recent graduate", "university grad",
    ]

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY", "")
        self.client = Groq(api_key=api_key) if api_key else None
        if not self.client:
            print("[ATSScorer] GROQ_API_KEY not set — using keyword scoring only")

    # ------------------------------------------------------------------ #
    # Public API                                                            #
    # ------------------------------------------------------------------ #

    def keyword_score(self, text: str, resume_ai: str, resume_fullstack: str) -> Dict:
        """Fast keyword matching — returns scores 0-100."""
        text_lower = text.lower()

        # Extract the title portion (Jooble format: "Role at Company. snippet...")
        # Use the first sentence as the title signal
        title_part = text_lower.split(".")[0][:120] if "." in text_lower else text_lower[:120]

        if len(text_lower.strip()) < 150:
            # Short text — title scoring is most reliable
            ai_score = self._title_score(text_lower, "ai")
            fs_score = self._title_score(text_lower, "fullstack")
        else:
            # Full keyword match on entire text
            ai_score = self._kw_match(text_lower, self.AI_KEYWORDS)
            fs_score = self._kw_match(text_lower, self.FULLSTACK_KEYWORDS)
            # Use title score as a floor — prevents vague descriptions from tanking
            # jobs that clearly match by title (e.g. "React Developer entry level at Stripe")
            title_ai = self._title_score(title_part, "ai")
            title_fs = self._title_score(title_part, "fullstack")
            ai_score = max(ai_score, title_ai)
            fs_score = max(fs_score, title_fs)
            # New-grad signal boosts both scores
            if any(sig in text_lower for sig in self.NEW_GRAD_SIGNALS):
                ai_score = min(ai_score + 10, 100)
                fs_score = min(fs_score + 10, 100)

        return {"ai": round(ai_score), "fullstack": round(fs_score)}

    def _title_score(self, title: str, resume_type: str) -> float:
        """
        Score a job based on title alone (no description available).
        Gives fair credit to entry-level roles even without a full description.
        """
        t = title.lower()

        # Must be a software engineering / tech role
        sw_signals = [
            "software engineer", "software developer", "full stack", "full-stack",
            "backend", "frontend", "ml engineer", "ai engineer", "data engineer",
            "platform engineer", "devops", "python developer", "java developer",
            "machine learning", "data scientist", "swe", "developer",
        ]
        if not any(s in t for s in sw_signals):
            return 30  # Not a relevant role

        # Base score for a relevant SW role
        base = 52

        # Entry-level bonus — these are the jobs we actually want
        entry_signals = [
            "new grad", "new graduate", "entry level", "entry-level",
            "junior", "associate", "0-2 years", "2025", "2026",
            "university grad", "fresh grad", "early career",
        ]
        is_entry = any(s in t for s in entry_signals)
        if is_entry:
            base += 18

        if resume_type == "ai":
            ai_title_kw = [
                "ai", "ml", "machine learning", "llm", "nlp", "data science",
                "python", "generative", "research", "intelligence", "deep learning",
                "neural", "computer vision", "natural language",
            ]
            matches = sum(1 for k in ai_title_kw if k in t)
            return min(base + matches * 7, 90)
        else:
            fs_title_kw = [
                "full stack", "full-stack", "fullstack", "backend", "frontend",
                "react", "python", "java", "node", "typescript", "javascript",
                "software engineer", "software developer", "web",
            ]
            matches = sum(1 for k in fs_title_kw if k in t)
            return min(base + matches * 6, 90)

    def score(self, description: str, resume_ai: str, resume_fullstack: str) -> Dict:
        """
        Full ATS scoring. Uses Groq LLM if available, falls back to keywords.
        Returns dict with ats_score_ai, ats_score_fullstack, best_score, best_resume, tier.
        """
        # Fast keyword pass first
        kw = self.keyword_score(description, resume_ai, resume_fullstack)
        ai_score = kw["ai"]
        fs_score = kw["fullstack"]

        # LLM pass — run on any description with at least a job title
        if self.client and len(description.strip()) > 30:
            llm_ai = self._llm_score(description, resume_ai, "AI-Focused")
            if llm_ai is not None:
                # Take the better of LLM and keyword scores — keyword scoring
                # protects against LLM underscoring short/vague Jooble snippets
                ai_score = max(llm_ai, ai_score)

            llm_fs = self._llm_score(description, resume_fullstack, "Full-Stack")
            if llm_fs is not None:
                fs_score = max(llm_fs, fs_score)

        best_score = max(ai_score, fs_score)
        best_resume = "AI" if ai_score >= fs_score else "Full-Stack"

        return {
            "ats_score_ai": ai_score,
            "ats_score_fullstack": fs_score,
            "best_score": best_score,
            "best_resume": best_resume,
            "tier": self.assign_tier(best_score),
        }

    @staticmethod
    def assign_tier(score: float) -> str:
        if score >= 72:
            return "A"
        elif score >= 58:
            return "B"
        elif score >= 42:
            return "C"
        else:
            return "D"

    # ------------------------------------------------------------------ #
    # Internal helpers                                                      #
    # ------------------------------------------------------------------ #

    def _kw_match(self, text: str, keyword_weights: Dict) -> float:
        total_weight = sum(keyword_weights.values())
        matched_weight = 0
        for kw, weight in keyword_weights.items():
            if kw in text:
                matched_weight += weight
        # Normalize to 0-100, cap at 95 (LLM can push to 100)
        # Use 4x multiplier — large keyword set means even good matches only hit ~20% raw
        raw = (matched_weight / total_weight) * 100
        return min(raw * 4.0, 95)

    def _llm_score(
        self, description: str, resume_text: str, resume_label: str
    ) -> Optional[int]:
        """
        Call Groq LLM to get ATS score. Returns None on failure.
        Sleeps 2s after each call to respect rate limits.
        """
        prompt = f"""You are an ATS (Applicant Tracking System) scoring a new graduate candidate.

CONTEXT: New graduate / entry-level candidate (0-2 years experience).
Score based on ROLE TYPE and TECH STACK ALIGNMENT, not years of experience.

CRITICAL RULES:
1. If the job title is a software engineering role (Software Engineer, SWE, Backend Engineer, Frontend Engineer, Full Stack Engineer, ML Engineer, Data Engineer, Platform Engineer, DevOps, etc.) — minimum score is 60, even if the description is vague or brief.
2. If the job title matches AND the tech stack aligns with the resume — score 75-95.
3. Only score below 45 if the role is clearly NOT software engineering (sales, marketing, operations, HR, design, fitness, etc.).
4. Do NOT penalize for a vague job description — brief Jooble/LinkedIn snippets still represent real SWE jobs.

Scoring guide (0-100):
- 80-95: Role is SWE/ML/Backend/Frontend/Full-Stack AND tech stack clearly aligns with resume
- 65-79: Role is SWE/tech role, partial stack overlap or vague description
- 60-64: Role is SWE/tech but different domain (e.g., embedded systems, gaming if resume is web-focused)
- 45-59: Tech-adjacent role (QA, DevOps, data analyst) with some overlap
- Below 45: Clearly non-engineering role (sales, marketing, design, etc.)

Job Description:
{description[:2500]}

Candidate Resume ({resume_label}):
{resume_text[:2000]}

Respond with ONLY a single integer from 0 to 100. No explanation."""

        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10,
            )
            raw = response.choices[0].message.content.strip()
            # Robust parsing: extract first number found
            m = re.search(r"\b(\d{1,3})\b", raw)
            if m:
                score = int(m.group(1))
                return min(max(score, 0), 100)  # clamp to [0, 100]
        except Exception as e:
            print(f"[ATSScorer] LLM error: {e}")
        finally:
            time.sleep(2)  # rate limit: 30 req/min on free tier

        return None

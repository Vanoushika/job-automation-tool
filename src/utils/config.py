import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")       # optional
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")     # optional

# ── Email ─────────────────────────────────────────────────────────────────────
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "anoushikavennamaneni@gmail.com")

# ── Database ──────────────────────────────────────────────────────────────────
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DB_NAME = "job_automation"

# ── Resume paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent
RESUME_AI_PATH = BASE_DIR / "data" / "resumes" / "resume_ai.txt"
RESUME_FULLSTACK_PATH = BASE_DIR / "data" / "resumes" / "resume_fullstack.txt"

# ── Scheduler ─────────────────────────────────────────────────────────────────
DAILY_RUN_HOUR = int(os.getenv("DAILY_RUN_HOUR", "9"))    # 9 AM
DAILY_RUN_MINUTE = int(os.getenv("DAILY_RUN_MINUTE", "0"))

# ── Pipeline settings ─────────────────────────────────────────────────────────
TARGET_JOBS = 50        # Aim for this many jobs per daily run
MAX_DAYS_OLD = 2        # Max age of job postings to consider


def load_resume(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(
            f"Resume not found: {path}\n"
            f"Please add your resume text to {path}"
        )
    return path.read_text(encoding="utf-8").strip()


def validate():
    """Call on startup to warn about missing configuration."""
    warnings = []
    if not GROQ_API_KEY:
        warnings.append("GROQ_API_KEY not set — using keyword-only ATS scoring")
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        warnings.append("GMAIL_USER / GMAIL_APP_PASSWORD not set — email disabled")
    if not ADZUNA_APP_ID:
        warnings.append("ADZUNA_APP_ID not set — Adzuna source disabled")
    if not RESUME_AI_PATH.exists():
        warnings.append(f"AI resume missing: {RESUME_AI_PATH}")
    if not RESUME_FULLSTACK_PATH.exists():
        warnings.append(f"Full-stack resume missing: {RESUME_FULLSTACK_PATH}")
    for w in warnings:
        print(f"[Config] WARNING: {w}")

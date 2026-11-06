# Job Automation Tool

An automated job-search pipeline: it scrapes job postings, scores them with an LLM against a candidate profile, stores the results, and serves them through an API and web frontend — with a scheduled daily run so new matches surface automatically.

## ✨ What it does

- **Scrapes** job postings from the web (requests / httpx / BeautifulSoup)
- **Scores** each posting for fit using an LLM via the Groq API (`src/scoring`)
- **Stores** postings and scores in MongoDB (`src/database`, PyMongo)
- **Serves** results through a FastAPI backend (`src/api`)
- **Runs daily** on a schedule (APScheduler, `run_daily.py`)

## 🛠️ Tech Stack

- **Python** — core pipeline and backend
- **FastAPI + Uvicorn** — API layer
- **MongoDB (PyMongo)** — persistence
- **Groq API** — LLM-based job scoring
- **APScheduler** — daily scheduled runs
- **BeautifulSoup / lxml / httpx** — scraping

## 📁 Project Structure

```
job-automation-tool/
├── run_daily.py        # Entry point for the scheduled daily pipeline
├── requirements.txt    # Python dependencies
├── .env.example        # Required environment variables (template)
├── src/
│   ├── api/            # FastAPI application
│   ├── database/       # MongoDB access layer
│   ├── scoring/        # LLM scoring of job postings
│   ├── scrapers/       # Site-specific scrapers
│   └── scraper.py      # Core scraping logic
├── scripts/            # Helper scripts
├── frontend/           # Web UI
└── data/               # Local data files
```

## 🚀 Getting Started

```bash
# 1. Clone the repository
git clone https://github.com/Vanoushika/job-automation-tool.git
cd job-automation-tool

# 2. Create a virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# Edit .env with your own API keys and settings — never commit real keys

# 4. Run the daily pipeline
python run_daily.py
```

## 🔐 Configuration

All secrets and environment-specific settings are supplied through a `.env` file based on `.env.example`. No credentials are stored in the repository.

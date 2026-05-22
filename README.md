# 🏃 Smart Marathon Coach API

This is a Flask-based API for syncing Strava activity data, enriching runs, and generating training insights. This repo is part of a multi-phase project — currently in **Milestone 1: Setup & Plumbing**.

---

## 🚀 Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/your-username/railway-pg-test.git
cd railway-pg-test


### 2. Set up your virtual environment

```bash
python -m venv venv
venv\Scripts\activate  # On Windows
# or
source venv/bin/activate  # On Mac/Linux
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 🛠️ Environment Configuration

Copy the example `.env` file and fill in your secrets:

```bash
cp .env.example .env
```

Or manually create `.env` with values like:

```env
DATABASE_URL=postgresql://smartcoach:devpass@postgres:5432/smartcoach

# NOTE: For local dev without Docker, change "postgres" → "localhost"
# DATABASE_URL=postgresql://smartcoach:devpass@localhost:5432/smartcoach

STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
REDIRECT_URI=http://127.0.0.1:5000/oauth/callback
ADMIN_USER=admin
ADMIN_PASS=secret
SECRET_KEY=supersecretkey

```

---

## Strava activity sync (rolling window)

Full sync, filtering after fetch, and `GET .../strava/sync-health` share one window: runs with `start_date` on or after **Monday 00:00 UTC** of the **N**th full ISO week before the current week start, through now. **N** is `STRAVA_INGEST_LOOKBACK_WEEKS` in `src/services/strava_reconciliation_service.py` (currently **2**).

---

## 💻 Running Locally

```bash
python run.py
```

Then open [http://127.0.0.1:5000/ping](http://127.0.0.1:5000/ping)
You should see: `pong`

---

## 🧪 Endpoints (Milestone 1)

| Route           | Description                      |
|-----------------|----------------------------------|
| `/ping`         | Health check                     |
| `/init-db`      | Creates DB tables                |
| `/auth/login`   | Basic credential-based login     |
| `/auth/logout`  | Clear session                    |
| `/enrich/status`| Returns enrichment status (stub) |

> More functionality is coming in Milestone 2

---

## 🧬 GitHub Actions

We’ve added a skeleton workflow in `.github/workflows/cron-sync.yml` that:

- Runs every 6 hours
- Supports manual trigger
- Runs placeholder logic (future expansion)

**Staging → Railway:** `.github/workflows/staging-ci.yml` runs on every push to `staging` (fast `compileall` only, no database). If Railway has **Wait for CI** enabled, that flag requires a successful push workflow; without a matching `on: push: branches: [staging]` job, new commits may never deploy. In the Railway service: **Settings → Source** → trigger branch **staging**, **Autodeploy** enabled, and either leave **Wait for CI** off or keep it on with this workflow green. If deploys are skipped, check **watch paths** (empty = all paths) in the same settings.

---

## 📚 Documentation

Canonical docs under [`docs/`](docs/):

- **Product spec:** [`docs/SMARTCOACH_SYSTEM_SPEC_V1.md`](docs/SMARTCOACH_SYSTEM_SPEC_V1.md)
- **API:** [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md)
- **Phase checklists:** [`docs/PHASE_1_IMPLEMENTATION_CHECKLIST.md`](docs/PHASE_1_IMPLEMENTATION_CHECKLIST.md), [`docs/PHASE_2_IMPLEMENTATION_CHECKLIST.md`](docs/PHASE_2_IMPLEMENTATION_CHECKLIST.md)
- **How docs relate:** [`docs/DOCUMENTATION_GOVERNANCE.md`](docs/DOCUMENTATION_GOVERNANCE.md)
- **Design note (draft):** [`docs/RUN_SUMMARY_SECTIONS_DESIGN_NOTE.md`](docs/RUN_SUMMARY_SECTIONS_DESIGN_NOTE.md) — optional `sections` on opening `run_summary` (“How was my run?”) only

**OAuth helper:** `python src/scripts/verify_oauth_config.py`

---

## 🧩 Project Structure

```bash
railway-pg-test/
├── src/
│   ├── app.py               → Flask app entrypoint
│   ├── routes/              → Route blueprints
│   ├── services/            → Business logic
│   ├── db/                  → Database models + sessions
│   └── utils/               → Utility functions
├── docs/                    → Product spec, API doc, phase checklists (see Documentation)
├── schema.sql               → Creates core DB tables
├── run.py                   → Runs the app
├── requirements.txt
└── .env                     → Environment variables

```

---

## 📦 Requirements

- Python 3.11+
- SQLite or Postgres
- A Strava API App (https://www.strava.com/settings/api)

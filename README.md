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
CRON_SECRET_KEY=your_cron_key
INTERNAL_API_KEY=your_internal_key

```

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

---

## 📚 Documentation

### Strava Production Readiness
- **Main Checklist:** [`docs/strava-production-readiness.md`](docs/strava-production-readiness.md)
- **Process Guide:** [`docs/strava-production-process-guide.md`](docs/strava-production-process-guide.md) - Complete walkthrough
- **OAuth Verification:** [`docs/strava-oauth-verification-checklist.md`](docs/strava-oauth-verification-checklist.md)
- **Verification Script:** `python src/scripts/verify_oauth_config.py`

### Other Documentation
See [`docs/`](docs/) directory for architecture guides, API docs, and setup instructions.

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
├── docs/                    → Documentation (see above)
├── schema.sql               → Creates core DB tables
├── run.py                   → Runs the app
├── requirements.txt
└── .env                     → Environment variables

```

---

## 📦 Requirements

- Python 3.11+
- SQLite or Postgres
- A Strava API App (https://www.strava.com/settings/api)# Triggering redeploy

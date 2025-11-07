# RUN_CRON Usage Analysis

## Summary

`RUN_CRON=true` is **ONLY for local development/testing** - it's not used in production or staging.

## Findings

### ✅ Used Only in Local Development
- **`run.py` line 75**: Used to enable "cron-only mode" when running locally
- When `RUN_CRON=true`, it runs a sync job once and exits
- Requires `ATHLETE_ID` environment variable (also only for local testing)

### ❌ **NOT Used in Production/Staging**

#### Railway Cron Service
- Railway runs: `python src/scripts/metrics_scheduler.py` (directly, from `nixpacks.toml`/`Procfile`)
- **Does NOT use `run.py`** at all
- **Does NOT check `RUN_CRON`** flag

#### GitHub Actions
- Uses: `python -m src.scripts.run_staging_cron` (different script)
- **Does NOT use `run.py`** at all
- **Does NOT check `RUN_CRON`** flag

#### Production Web Server
- Railway runs: `gunicorn run:app` (Flask app, not cron mode)
- **Does NOT use cron mode**

## Code Flow

### Local Development (with RUN_CRON=true)
```bash
# Developer runs locally:
export RUN_CRON=true
export ATHLETE_ID=123456
python run.py
# → Runs sync job once, then exits
```

### Production/Staging (Railway)
```bash
# Railway cron service runs:
python src/scripts/metrics_scheduler.py
# → Long-running scheduler, doesn't use run.py
```

## Recommendation

### ❌ **NOT NEEDED for Production/Staging**

**Reason**:
- Only used for local development convenience
- Railway cron service runs scripts directly, bypassing `run.py`
- Not referenced anywhere in production code paths

### Action Items

1. **Remove from Railway**:
   - Remove `RUN_CRON` from Railway staging backend
   - Remove `RUN_CRON` from Railway cron service (if exists)
   - Remove `RUN_CRON` from Railway production backend (when set up)

2. **Keep for Local Development** (Optional):
   - Can keep in `.env.local` for local testing
   - Useful for developers who want to test sync jobs manually
   - Not required, but convenient

### If Removing from Railway

**Safe to delete** - Railway doesn't use it. The cron service runs `metrics_scheduler.py` directly, which doesn't check `RUN_CRON`.

## Current Cron Setup

| Environment | How Cron Runs | Uses RUN_CRON? |
|-------------|---------------|----------------|
| **Local Dev** | `python run.py` (if RUN_CRON=true) | ✅ Yes (optional) |
| **Railway Cron** | `python src/scripts/metrics_scheduler.py` | ❌ No |
| **GitHub Actions** | `python -m src.scripts.run_staging_cron` | ❌ No |
| **Production** | `python src/scripts/metrics_scheduler.py` | ❌ No |

## Related: ATHLETE_ID

`ATHLETE_ID` is also only for local testing:
- Used in `run.py` when `RUN_CRON=true`
- Defaults to `123456` if not set
- Not used in production (each user has their own athlete_id stored in DB)

## Conclusion

`RUN_CRON=true` is a **local development convenience flag**. It's safe to remove from Railway environments since Railway doesn't use `run.py` for cron jobs.

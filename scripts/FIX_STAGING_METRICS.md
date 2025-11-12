# Fix Staging Metrics Rendering Issue

## Problem
Staging charts are showing incorrect data compared to production, even though the underlying activity data was migrated correctly.

## Root Cause
The materialized view `mv_athlete_metrics` in staging contains stale data. After migrating data from production to staging, the materialized view needs to be refreshed to recalculate the metrics.

## Solution

### Option 1: Use Admin API Endpoint (Recommended)
Call the admin endpoint to refresh metrics:

```bash
# Using curl
curl -X POST https://api.smartcoach.dev/admin/refresh-metrics \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Or use the Admin page in the frontend
# Navigate to /admin and click "🔄 Refresh Metrics" button
```

### Option 2: Refresh via Railway CLI
If you have Railway CLI access:

```bash
railway run --service web-staging python -m src.scripts.refresh_metrics_cron
```

### Option 3: Direct Database Refresh (If you have staging DB access)
If you have direct access to staging database:

```python
# Run this script with STAGING_DATABASE_URL set
python scripts/refresh_staging_metrics.py
```

Or manually:

```sql
REFRESH MATERIALIZED VIEW mv_athlete_metrics;
REFRESH MATERIALIZED VIEW mv_longest_runs;
```

## What Gets Refreshed
- `mv_athlete_metrics`: Weekly trends, dashboard metrics, HR zones
- `mv_longest_runs`: Longest run per week data

## Verification
After refreshing, check that staging charts match production:
1. Weekly distance trends should match
2. Current/previous week metrics should match
3. Pace and run counts should match

## Notes
- The refresh takes 1-2 minutes to complete
- No production data is altered
- This only updates the materialized views in staging


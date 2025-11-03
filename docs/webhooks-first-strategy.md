# Webhooks-First Strategy - Minimizing Polling

**Status:** ✅ Implemented
**Purpose:** Minimize Strava API polling by prioritizing webhooks and using incremental sync

---

## Overview

This implementation ensures we:
1. **Prioritize webhooks** - Use real-time webhook events for new activities (primary method)
2. **Incremental polling** - Only fetch activities after `last_sync_at` when webhooks are active
3. **Full polling fallback** - Only when webhooks are inactive or initial sync

**Result:** Dramatically reduced API calls (95%+ reduction when webhooks are active)

---

## Strategy

### Webhooks-First Approach

```
New Activity Created in Strava
  ↓
Strava sends webhook → activity.create event
  ↓
Webhook processor fetches & stores activity
  ↓
No polling needed! ✅
```

### Incremental Polling (When Needed)

```
Periodic Sync (e.g., daily backup)
  ↓
Check: Are webhooks active? YES
  ↓
Check: When was last sync? (last_sync_at)
  ↓
Only fetch activities after last_sync_at
  ↓
Minimal API calls ✅
```

### Full Polling (Fallback)

```
Initial Sync OR Webhooks Inactive
  ↓
Fetch full history (e.g., 365 days)
  ↓
Store all activities
  ↓
Update last_sync_at
```

---

## Implementation

### 1. Sync Tracking Service (`src/services/sync_tracking_service.py`)

**Functions:**
- `get_last_sync_timestamp()` - Get most recent activity timestamp
- `has_recent_webhook_activity()` - Check if athlete has recent webhook events
- `is_webhook_active()` - Check if webhook subscription is active globally
- `should_use_incremental_sync()` - Determine sync strategy

**Logic:**
```python
# Use incremental sync if:
# 1. Webhooks are active globally
# 2. Athlete has recent webhook activity
# 3. Last sync timestamp exists

# Otherwise: Use full sync
```

### 2. Integrated into Ingestion (`src/services/ingestion_orchestrator_service.py`)

**Changes:**
- Checks webhook status before syncing
- Uses `last_sync_at` for incremental sync when webhooks active
- Falls back to full sync when needed
- Updates `last_sync_at` after successful sync

**Usage:**
```python
# Automatic (webhooks-first)
run_full_ingestion_and_enrichment(session, athlete_id, user_id)

# Force full sync (ignore webhooks)
run_full_ingestion_and_enrichment(
    session, athlete_id, user_id, force_full_sync=True
)
```

---

## How It Works

### Scenario 1: Webhooks Active (Normal Operation)

```
1. User records run in Strava
2. Strava sends webhook → activity.create
3. Webhook processor fetches & stores activity
4. No polling needed ✅

5. Daily backup sync runs
6. Checks: webhooks active? YES
7. Checks: last_sync_at? Yesterday
8. Only fetches activities since yesterday (likely 0-1 new)
9. Minimal API calls ✅
```

### Scenario 2: Webhooks Inactive (Fallback)

```
1. Daily backup sync runs
2. Checks: webhooks active? NO
3. Uses full sync (fetch last 365 days)
4. Deduplicates (most already in DB)
5. Only new activities stored
6. More API calls, but necessary ✅
```

### Scenario 3: Initial Sync (New User)

```
1. User connects Strava
2. Checks: last_sync_at? None
3. Uses full sync (fetch last 365 days)
4. Stores all activities
5. Sets last_sync_at
6. Future syncs will be incremental ✅
```

---

## Benefits

### API Call Reduction

**Before (Polling Only):**
- Daily sync: ~50-200 API calls per athlete
- 20 athletes: 1,000-4,000 calls/day
- Risk of hitting 1000/day limit

**After (Webhooks-First):**
- Webhook events: ~1-5 calls/day per athlete (only new activities)
- Daily backup: ~0-5 calls (only activities since last sync)
- 20 athletes: ~20-100 calls/day
- **95%+ reduction** ✅

### Rate Limit Safety

- Stay well under 1000/day limit
- Room for growth
- Fewer 429 errors
- Better user experience

---

## Monitoring

### Check Webhook Status

```python
from src.services.sync_tracking_service import is_webhook_active

session = get_session()
active = is_webhook_active(session)
print(f"Webhooks active: {active}")
```

### Check Last Sync

```python
from src.services.sync_tracking_service import get_last_sync_timestamp

session = get_session()
last_sync = get_last_sync_timestamp(session, athlete_id)
print(f"Last sync: {last_sync}")
```

### Check Sync Strategy

```python
from src.services.sync_tracking_service import should_use_incremental_sync

session = get_session()
incremental, last_sync = should_use_incremental_sync(session, athlete_id)
print(f"Use incremental: {incremental}, Last sync: {last_sync}")
```

---

## Configuration

### Force Full Sync

If you need to force a full sync (ignore webhook status):

```python
run_full_ingestion_and_enrichment(
    session,
    athlete_id,
    user_id,
    force_full_sync=True  # Override webhook-first strategy
)
```

### Adjust Lookback Days

For incremental sync, the lookback is based on `last_sync_at`. For full sync:

```python
run_full_ingestion_and_enrichment(
    session,
    athlete_id,
    user_id,
    lookback_days=90  # Only fetch last 90 days
)
```

---

## Monitoring

### Track Sync Efficiency

**Query to see sync patterns:**
```sql
-- Check last sync timestamps (most recent activity per athlete)
SELECT
    athlete_id,
    MAX(start_date) as last_activity,
    COUNT(*) as activity_count
FROM activities
GROUP BY athlete_id
ORDER BY last_activity DESC;
```

**Check webhook activity:**
```sql
-- Recent webhook events per athlete
SELECT
    owner_id as athlete_id,
    COUNT(*) as webhook_count,
    MAX(received_at) as last_webhook
FROM webhook_events
WHERE object_type = 'activity'
  AND aspect_type = 'create'
  AND received_at >= NOW() - INTERVAL '7 days'
GROUP BY owner_id;
```

---

## Future Enhancements

### Potential Improvements

1. **Database-Backed Last Sync**
   - Add `last_sync_at` column to `user_athletes` table
   - More explicit tracking (currently uses most recent activity)

2. **Per-Athlete Webhook Status**
   - Track if each athlete is receiving webhooks
   - More granular sync strategy decisions

3. **Smart Polling Interval**
   - Adjust polling frequency based on webhook activity
   - More frequent if webhooks inactive, less if active

4. **Webhook Health Dashboard**
   - Monitor webhook delivery rates per athlete
   - Alert if webhooks stop working

---

## Related Files

- **Sync Tracking:** `src/services/sync_tracking_service.py`
- **Ingestion:** `src/services/ingestion_orchestrator_service.py`
- **Webhook Processor:** `src/services/webhook_processor.py`
- **Webhook Routes:** `src/routes/webhook_routes.py`

---

## Testing

### Test Incremental Sync

```python
from src.services.ingestion_orchestrator_service import run_full_ingestion_and_enrichment
from src.services.sync_tracking_service import should_use_incremental_sync

session = get_session()

# Check strategy
incremental, last_sync = should_use_incremental_sync(session, athlete_id)
print(f"Incremental: {incremental}, Last sync: {last_sync}")

# Run sync (will use incremental if webhooks active)
result = run_full_ingestion_and_enrichment(session, athlete_id, user_id)
print(f"Synced: {result['synced']}, Enriched: {result['enriched']}")
```

### Test Webhook Detection

```python
from src.services.sync_tracking_service import (
    is_webhook_active,
    has_recent_webhook_activity,
)

session = get_session()

# Global webhook status
active = is_webhook_active(session)
print(f"Webhooks active globally: {active}")

# Per-athlete webhook activity
has_activity = has_recent_webhook_activity(session, athlete_id, hours=24)
print(f"Athlete has recent webhook activity: {has_activity}")
```

---

**Last Updated:** November 3, 2025

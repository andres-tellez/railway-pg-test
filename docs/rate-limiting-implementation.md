# Rate Limiting Implementation - Per-Athlete Sync Queue

**Status:** ✅ Implemented
**Purpose:** Queue and serialize per-athlete syncs to respect Strava API limits (100/15m, 1000/day)

---

## Overview

This implementation ensures that when syncing multiple athletes, we:
1. **Queue syncs** - Add athletes to a queue instead of syncing all at once
2. **Respect rate limits** - Track and enforce 100 requests/15min and 1000 requests/day
3. **Process sequentially** - Sync one athlete at a time to avoid overwhelming the API

---

## Components

### 1. Rate Limiter (`src/services/rate_limiter.py`)

Tracks API request timestamps and enforces limits:

**Features:**
- Sliding window tracking (15-minute and 24-hour windows)
- Automatic cleanup of old timestamps
- Wait time calculation
- Safety margin (90% of limit to avoid hitting it)

**Usage:**
```python
from src.services.rate_limiter import get_rate_limiter

rate_limiter = get_rate_limiter()

# Check if we can make a request
if rate_limiter.can_make_request():
    # Make API call
    rate_limiter.record_request()
else:
    # Wait until we can
    wait_time = rate_limiter.get_wait_time()
    time.sleep(wait_time)
```

**Limits:**
- Safe limit: 90 requests per 15 minutes (90% of 100)
- Safe limit: 900 requests per day (90% of 1000)

---

### 2. Sync Queue Service (`src/services/sync_queue_service.py`)

Manages a queue of athletes waiting to sync:

**Features:**
- In-memory queue (can be upgraded to Redis/database-backed)
- Sequential processing
- Rate limit integration
- Automatic user_id lookup

**Usage:**
```python
from src.services.sync_queue_service import queue_athlete_sync, process_sync_queue

# Queue an athlete for syncing
queue_athlete_sync(athlete_id, user_id)

# Process all queued syncs (respecting rate limits)
stats = process_sync_queue()
# Returns: {"processed": 5, "skipped": 0, "failed": 1}
```

**Functions:**
- `queue_athlete_sync(athlete_id, user_id)` - Add athlete to queue
- `process_sync_queue(max_syncs=None)` - Process queue (respects rate limits)
- `queue_all_athletes()` - Queue all athletes in system

---

### 3. Integrated Rate Limiting (`src/services/strava_access_service.py`)

The `StravaClient` now automatically:
- Checks rate limits before each API request
- Waits if necessary
- Records each request

**No code changes needed** - existing code automatically uses rate limiting!

---

## How It Works

### Normal Flow (Single Athlete)

```
User connects Strava
  ↓
Ingestion service called
  ↓
StravaClient makes API calls
  ↓
Rate limiter checks limits
  ↓
If OK: proceed, record request
If not OK: wait, then proceed
  ↓
Sync completes
```

### Batch Flow (Multiple Athletes)

```
Multiple athletes need syncing
  ↓
Each added to sync queue
  ↓
process_sync_queue() called
  ↓
For each athlete in queue:
  - Check rate limits
  - Wait if needed
  - Process sync
  - Record API usage
  ↓
Continue until queue empty or limits hit
```

---

## Rate Limit Tracking

The rate limiter uses **sliding windows**:

**15-Minute Window:**
- Tracks requests in last 15 minutes
- Old requests automatically removed
- If ≥ 90 requests, wait until oldest expires

**24-Hour Window:**
- Tracks requests in last 24 hours
- Old requests automatically removed
- If ≥ 900 requests, wait until oldest expires

**Safety Margin:**
- Uses 90% of actual limits (90/100, 900/1000)
- Prevents accidentally hitting the limit
- Provides buffer for concurrent requests

---

## Usage Examples

### Example 1: Queue Single Athlete

```python
from src.services.sync_queue_service import queue_athlete_sync, process_sync_queue

# User connects Strava
queue_athlete_sync(athlete_id=12345, user_id="user-uuid")

# Process immediately (or wait for batch)
process_sync_queue()
```

### Example 2: Batch Sync All Athletes

```python
from src.services.sync_queue_service import queue_all_athletes, process_sync_queue

# Queue all athletes
queue_all_athletes()

# Process up to 10 at a time (respects rate limits)
process_sync_queue(max_syncs=10)
```

### Example 3: Check Rate Limit Status

```python
from src.services.rate_limiter import get_rate_limiter

rate_limiter = get_rate_limiter()
stats = rate_limiter.get_stats()

print(f"15min: {stats['requests_15min']}/{stats['limit_15min']}")
print(f"24h: {stats['requests_24h']}/{stats['limit_24h']}")
print(f"Can make request: {stats['can_make_request']}")
print(f"Wait time: {stats['wait_time_seconds']}s")
```

---

## Integration Points

### Where Rate Limiting is Applied

1. **StravaClient** (`src/services/strava_access_service.py`)
   - All API requests automatically rate-limited
   - No code changes needed in calling code

2. **Sync Queue** (`src/services/sync_queue_service.py`)
   - Queue processing respects rate limits
   - Automatically waits between athletes

3. **Webhook Processing** (`src/services/webhook_processor.py`)
   - Individual webhook events are rate-limited
   - Sequential processing prevents bursts

---

## Monitoring

### Check Rate Limit Status

```python
from src.services.rate_limiter import get_rate_limiter

rate_limiter = get_rate_limiter()
stats = rate_limiter.get_stats()

# Log current status
logger.info(f"Rate limit: {stats['requests_15min']}/{stats['limit_15min']} (15min), "
            f"{stats['requests_24h']}/{stats['limit_24h']} (24h)")
```

### Check Queue Status

```python
from src.services.sync_queue_service import get_sync_queue

queue = get_sync_queue()
print(f"Queue size: {queue.size()}")
```

---

## Future Enhancements

### Potential Improvements

1. **Database-Backed Queue**
   - Use Redis or PostgreSQL for persistent queue
   - Survive server restarts
   - Better for distributed systems

2. **Per-Athlete Rate Limiting**
   - Track limits per athlete (if using different OAuth apps)
   - Currently uses global limits

3. **Priority Queue**
   - Prioritize certain athletes (e.g., premium users)
   - Process high-priority first

4. **Rate Limit Headers**
   - Parse Strava's rate limit headers from responses
   - More accurate than estimating

5. **Distributed Rate Limiting**
   - Share rate limit state across multiple servers
   - Use Redis for shared state

---

## Testing

### Test Rate Limiter

```python
from src.services.rate_limiter import get_rate_limiter, reset_rate_limiter

# Reset for testing
reset_rate_limiter()

rate_limiter = get_rate_limiter()

# Record some requests
for i in range(95):
    rate_limiter.record_request()

# Check if we can make more
print(rate_limiter.can_make_request())  # False (over 90 limit)

# Get wait time
print(rate_limiter.get_wait_time())  # Seconds until oldest request expires
```

### Test Sync Queue

```python
from src.services.sync_queue_service import (
    get_sync_queue,
    queue_athlete_sync,
    process_sync_queue,
)

# Queue some athletes
queue_athlete_sync(athlete_id=1, user_id="user1")
queue_athlete_sync(athlete_id=2, user_id="user2")

# Process queue
stats = process_sync_queue()
print(stats)  # {"processed": 2, "skipped": 0, "failed": 0}
```

---

## Configuration

### Environment Variables

No new environment variables needed. Rate limiting is automatic.

### Tuning

To adjust safety margin, edit `src/services/rate_limiter.py`:

```python
SAFETY_MARGIN = 0.9  # Use 90% of limit (adjust to 0.95 for more aggressive)
```

---

## Related Files

- **Rate Limiter:** `src/services/rate_limiter.py`
- **Sync Queue:** `src/services/sync_queue_service.py`
- **Strava Client:** `src/services/strava_access_service.py`
- **Ingestion:** `src/services/ingestion_orchestrator_service.py`

---

**Last Updated:** November 3, 2025

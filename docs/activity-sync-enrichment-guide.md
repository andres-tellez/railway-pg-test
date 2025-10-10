# Activity Sync & Enrichment Guide

## Overview
SmartCoach has a comprehensive system for syncing Strava activities, extracting splits, and enriching them with detailed data (heart rate zones, pace zones, etc.).

---

## 🔄 Activity Sync & Enrichment Flow

### **1. Main Orchestration Function**
**File:** `src/services/ingestion_orchestrator_service.py`

**Function:** `run_full_ingestion_and_enrichment()`

**Parameters:**
- `athlete_id` (int) - Strava athlete ID
- `user_id` (UUID) - Internal user ID
- `lookback_days` (int) - How many days back to fetch (default: 365)
- `max_activities` (int) - Maximum activities to download (from config)
- `batch_size` (int) - Enrichment batch size
- `per_page` (int) - Activities per API page
- `after` (timestamp) - Only fetch activities after this time
- `before` (timestamp) - Only fetch activities before this time

**What it does:**
1. ✅ Fetches activities from Strava API
2. ✅ Filters for runs only
3. ✅ Saves new activities to database
4. ✅ Enriches activities with detailed data
5. ✅ Extracts and saves mile splits

---

## 📡 API Endpoints

### **Option 1: Admin Trigger (Recommended for Manual Refresh)**
```
POST /admin/trigger-ingest/<athlete_id>
```

**Query Parameters:**
- `lookback_days` (optional) - Number of days to look back
- `max_activities` (optional, default: 10) - Max activities to fetch

**Example:**
```bash
# Fetch last 30 days of activities
curl -X POST http://localhost:5000/admin/trigger-ingest/347085?lookback_days=30&max_activities=50 \
  -H "Authorization: Bearer <jwt_token>"
```

**Response:**
```json
{
  "status": "success",
  "result": {
    "synced": 15,
    "enriched": 15
  }
}
```

**Location:** `src/routes/admin_routes.py`

---

### **Option 2: Auth Callback Trigger (Automatic on Strava Connect)**
```
POST /auth/trigger-ingest/<athlete_id>
```

**What it does:**
- Automatically triggered after Strava OAuth connection
- Fetches initial activity history
- No authentication required (internal use)

**Location:** `src/routes/auth_routes.py`

---

### **Option 3: Batch Enrichment Only**
```
POST /api/activities/enrich/batch?athlete_id=<id>&batch=<size>
```

**Query Parameters:**
- `athlete_id` (required) - Athlete ID
- `batch` (optional, default: 20) - Number of activities to enrich

**What it does:**
- Enriches existing activities that haven't been enriched yet
- Adds HR zones, splits, detailed metrics
- Does NOT fetch new activities from Strava

**Example:**
```bash
curl -X POST "http://localhost:5000/api/activities/enrich/batch?athlete_id=347085&batch=30" \
  -H "Authorization: Bearer <jwt_token>"
```

**Location:** `src/routes/activity_routes.py`

---

### **Option 4: Single Activity Enrichment**
```
POST /api/activities/enrich/activity/<activity_id>
```

**What it does:**
- Enriches a single specific activity
- Useful for re-enrichment or fixing missing data

**Location:** `src/routes/activity_routes.py`

---

## 🛠️ Core Services

### **1. ActivityIngestionService**
**File:** `src/services/activity_service.py`

**Methods:**

#### `fetch_all_activities(after, before, per_page, limit)`
- Fetches activities from Strava with pagination
- Handles rate limiting and retries
- Returns raw Strava activity data

#### `ingest_full_history(lookback_days, max_activities, per_page)`
- Fetches all activities within lookback period
- Filters for runs only
- Saves to database with deduplication
- Injects user_id for multi-user support

#### `ingest_between(start_date, end_date, max_activities)`
- Fetches activities within specific date range
- Useful for targeted syncs

---

### **2. Enrichment Functions**

#### `enrich_one_activity(session, access_token, activity_id)`
**What it does:**
1. Fetches detailed activity data from Strava
2. Gets HR zone data
3. Fetches activity streams (distance, time, velocity, HR)
4. Extracts HR zone percentages
5. Builds mile splits from streams
6. Updates database with enriched data

**Data Extracted:**
- ✅ Heart rate zones (% time in each zone)
- ✅ Mile splits with pace, HR, elevation
- ✅ Average speed, max speed
- ✅ Suffer score (if available)
- ✅ Calories burned

#### `build_mile_splits(activity_id, streams)`
**What it does:**
- Analyzes distance/time/velocity/HR streams
- Identifies mile markers
- Calculates per-mile metrics:
  - Split time
  - Average pace
  - Average heart rate
  - Pace zone classification

---

### **3. StravaClient**
**File:** `src/services/strava_access_service.py`

**Methods:**

#### `get_activities(after, before, limit, per_page)`
- Wrapper for Strava `/athlete/activities` API
- Handles pagination automatically
- Implements exponential backoff for rate limits
- Supports date filtering with Unix timestamps

#### `get_activity(activity_id)`
- Fetches single activity detail
- Returns full activity JSON

#### `get_hr_zones(activity_id)`
- Fetches HR zone distribution for activity

#### `get_streams(activity_id, keys)`
- Fetches time-series data streams
- Keys: `['distance', 'time', 'velocity_smooth', 'heartrate']`

---

## 📊 Data Flow Diagram

```
┌─────────────────────────────────────────────┐
│  1. Trigger Endpoint                        │
│  POST /admin/trigger-ingest/:athlete_id     │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  2. run_full_ingestion_and_enrichment()     │
│  • Calculates date window                   │
│  • Fetches from Strava                      │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  3. StravaClient.get_activities()           │
│  • Paginates through activities             │
│  • Returns raw JSON                         │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  4. Filter & Deduplicate                    │
│  • Type == "Run" only                       │
│  • Check existing activity_ids              │
│  • Inject user_id                           │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  5. ActivityDAO.upsert_activities()         │
│  • Save to activities table                 │
│  • Convert units (m/s → mph, m → mi)        │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  6. run_enrichment_batch()                  │
│  • Find unenriched activities               │
│  • Process in batches                       │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  7. enrich_one_activity()                   │
│  • Fetch detailed activity                  │
│  • Get HR zones                             │
│  • Get streams                              │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  8. Update Database                         │
│  • Update activities with HR zones          │
│  • Save splits to splits table              │
└─────────────────────────────────────────────┘
```

---

## 🔧 Key Configuration

**File:** `src/utils/config.py`

```python
MAX_ACTIVITIES_TO_DOWNLOAD = 1000  # Max activities per sync
MIN_ACTIVITIES_REQUIRED = 10       # Min for training plan generation
STRAVA_API_BASE_URL = "https://www.strava.com/api/v3"
```

---

## 💾 Database Tables

### **activities**
- Stores basic activity data
- Columns: `activity_id`, `athlete_id`, `user_id`, `name`, `type`, `distance`, `moving_time`, etc.
- Enrichment adds: `hr_zone_1` through `hr_zone_5`, `average_heartrate`, `suffer_score`

### **splits**
- Stores mile-by-mile split data
- Columns: `activity_id`, `lap_index`, `split`, `average_speed`, `average_heartrate`, `pace_zone`
- Built from Strava streams

### **user_athletes**
- Maps user_id (UUID) to athlete_id (Strava ID)
- Used to identify which user owns which activities

---

## 🚀 Usage Examples

### **1. Refresh Last 7 Days of Activities**
```python
from src.services.ingestion_orchestrator_service import run_full_ingestion_and_enrichment
from src.db.db_session import get_session

session = get_session()
result = run_full_ingestion_and_enrichment(
    session,
    athlete_id=347085,
    user_id="ddc21831-1b01-4cfc-82db-7632ab2cfba1",
    lookback_days=7,
    max_activities=50
)
print(f"Synced: {result['synced']}, Enriched: {result['enriched']}")
```

### **2. Enrich Existing Activities (No New Fetch)**
```python
from src.services.activity_service import run_enrichment_batch
from src.db.db_session import get_session

session = get_session()
enriched_count = run_enrichment_batch(
    session,
    athlete_id=347085,
    batch_size=20
)
print(f"Enriched {enriched_count} activities")
```

### **3. API Call to Refresh Activities**
```bash
# Get JWT token
TOKEN="your_jwt_token_here"

# Refresh last 30 days
curl -X POST "http://localhost:5000/admin/trigger-ingest/347085?lookback_days=30&max_activities=100" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

---

## 🎯 Best Practices

### **For Metrics Dashboard Refresh:**
1. **Use admin trigger endpoint** with specific lookback period
2. **Limit max_activities** to avoid rate limits (50-100 recommended)
3. **Run enrichment batch** after sync to ensure all data is complete

### **Recommended Refresh Strategy:**
```bash
# Step 1: Sync last 7 days (catches new activities)
POST /admin/trigger-ingest/347085?lookback_days=7&max_activities=50

# Step 2: Enrich any missing data
POST /api/activities/enrich/batch?athlete_id=347085&batch=30
```

### **Rate Limiting:**
- Strava API limits: 100 requests per 15 minutes, 1000 per day
- Built-in exponential backoff handles 429 errors
- Batch processing prevents overwhelming the API

---

## 🐛 Troubleshooting

### **Problem: Activities not showing in metrics**
**Solution:** 
1. Check if activities exist: `SELECT COUNT(*) FROM activities WHERE athlete_id = X`
2. Run enrichment batch to add missing HR zones
3. Verify date range matches your query

### **Problem: Missing splits data**
**Solution:**
1. Splits require stream data from Strava
2. Run enrichment: `POST /api/activities/enrich/batch`
3. Check if activity has GPS data (indoor runs may not have streams)

### **Problem: Strava rate limit errors**
**Solution:**
- Reduce `max_activities` parameter
- Add delays between requests (built-in backoff handles this)
- Wait 15 minutes for rate limit reset

---

## 📝 Future Enhancements

### **Planned Features:**
1. **Automatic background refresh** - Cron job to sync daily
2. **Webhook integration** - Real-time sync when Strava activities are created
3. **Selective enrichment** - Only enrich activities needed for metrics
4. **Incremental sync** - Only fetch activities newer than latest in DB

### **Potential New Endpoints:**
- `POST /api/activities/refresh` - User-friendly refresh for last X days
- `GET /api/activities/sync-status` - Check sync progress and last sync time
- `POST /api/activities/refresh-metrics` - Sync + recalculate dashboard metrics

---

## 🔗 Related Files

- **Orchestration:** `src/services/ingestion_orchestrator_service.py`
- **Activity Service:** `src/services/activity_service.py`
- **Strava Client:** `src/services/strava_access_service.py`
- **Admin Routes:** `src/routes/admin_routes.py`
- **Activity Routes:** `src/routes/activity_routes.py`
- **DAO:** `src/db/dao/activity_dao.py`
- **Models:** `src/db/models/activities.py`, `src/db/models/splits.py`

---

**Last Updated:** October 9, 2025  
**Author:** SmartCoach Development Team


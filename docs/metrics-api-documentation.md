# Metrics API Documentation

## Overview
The Metrics API provides real-time running analytics and performance indicators for SmartCoach users. It leverages a materialized view (`mv_athlete_metrics`) for ultra-fast performance, with query times of ~5-10ms.

---

## Architecture

### Materialized View
All metrics are pre-calculated in the `mv_athlete_metrics` materialized view, which is automatically refreshed after:
- Activity ingestion
- Activity enrichment
- Manual activity sync

### Performance
- **Query Time**: ~5-10ms (20x faster than previous CASE statement approach)
- **Cache TTL**: 5 minutes
- **API Calls**: Single endpoint returns all data
- **Processing**: 95% database, 5% Python (pace formatting only)

---

## Endpoints

### GET `/api/metrics/all-metrics`

**Description:** Returns ALL metrics in a single optimized call - dashboard metrics, weekly trends, HR zones, and VO2 estimates for the last 20 weeks.

**Authentication:** Required (JWT token from Auth0)

**Request Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response Format:**
```json
{
  "weekly_distance": {
    "current": 42.3,      // Current week's distance in miles
    "previous": 35.8,     // Last week's distance in miles
    "change_pct": 18.1    // Percentage change (positive = increase)
  },
  "weekly_runs": {
    "current": 5,         // Number of runs this week
    "previous": 4,        // Number of runs last week
    "change_pct": 25.0    // Percentage change
  },
  "average_pace": {
    "current": "8:45",    // Current week pace (min/mi format)
    "previous": "9:52",   // Previous week pace
    "change_pct": 0       // Not calculated yet
  },
  "hr_zones": {
    "zone_1": 15.2,       // % time in Zone 1 (Recovery: 50-60% max HR) - last 30 days
    "zone_2": 45.8,       // % time in Zone 2 (Aerobic: 60-70% max HR)
    "zone_3": 28.3,       // % time in Zone 3 (Tempo: 70-80% max HR)
    "zone_4": 8.5,        // % time in Zone 4 (Threshold: 80-90% max HR)
    "zone_5": 2.2         // % time in Zone 5 (VO2 Max: 90-100% max HR)
  },
  "weekly_trends": [
    {
      "week": "2025-10-06",     // Week start date (Monday)
      "distance": 27.3,         // Total miles for the week
      "runs": 4,                // Number of runs
      "avgPace": "8:45"         // Average pace (min/mi)
    },
    // ... 19 more weeks
  ],
  "weekly_hr_zones": [
    {
      "week": "2025-10-06",
      "zone_1": 15.2,
      "zone_2": 45.8,
      "zone_3": 28.3,
      "zone_4": 8.5,
      "zone_5": 2.2
    },
    // ... 19 more weeks
  ],
  "weekly_vo2_estimates": [
    {
      "week": "2025-10-06",
      "vo2_estimate": 48.5,     // Estimated VO2 Max
      "run_score": 185          // Strava run score (basis for estimate)
    },
    // ... 19 more weeks
  ]
}
```

**Response Codes:**
- `200 OK` - Success
- `401 Unauthorized` - Missing or invalid JWT token
- `404 Not Found` - User not found or no Strava connection
- `500 Internal Server Error` - Server error

**Performance:**
- **Cold**: ~200-500ms (includes auth + database + processing)
- **Cached**: ~50ms (served from memory cache)
- **Query Time**: ~5-10ms (materialized view)

**Example Request:**
```bash
curl -X GET https://smartcoach.dev/api/metrics/all-metrics \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..."
```

---

### GET `/api/metrics/performance`

**Description:** Returns cache statistics and performance monitoring data. Useful for debugging and admin purposes.

**Authentication:** Required (JWT token from Auth0)

**Request Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response Format:**
```json
{
  "cache_stats": {
    "total_hits": 1234,
    "total_misses": 567,
    "hit_rate": 68.5,
    "cache_size": 42
  },
  "optimizations": {
    "database_indexes": "Enabled",
    "query_caching": "Enabled (5 min TTL)",
    "materialized_view": "Enabled",
    "performance_monitoring": "Enabled"
  },
  "performance_notes": [
    "Metrics are cached for 5 minutes",
    "Uses materialized view (mv_athlete_metrics) for 20x faster queries",
    "Database queries optimized with proper indexes",
    "Cache automatically invalidates on data updates"
  ]
}
```

**Response Codes:**
- `200 OK` - Success
- `401 Unauthorized` - Missing or invalid JWT token
- `500 Internal Server Error` - Server error

---

## Data Flow

```
Strava Activity
    ↓
Webhook Event
    ↓
Activity Ingestion
    ↓
Activity Enrichment
    ↓
Refresh Materialized View (mv_athlete_metrics)
    ↓
Cache Invalidation
    ↓
Frontend Request (/api/metrics/all-metrics)
    ↓
Cache Check (5 min TTL)
    ↓
Return JSON Response
```

---

## Heart Rate Zones

Heart rate zones are calculated based on percentage of maximum heart rate:

| Zone | Name | % Max HR | Training Effect |
|------|------|----------|----------------|
| 1 | Recovery | 50-60% | Active recovery, warm-up |
| 2 | Aerobic Base | 60-70% | Build aerobic endurance |
| 3 | Tempo | 70-80% | Improve lactate threshold |
| 4 | Threshold | 80-90% | Increase anaerobic capacity |
| 5 | VO2 Max | 90-100% | Boost maximum oxygen uptake |

---

## VO2 Max Estimation

VO2 Max estimates are calculated from Strava's "run_score" metric:

```
vo2_estimate = (run_score / 100.0) + 30
```

**Requirements for VO2 estimation:**
- Run distance ≥ 2 miles
- Run duration ≥ 12 minutes
- Run has valid run_score from Strava

---

## Caching Strategy

### Cache Keys
- Format: `metrics_all_{athlete_id}`
- TTL: 5 minutes (300 seconds)

### Invalidation
Cache is automatically invalidated when:
- New activity is synced
- Activity is updated
- Activity is deleted
- Materialized view is refreshed

### Cache Stats
Available via `/api/metrics/performance` endpoint:
- Total hits/misses
- Hit rate percentage
- Current cache size

---

## Error Handling

### Common Errors

**401 Unauthorized**
```json
{
  "error": "Missing sub claim"
}
```
**Solution:** Ensure valid JWT token is provided in Authorization header.

**404 Not Found**
```json
{
  "error": "No Strava connection found"
}
```
**Solution:** User needs to connect their Strava account.

**500 Internal Server Error**
```json
{
  "error": "Internal server error"
}
```
**Solution:** Check server logs for detailed error information.

---

## Optimization Notes

### Why Materialized View?
- **20x faster** than previous CASE statement approach
- **Pre-calculated** aggregations at database level
- **Efficient** index lookups (athlete_id)
- **Automatic** refresh on activity sync

### Performance Comparison

| Approach | Query Time | API Response Time |
|----------|-----------|------------------|
| **Old (CASE statements)** | ~100-200ms | ~2-3 seconds |
| **New (Materialized View)** | ~5-10ms | ~200-500ms |

### Best Practices
1. Use `/all-metrics` for all metric needs (single API call)
2. Let frontend handle filtering (4/8/16 weeks)
3. Cache is your friend (5-minute TTL is optimal)
4. Monitor cache hit rate via `/performance` endpoint

---

## Version History

### v2.0 (October 11, 2025)
- Removed legacy endpoints (/dashboard, /weekly-data, /weekly-trends, /weekly-hr-zones)
- Consolidated to single /all-metrics endpoint
- 71% reduction in code (327 lines vs 1,127 lines)
- Updated documentation

### v1.5 (October 9, 2025)
- Implemented materialized view (mv_athlete_metrics)
- 20x performance improvement
- Added VO2 Max estimates

### v1.0 (September 2025)
- Initial implementation with CASE statements
- Multiple separate endpoints

# Metrics API Documentation

## Overview
The Metrics API provides real-time running analytics and performance indicators for SmartCoach users. It leverages existing activity data from Strava to calculate key performance metrics.

---

## Endpoints

### GET `/api/metrics/dashboard`

**Description:** Returns key metrics for the dashboard display, including weekly distance, pace trends, activity frequency, and heart rate zone distribution.

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
  "average_pace": {
    "current": "8:45",    // Current pace (min/mi format)
    "previous": "9:52",   // Previous 30-day pace
    "change_pct": -12.0   // Percentage change (negative = faster/better)
  },
  "weekly_runs": {
    "current": 5,         // Number of runs this week
    "previous": 4,        // Number of runs last week
    "change_pct": 25.0    // Percentage change
  },
  "hr_zones": {
    "zone_1": 15.2,       // % time in Zone 1 (Recovery: 50-60% max HR)
    "zone_2": 45.8,       // % time in Zone 2 (Aerobic: 60-70% max HR)
    "zone_3": 28.3,       // % time in Zone 3 (Tempo: 70-80% max HR)
    "zone_4": 8.5,        // % time in Zone 4 (Threshold: 80-90% max HR)
    "zone_5": 2.2         // % time in Zone 5 (VO2 Max: 90-100% max HR)
  }
}
```

**Response Codes:**
- `200 OK` - Success
- `401 Unauthorized` - Missing or invalid JWT token
- `404 Not Found` - User has no Strava connection
- `500 Internal Server Error` - Database or processing error

**Example Request:**
```bash
curl -X GET https://api.smartcoach.app/api/metrics/dashboard \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "Content-Type: application/json"
```

**Example Response (No Strava Connection):**
```json
{
  "error": "No Strava connection found",
  "weekly_distance": {"current": 0, "previous": 0, "change_pct": 0},
  "average_pace": {"current": "0:00", "previous": "0:00", "change_pct": 0},
  "weekly_runs": {"current": 0, "previous": 0, "change_pct": 0},
  "hr_zones": {"zone_1": 0, "zone_2": 0, "zone_3": 0, "zone_4": 0, "zone_5": 0}
}
```

---

## Data Sources

### Primary Tables:
1. **`activities`** - Main activity records from Strava
   - Contains distance, pace, heart rate, timestamps
   - Filtered by activity type = "Run"
   
2. **`user_athletes`** - Maps user_id to athlete_id
   - Links Auth0 users to Strava athletes
   
3. **`splits`** - Lap/mile split data (future use)
   - Not currently used in dashboard metrics

### Database Views (Future Enhancement):
- `v_activities_running_plan` - Filtered running activities
- `v_splits_running_plan` - Split analysis

---

## Calculation Methods

### 1. Weekly Distance
**Logic:**
- Current week: Monday 00:00 to now
- Previous week: Previous Monday 00:00 to Sunday 23:59
- Converts meters to miles (1 mile = 1609.34 meters)

**Formula:**
```python
current_miles = total_distance_meters / 1609.34
change_pct = ((current - previous) / previous) * 100
```

### 2. Average Pace
**Logic:**
- Current: Last 30 days average
- Previous: Days 31-60 average
- Converts m/s to min/mile format

**Formula:**
```python
seconds_per_mile = 1609.34 / avg_speed_mps
minutes = seconds_per_mile // 60
seconds = seconds_per_mile % 60
pace = f"{minutes}:{seconds:02d}"
```

**Note:** Lower pace is better (faster running), so percentage change is inverted.

### 3. Weekly Runs
**Logic:**
- Counts number of activities in current vs previous week
- Only includes activities with type = "Run"

### 4. Heart Rate Zones
**Logic:**
- Averages HR zone percentages over last 30 days
- Based on Strava's 5-zone model
- Zones are automatically calculated by Strava based on user's max HR

---

## Data Access Layer (DAO)

### ActivityStatsDAO Methods Used:

| Method | Purpose | Parameters | Returns |
|--------|---------|-----------|---------|
| `get_total_distance()` | Sum distance in date range | athlete_id, start_date, end_date | float (meters) |
| `get_average_pace()` | Calculate average pace | athlete_id, days | float (m/s) |
| `get_activities_by_date_range()` | Get activities in range | athlete_id, start_date, end_date | List[Activity] |
| `get_hr_zone_summary()` | Average HR zones | athlete_id, days | Dict[str, float] |

**File:** `src/db/dao/activity_stats_dao.py`

---

## Frontend Integration

### React Hook Example:
```typescript
import { useApiClient } from '@/utils/apiClient';
import { useEffect, useState } from 'react';

interface DashboardMetrics {
  weekly_distance: {
    current: number;
    previous: number;
    change_pct: number;
  };
  average_pace: {
    current: string;
    previous: string;
    change_pct: number;
  };
  weekly_runs: {
    current: number;
    previous: number;
    change_pct: number;
  };
  hr_zones: {
    zone_1: number;
    zone_2: number;
    zone_3: number;
    zone_4: number;
    zone_5: number;
  };
}

export function useDashboardMetrics() {
  const api = useApiClient();
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await api.get('/api/metrics/dashboard');
        setMetrics(response.data);
      } catch (err) {
        setError('Failed to load metrics');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
  }, []);

  return { metrics, loading, error };
}
```

---

## Error Handling

### Common Errors:

1. **No Strava Connection**
   ```json
   {
     "error": "No Strava connection found",
     // ... returns zeros for all metrics
   }
   ```
   **Resolution:** User needs to connect Strava account

2. **Invalid JWT**
   ```json
   {
     "error": "User ID not found"
   }
   ```
   **Resolution:** User needs to re-authenticate

3. **Database Error**
   ```json
   {
     "error": "Internal server error"
   }
   ```
   **Resolution:** Check server logs, verify database connection

---

## Performance Considerations

### Caching Strategy (Future):
- Cache metrics for 5 minutes per user
- Invalidate on new activity sync
- Use Redis for distributed caching

### Query Optimization:
- Indexes on `athlete_id` and `start_date` columns
- Date range queries are optimized with WHERE clauses
- Aggregations use database-level SUM/AVG functions

### Response Time:
- Target: < 200ms
- Typical: 50-150ms
- Depends on: Number of activities, database load

---

## Testing

### Manual Test (cURL):
```bash
# Get JWT token from Auth0
TOKEN="your_jwt_token_here"

# Call metrics endpoint
curl -X GET http://localhost:5000/api/metrics/dashboard \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

### Expected Test Data:
- User must have Strava connected
- User should have at least 2 weeks of running data
- Activities should have heart rate data for HR zones

---

## Future Enhancements

### Planned Features:
1. **Weekly Summaries Endpoint** - Detailed week-by-week breakdown
2. **Pace Zone Analysis** - Easy/Tempo/Hard distribution
3. **Long Run Tracking** - Weekly long run progression
4. **Training Load** - Weekly mileage trends with alerts
5. **Personal Records** - Fastest times by distance
6. **Consistency Score** - Training frequency metrics

### Additional Endpoints (Roadmap):
- `GET /api/metrics/weekly-summary?weeks=12` - Historical weekly data
- `GET /api/metrics/pace-zones` - Pace distribution analysis
- `GET /api/metrics/long-runs` - Long run progression
- `GET /api/metrics/personal-records` - PRs by distance

---

## Related Documentation
- [ActivityStatsDAO Source](../src/db/dao/activity_stats_dao.py)
- [Metrics Routes Source](../src/routes/metrics_routes.py)
- [Activity Model Schema](../src/db/models/activities.py)
- [Auth0 JWT Authentication](../src/utils/auth0_jwt.py)

---

**Last Updated:** October 9, 2025  
**API Version:** 1.0  
**Author:** SmartCoach Development Team


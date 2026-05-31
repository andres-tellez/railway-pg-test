# Heart Rate Zone Services

## Purpose

Provides HRmax estimation from Strava activities and Karvonen zone calculation
for users without paid Strava subscriptions.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Route Layer                          │
│                  (heart_rate_routes.py)                      │
└─────────────────────┬───────────────────────────────────────┘
                      │ calls
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Orchestration Service                           │
│       (heart_rate_orchestration_service.py)                 │
│  • Fetches data from database                                │
│  • Coordinates other services                                │
│  • Handles user context                                      │
└─────┬───────────────────┬───────────────────┬───────────────┘
      │                   │                   │
      │ calls             │ calls             │ calls
      ▼                   ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐
│  Resolution  │  │  Estimation  │  │   Karvonen Zone      │
│   Service    │  │   Service    │  │      Service         │
│              │  │              │  │                      │
│  (Pure)      │  │  (Pure)      │  │   (Pure)             │
└──────────────┘  └──────────────┘  └──────────────────────┘
      │                   │                   │
      └───────────────────┴───────────────────┘
                         │
                         ▼
                  ┌──────────────┐
                  │  Dataclasses │
                  │  (Results)   │
                  └──────────────┘
```

## File Responsibilities

### heart_rate_orchestration_service.py
- Main entry point for routes
- Fetches activities from database
- Coordinates resolution → estimation → zone calculation
- Returns complete result to route

### hrmax_estimation_service.py
- Pure calculation: estimates HRmax from activities
- No database access
- No user context
- Returns `HRMaxEstimationResult` dataclass

### karvonen_zone_service.py
- Pure calculation: calculates Karvonen zones
- No database access
- Returns `KarvonenZonesResult` dataclass

### hrmax_resolution_service.py
- Determines effective HRmax (USER vs AUTO)
- Checks if recalculation needed
- Pure logic (no DB, but may receive profile dict)

### validation.py
- Input shape/type validation only
- Pre-service validation
- NO physiological range validation (services do this)

## Guardrails

See [GUARDRAILS.md](GUARDRAILS.md) for complete rules.

### Key Rules:
- Pure services never import each other
- Constants only in `hr_zone_constants.py`
- Data fetching only in orchestration service
- Zones calculated through orchestration only
- No user_id in service layer logs

## Example Usage

### In Route Handler

```python
from src.services.heart_rate import HeartRateZoneOrchestrationService

result = HeartRateZoneOrchestrationService.calculate_zones_for_user(
    session, user_id
)

if result["success"]:
    return success_response(result)
else:
    return error_response(
        result["error_message"],
        error_code=result["error_code"]
    )
```

### Using Pure Services Directly

```python
from src.services.heart_rate import (
    HRMaxEstimationService,
    KarvonenZoneService,
)

# Estimate HRmax (no DB access)
activities = [...]  # List of activity dicts
hrmax_result = HRMaxEstimationService.estimate_hrmax(activities)

if hrmax_result.success:
    # Calculate zones (no DB access)
    zones_result = KarvonenZoneService.calculate_zones(
        hrmax_result.hrmax,
        resting_hr=60
    )
```

## Import Patterns

### From Routes
```python
from src.services.heart_rate import HeartRateZoneOrchestrationService
```

### From Other Services
```python
from src.services.heart_rate import (
    KarvonenZoneService,
    HRMaxResolutionService,
)
```

## Data Flow

1. **Route** receives request
2. **Orchestration Service** fetches activities from DB
3. **Resolution Service** determines effective HRmax
4. **Estimation Service** estimates HRmax if needed (pure calculation)
5. **Karvonen Service** calculates zones (pure calculation)
6. **Route** returns JSON response

## Dependencies

- All constants: `src/utils/hr_zone_constants.py`
- Database models: `src/db/models/user_profile.py`
- Database DAOs: `src/db/dao/user_profile_dao.py`

## HR Zone Status Contract (Canonical Truth)

The `/api/heart-rate/zones/status` endpoint returns diagnostic information about zone readiness. This table defines the canonical meaning of each field:

| Field | Meaning | Values |
|-------|---------|--------|
| `ready` | Zones can be calculated | `true` / `false` |
| `method` | Which calculation path applies | `"KARVONEN"` / `"SIMPLE_PERCENTAGE"` / `null` |
| `accuracy_tier` | UX indicator for zone quality | `"HIGH"` / `"MEDIUM"` / `"LOW"` |
| `next_action` | Single action user must take next | See `NEXT_ACTION_PRIORITY` in constants |
| `issues` | List of blockers | Array of `HR_ZONE_ISSUES` enum values |
| `readiness` | Structural diagnostics | Object with detailed readiness info |
| `hrmax_source` | How HRmax was determined | `"USER"` / `"AUTO"` / `"STRAVA"` |
| `resting_hr_source` | How resting HR was determined | `"USER"` / `"APPLE_HEALTH"` / `null` (`ESTIMATED` legacy) |
| `activities_needed` | Count of activities needed for estimation | Integer (0+ if ready) |
| `zones` | Zone boundaries | **Always `null` in status endpoint** |
| `confidence` | HRmax estimation confidence | **Always `null` in status endpoint** |
| `accuracy_warning` | Warning message | **Always `null` in status endpoint** |

**Critical Rules:**
- Status endpoint **NEVER** calculates zones (read-only diagnostics)
- Zones are returned by `/zones/current` or `/zones/calculate` only
- `accuracy_tier` is a UX indicator, NOT a physiological reliability measure
- Status endpoint has no side effects (no DB writes)

**Next Action Priority (canonical order):**
1. `connect_strava` - Highest priority (must connect Strava first)
2. `add_resting_hr` - Resting HR is required for Karvonen zones
3. `run_more_activities` - Need more data for HRmax estimation
4. `view_zones` - Zones are ready, user can view them
5. `improve_accuracy` - Lowest priority (zones work but could be better)

**Accuracy Tiers (UX indicator, not physiological):**
- `HIGH`: User RHR provided + high confidence HRmax
- `MEDIUM`: User RHR with moderate HRmax confidence
- `LOW`: pct_max fallback (max HR set, resting HR missing) or low-confidence inputs

Note: Accuracy tier indicates user experience expectations, NOT physiological zone reliability. Do not treat as a scientific measure.

## Testing

See `tests/services/heart_rate/` for comprehensive test suite.

Test guardrails:
- Use dict fixtures only (no real API calls)
- No stream mocking in v1 tests
- Tests must be fast and pure

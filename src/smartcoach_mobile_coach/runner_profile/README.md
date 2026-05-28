# Runner profile — logic hub (Tier 1)

## Three-tier model

| Tier | Package / surface | Owns |
|------|-------------------|------|
| **1 — Logic hub** | `runner_profile/` + `GET /api/runner-profile/zones` | HR zones, calibrated pace, run definitions, marathon goal-aligned targets |
| **2 — Execution facts** | `execution_analytics/` | Per-run `insights_system`, easy/tempo KPIs, tempo segment columns on `activities` |
| **3 — Product** | `weekly_insights_service`, `training_kpi_service`, coach tools | Weekly rollups and chart assembly from stored facts |

Tier 2 calls `get_runner_profile` only. Tier 3 reads `activities` execution columns — not SQL views.

## Plan definitions authority

Run-type zone mapping, workout taxonomy, and placement roles are owned by this package:

| Module | Owns |
|--------|------|
| `plan_run_type_registry.py` | Canonical keys, zone mapping, display names, scoring tolerances |
| `plan_workout_taxonomy.py` | `WORKOUT_DEFINITIONS`, quality flags, detail archetypes |
| `plan_placement.py` | Placement roles (easy/steady/endurance/long), mileage shares |
| `service.py` | Facades for plan generation, storage, and HR/pace targets |

Plan pipeline code should import from `src.smartcoach_mobile_coach.runner_profile`
(or the specific submodule above).

## HTTP API — `GET /api/runner-profile/zones`

Exposes:

- **`inputs`** — `{ hrmax, resting_hr, target_time, race_distance, goal_aligned_status }` so clients see what drove goal-aligned pace bands
- **`run_type_registry`** — canonical run types + zone/Insights mapping (Steady → Z3/tempo)
- **`plan_workout_taxonomy`** — read-only taxonomy slice
- **`pace_authorities`** — explicit split between plan (activity median) and Insights (marathon goal)

### Goal-aligned pace (`goal_aligned_status`)

| Status | Meaning |
|--------|---------|
| `active` | Marathon plan + valid target time → goal bands present |
| `missing_target_time` | Marathon-capable plan but no goal time |
| `unsupported_race` | Race distance has no goal config yet (e.g. Half Marathon) |
| `unavailable` | Config + time present but bands could not be built |

**Half marathon later:** add a `GoalAlignedPaceConfig` branch in
`resolve_goal_aligned_config()` — no consumer/API shape changes required.

## Pace authorities

| Consumer | Authority | Source |
|----------|-----------|--------|
| Plan Pass4 segments | Activity-calibrated | `get_runner_pace_zones_for_plan_generation` |
| Plan row `pace_ranges` | Persisted profile bands | `runner_pace_ranges_payload` |
| Insights Easy Avg Pace | Marathon goal | `training_pace_recommendations.pace_progress` |
| Insights Tempo Avg Pace | Marathon goal Z3 | `training_pace_recommendations.tempo_pace_progress` |

## Insights tab API bundle

Mobile Insights opens with **`GET /api/training-insights/weekly-history`** only (no
`/zones` or `/weekly` on tab load).

| Endpoint | Role on Insights |
|----------|------------------|
| **`/api/training-insights/weekly-history`** | Charts, display authority, `latest_week` scoreboard |
| **`/api/runner-profile/zones`** | Plan, Profile, Coach (not Insights open) |
| **`/api/training-insights/weekly`** | Coach tools and other consumers |

### `weekly-history.systems` authority split

| Slice | Source | Stored at write time? |
|-------|--------|----------------------|
| Easy pace / HR progress (banner, footnotes, chart zones) | Profile `training_pace_recommendations` | No (recomputed from profile on read) |
| Easy drift / efficiency (footnotes, chart zones) | Global `easy_kpi/` defaults | N/A (app-wide constants) |
| Easy chart dot bands (`easy_pace_progress_band`, etc.) | Classified at insight generation | Yes — `weekly_training_insights` columns |
| Tempo pace / HR progress (banner, footnotes, chart zones) | Profile `tempo_pace_progress` / `tempo_hr_progress` | No |
| Tempo chart dot GYOR bands | Classified at insight generation | Yes — `kpi_snapshot.systems.tempo.bands` |

Legacy insight rows without stored bands still classify on read using current profile
targets (same fallback pattern as Easy Step 5).

## HR / `target_hr` paths

All plan-side HR display strings flow through `get_runner_zone_string_for_run_type`
(`service.py`), which reads `runner_zone_profiles` and formats via the registry.

| Call site | Behavior |
|-----------|----------|
| `plan_storage_service._calculate_hr_zone` | SSOT lookup at row creation |
| `plan_routes` GET `/plan/current*` | Legacy fallback only when `target_hr` is null |
| `weekly_plan.build_weekly_plan_payload` | Same legacy fallback for missing rows |
| `weekly_rebuild_service` | Delegates to `PlanStorageService._calculate_hr_zone` |
| `recalculate_hr_zones_service` | Bulk refresh via storage helper |
| `heart_rate_orchestration_service` | Same facade when session + user_id present |

HR zone **percentages** remain in `hr_zone_constants.py` + `hr_builder.py` only;
they are not duplicated in run-type modules.

Optional later cleanup: `shared_v2/workout_utils.get_workout_pace_label_key` still
uses inline label heuristics — migrate to registry/taxonomy when touching Pass3/4.

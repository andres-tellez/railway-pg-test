# Runner profile — plan SSOT

## Plan definitions authority

Run-type zone mapping, workout taxonomy, and placement roles are owned by this
package:

| Module | Owns |
|--------|------|
| `plan_run_type_registry.py` | Canonical keys, zone mapping, display names, scoring tolerances |
| `plan_workout_taxonomy.py` | `WORKOUT_DEFINITIONS`, quality flags, detail archetypes |
| `plan_placement.py` | Placement roles (easy/steady/endurance/long), mileage shares |
| `service.py` | Facades for plan generation, storage, and HR/pace targets |

Plan pipeline code should import from `src.smartcoach_mobile_coach.runner_profile`
(or the specific submodule above). Deprecated shims have been removed.

## HTTP API

`GET /api/runner-profile/zones` exposes:

- `run_type_registry` — canonical run types + zone/Insights mapping (Steady → Z3/tempo)
- `plan_workout_taxonomy` — read-only taxonomy slice
- `pace_authorities` — explicit split between plan (activity median) and Insights (marathon goal)

## Pace authorities

| Consumer | Authority | Source |
|----------|-----------|--------|
| Plan Pass4 segments | Activity-calibrated | `get_runner_pace_zones_for_plan_generation` |
| Plan row `pace_ranges` | Persisted profile bands | `runner_pace_ranges_payload` |
| Insights Easy Avg Pace | Marathon goal | `training_pace_recommendations.pace_progress` |
| Insights Tempo Avg Pace | Marathon goal Z3 | `training_pace_recommendations.tempo_pace_progress` |

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

## Legacy follow-up

Insights SQL still references `v_easy_runs` (derived from legacy easy-run
classification). Migrating Insights KPI scope to registry-based `insights_system`
is tracked separately and does not block plan SSOT.

Optional later cleanup: `shared_v2/workout_utils.get_workout_pace_label_key` still
uses inline label heuristics — migrate to registry/taxonomy when touching Pass3/4.

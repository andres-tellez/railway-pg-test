# Phase 1 — Foundation layer (implementation checklist)

**Aligned with:** [`SMARTCOACH_SYSTEM_SPEC_V1.md`](./SMARTCOACH_SYSTEM_SPEC_V1.md) (system truth: canonical types, plan vs execution, tolerance, scoring, completion).

**Next phase checklist:** [Phase 2 — Plan tab](./PHASE_2_IMPLEMENTATION_CHECKLIST.md).

**Validated in repo:** `railway-pg-test` on **2026-04-20** (code review + targeted pytest).

**Verdict:** **Phase 1 (1A–1D) is implemented** for the backend execution pipeline. Items below marked **Pass** unless noted **Partial** or **Note**.

---

## 1A — Canonical run type registry

| ID | Requirement | Status | Evidence |
|----|----------------|--------|------------|
| 1A.1 | Five canonical run types (easy, recovery, steady, tempo, long) | **Pass** | `src/utils/run_type_constants.py` — `CANONICAL_RUN_TYPES`, `RUN_TYPE_*` constants |
| 1A.2 | Per-type HR target zone ids + acceptable zone span | **Pass** | `RunTypeDefinition.target_zone_ids`, `acceptable_zone_min` / `acceptable_zone_max` |
| 1A.3 | Per-type tolerance profile for score bucketing | **Pass** | `ToleranceProfile` on each `RUN_TYPE_DEFINITIONS` entry |
| 1A.4 | Legacy / plan keys map into canonical keys | **Pass** | `LEGACY_TO_CANONICAL_RUN_TYPE`, `normalize_run_type_key()` |
| 1A.5 | User-facing “effort cue” / long prose per type (if required for Phase 1) | **Partial** | Constants expose `display_name` only; **no** separate `effort_description` / intent strings in this file — OK if Phase 2 UI owns copy, otherwise extend here |

---

## 1B — Plan ↔ activity matching

| ID | Requirement | Status | Evidence |
|----|----------------|--------|------------|
| 1B.1 | Nullable FK `activities.matched_plan_workout_id` → `plan_workouts.id` | **Pass** | `src/db/models/activities.py` |
| 1B.2 | Match active plan workout to activity **local calendar date** | **Pass** | `match_plan_workout_for_activity()` — Postgres SQL uses `ACTIVITY_LOCAL_DATE_SQL_FRAGMENT` + active `plans`; SQLite path uses `_derive_local_date()` + `plan_workouts.date` |
| 1B.3 | Analysis persists `matched_plan_workout_id` (or clears when no match) | **Pass** | `analyze_activity_execution()` sets `activity.matched_plan_workout_id = match.workout_id if match else None` |
| 1B.4 | **Note (SQLite dev path)** | **Note** | `_match_plan_workout_sqlite` picks `plans.is_active` **without** `user_id` filter — fine for single-user SQLite tests; Postgres path joins `a.user_id` |

---

## 1C — Execution classification + per-run score

| ID | Requirement | Status | Evidence |
|----|----------------|--------|------------|
| 1C.1 | Trigger analysis after ingestion (recent window) | **Pass** | `src/services/ingestion_orchestrator_service.py` calls `analyze_recent_activity_window` |
| 1C.2 | HR zone fractions available for compliance | **Pass** | `hr_zone_1` … `hr_zone_5` on `Activity`; `_zone_distribution()` |
| 1C.3 | Persist `executed_type`, `zone_compliance_pct`, `pct_above_zone`, `pct_below_zone` | **Pass** | `analyze_activity_execution()` + `activities` columns |
| 1C.4 | Persist `planned_type`, `run_score` | **Pass** | Same |
| 1C.5 | Persist `scoring_detail` JSON (drill-down / audit) | **Pass** | `scoring_detail` dict with `schema_version`, `selection`, `distribution_pct`, `per_type_metrics` |
| 1C.6 | Plan vs executed **alignment penalty** | **Pass** | `_apply_plan_alignment_penalty()` — tested in `test_plan_mismatch_applies_score_penalty` |
| 1C.7 | Non-Run activities skipped | **Pass** | `if activity.type != "Run": return None` |
| 1C.8 | Automated tests | **Pass** | `tests/test_run_execution_analysis_service.py` (match + score + mismatch + `normalize_run_type_key`) |

---

## 1D — Completion tracking (separate from performance score)

| ID | Requirement | Status | Evidence |
|----|----------------|--------|------------|
| 1D.1 | Persist `planned_miles`, `actual_miles`, `completion_pct` | **Pass** | `activities` model + `analyze_activity_execution()` (`actual_miles` from `conv_distance`, `completion_pct` from planned/actual) |
| 1D.2 | `completion_pct` null when not computable | **Pass** | Only set when `planned_miles > 0` and `actual_miles` is not None |
| 1D.3 | Score driven by zone tolerance + mismatch logic, not completion alone | **Pass** | `_score_bucket` uses compliance + above-zone; completion is separate fields |

---

## Cross-cutting

| ID | Requirement | Status | Evidence |
|----|----------------|--------|------------|
| X.1 | `GET /api/plan/current-week` exposes execution payload | **Pass** | `src/routes/plan_routes.py` + `tests/test_plan_current_week_route.py` |
| X.2 | Coach run insight includes execution fields when present | **Pass** | `src/smartcoach_mobile_coach/run_insight.py` — `facts["execution_summary"]` |
| X.3 | DB migrations in deployed environments | **Not verified here** | Confirm Alembic revision applied on each environment (ops checklist) |

---

## Automated test run (this validation)

```bash
python -m pytest tests/test_run_execution_analysis_service.py tests/test_plan_current_week_route.py -q
```

**Result:** **6 passed** (2026-04-20). Repository-wide `fail-under=80` coverage may still fail when running only these files; that does not indicate Phase 1 test failure.

---

## Follow-ups (optional, not blocking “Phase 1 complete”)

1. Add **effort / intent strings** to `run_type_constants` (or a paired module) if mobile and coach must share exact copy from backend.
2. Harden **SQLite** plan match query with `user_id` if multi-user local DB is ever used.
3. Extend tests for **rest day** (no `plan_workout`) and **no HR zones** (analysis no-op) if you want explicit regression locks.

---

*This checklist is the implementation companion to the product spec. Update the table when behavior changes.*

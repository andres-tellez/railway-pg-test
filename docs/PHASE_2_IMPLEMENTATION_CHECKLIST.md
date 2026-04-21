# Phase 2 — Plan tab UX + execution surface (implementation checklist)

**Aligned with:** [`SMARTCOACH_SYSTEM_SPEC_V1.md`](./SMARTCOACH_SYSTEM_SPEC_V1.md) §15 (current week visible, future weeks not surfaced in this API), plus the **Plan tab / current-week** product intent.

**Scope:** **Backend** (`railway-pg-test`) + **Expo app** (`smartcoach_mobile` → `smartcoach_app/`). Depends on **[Phase 1](./PHASE_1_IMPLEMENTATION_CHECKLIST.md)**.

**Reviewed:** 2026-04-20.

**Verdict:** **Substantially complete** for a v1 weekly plan + execution readout. Items marked **Partial** match gaps vs an earlier line-by-line spec (standalone card component, icon map file, exact mega-JSON example).

---

## 2A — Plan API (current calendar week)

| ID | Requirement | Status | Evidence |
|----|----------------|--------|------------|
| 2A.1 | Authenticated **GET** for current plan week | **Pass** | `src/routes/plan_routes.py` — `@plan_bp.route("/current-week", methods=["GET"])` + `@requires_auth` |
| 2A.2 | Resolves **active** plan for user | **Pass** | Query `Plan` with `is_active`, fallback to latest plan |
| 2A.3 | **Mon–Sun** window from **today** in user TZ | **Pass** | `get_today_date_in_timezone(tz)` + `_monday_sunday_bounds(today)`; `tz` from query or `X-User-Timezone` |
| 2A.4 | Returns only `plan_workouts` in `[week_start, week_end]` | **Pass** | `PlanWorkout.date >= week_start` and `<= week_end` |
| 2A.5 | Joins **execution** when activity matches plan workout | **Pass** | `Activity.matched_plan_workout_id.in_(pw_ids)`; first activity per workout by `start_date` |
| 2A.6 | Response includes `run_type` metadata (display, zones) where implemented | **Pass** | Route builds `run_type` / `run_type_key` and execution fields (see `plan_routes.py` serialization) |
| 2A.7 | **Exact** frozen JSON schema from an early design doc | **Partial** | Shape is stable and typed in mobile `CurrentWeekPayload` / `CurrentWeekDayPayload`; field names may differ from every draft key |

**Tests:** `tests/test_plan_current_week_route.py`

---

## 2B — Week reveal / “no future weeks in this view”

| ID | Requirement | Status | Evidence |
|----|----------------|--------|------------|
| 2B.1 | This endpoint does **not** return full plan history | **Pass** | Only one week’s workouts queried |
| 2B.2 | “Current week” follows **viewer timezone** | **Pass** | `tz` / header + `get_today_date_in_timezone` |

> Full plan still exists in DB; other routes (e.g. `GET /api/plan/current`) may return more — weekly UI should keep using **`/current-week`** only.

---

## 2C — Run day UI (mobile)

| ID | Requirement | Status | Evidence |
|----|----------------|--------|------------|
| 2C.1 | Plan tab shows **weekly** list (Mon–Sun style) | **Pass** | `smartcoach_app/features/plan/components/weekly-plan-panel.tsx` — `enumerateMonSunWeek`, day rows |
| 2C.2 | **Day label** (abbrev) + workout summary for non-execution rows | **Pass** | `CompactPlanWorkoutLines` — title + miles + HR meta |
| 2C.3 | **Execution** (plan vs actual table) available to runner | **Pass** | Same file — modal detail; `PlanLineWithExecutionSummary` + `ExecutionMetricsTable` |
| 2C.4 | **Score** surfaced on list (past/today with execution) | **Pass** | KPI dot color from `execution.run_score` (`executionDotColor`) |
| 2C.5 | Dedicated **`run-day-card.tsx`** component | **Partial** | Layout lives inside `weekly-plan-panel.tsx` — functionally fine; extract later if reuse demands |
| 2C.6 | Explicit **pending / completed / rest** card state machine in code | **Partial** | Behavior exists; not necessarily named enums/components per early spec |

---

## 2D — Run type icons (mobile)

| ID | Requirement | Status | Evidence |
|----|----------------|--------|------------|
| 2D.1 | Per-canonical-type icon mapping module | **Partial** | **Not** present as `constants/run-type-icons.ts`; weekly header uses phase **leaf** icon only |
| 2D.2 | Icons reused in chat markdown | **Not done** | Out of scope until renderer + mapping exists |

---

## 2E — Training plan screen + client fetch

| ID | Requirement | Status | Evidence |
|----|----------------|--------|------------|
| 2E.1 | Plan tab screen not a placeholder | **Pass** | `smartcoach_app/features/plan/screens/training-plan-screen.tsx` — `WeeklyPlanPanel` / `PhasePlanPanel`, segment control |
| 2E.2 | Client calls **`/api/plan/current-week`** | **Pass** | `smartcoach_app/lib/api/plan.ts` — `fetchCurrentWeekPlan` |
| 2E.3 | Types for payload | **Pass** | `CurrentWeekPayload`, `CurrentWeekDayPayload`, `CurrentWeekExecutionPayload` |
| 2E.4 | **Week header** (range + phase hint) | **Pass** | `weekly-plan-panel.tsx` — `formatWeekRangeShort`, `planPhaseNameForWeek`, phase row with icon |
| 2E.5 | **Phase progress bar** for weekly strip | **Partial** | Phase name shown; dedicated progress bar may live under **Phase** tab / `phase-plan-panel` — confirm product expectation |

---

## Cross-cutting

| ID | Requirement | Status | Evidence |
|----|----------------|--------|------------|
| X.1 | Auth + retry on plan fetch (mobile) | **Pass** | `withUnauthorizedRetry`, `useAuth` in `WeeklyPlanPanel` |
| X.2 | Coach tool / insight can read same execution facts | **Pass** | Phase 1 checklist — `run_insight.py` `execution_summary` |

---

## Suggested next steps (to close “Phase 2” to spec 100%)

1. Extract **`RunDayCard`** (or rename) from `weekly-plan-panel.tsx` for readability and reuse.
2. Add **`run-type-icons.ts`** (or SF Symbol map) + wire into weekly row and future chat.
3. Add **pytest + detox/e2e** smoke: open Plan → assert 7 rows → open modal on a scored day.

---

*Update this table when shipping new Plan tab features.*

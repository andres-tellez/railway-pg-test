# Phase 3 — Plan-aware coach (V1.6 rollout checklist)

**Aligned with:** [`SMARTCOACH_SYSTEM_SPEC_V1.md`](./SMARTCOACH_SYSTEM_SPEC_V1.md) V1.6 — §5 (deviation direction), §6 (plan vs execution, `plan_status`, namespace isolation, future-week contract), §7 (adherence + run-type vs phase split), §8 (`phase_kpi_priority`), §12 (`baseline_status`), §16 (adaptation caps), **§19 Coach Behavior Contract**, and Appendix B (six new deterministic fields). Implementation counterpart documented in [`AGENTIC_COACH.md`](https://github.com/andres-tellez/smartcoach_mobile/blob/main/smartcoach_app/docs/AGENTIC_COACH.md) **Topic 9**.

**Scope:** **Backend** (`railway-pg-test`) + **Expo app** (`smartcoach_mobile` → `smartcoach_app/`). Depends on **[Phase 1](./PHASE_1_IMPLEMENTATION_CHECKLIST.md)** and **[Phase 2](./PHASE_2_IMPLEMENTATION_CHECKLIST.md)**.

**Status:** **Design approved (V1.6).** Implementation phased A → F.

**Verdict:** Not started — this is the V1.6 implementation roadmap.

---

## Rollout Overview

| Phase | Title | Goal | Blocking for |
|---|---|---|---|
| **Pre-A** | Cleanup & centralization | Eliminate duplicate code paths **before** adding V1.6 fields; establish single-source-of-truth rule | A |
| **A** | Schema discipline | Land six deterministic fields + namespace isolation in the backend | B, C |
| **B** | Plan read tools + context + glossary | `get_weekly_plan`, `get_plan_overview`, `get_phase_analysis`, `get_user_context`; metric glossary in system prompt; extend `get_run_summary` | C |
| **C** | In-chat plan rendering | §19 Coach Behavior Contract enforced in prompt + validator; session-summary injection at turn start | D |
| **D** | Phase goals | `user_phase_goals` table + `save_phase_goal` tool + read-path integration | E |
| **E** | Plan adjustments | LLM-proposed adjustments, system-validated inside §16 caps | F |
| **F** | Plan-aware long-term memory | Topic 6 Layer B/C extensions for plan context | — |

---

## Pre-Phase A — Cleanup & centralization (mandatory before Phase A)

**Rationale:** V1.6 adds 6 deterministic fields that must each have a single source of truth (see Cross-cutting X.5). Existing duplicate code paths would cause drift the moment the new fields land. This phase removes the duplication first.

### Pre-Phase A — Cross-cutting cleanup (backend + mobile)

| ID | Requirement | Status | Scope |
|----|----|----|----|
| 0.1 | **Document `null` vs absent convention** in `AGENTIC_COACH.md` Topic 4 — field **present with `null`** for "checked, no value"; field **absent** only when a whole optional section is suppressed | **Done** (2026-04-21) | Docs |
| 0.2 | **Centralize "is this week past / present / future?"** into one backend utility; all backend + tool code reads from it | **Done** (2026-04-21) — extended the canonical `src/utils/date_helpers.py` with `WeekTemporality` enum, `classify_week_temporality(target_week_start, user_tz, today=None)`, `is_future_week(...)` thin predicate, and `get_week_bounds_for_date(...)` helper. Removed duplicate `_monday_sunday_bounds` from `plan_routes.py`; call sites use the canonical helpers. 23 tests (21 pass + 2 skipped on environments without `tzdata`). | Backend (`railway-pg-test`) |
| 0.3 | **Centralize zone compliance / `pct_above` / `pct_below` computation** into one function that all scoring + execution-summary paths call; remove any duplicate implementations | **Done** (2026-04-21) — created `src/services/scoring/zone_compliance.py` with public `zone_distribution_from_activity(...)`, `zone_metrics_for_type(distribution, run_type)` returning a typed `ZoneMetrics` NamedTuple, and `_ActivityZoneReader` Protocol for tests. Removed duplicate private helpers `_zone_distribution` and `_zone_metrics_for_type` from `run_execution_analysis_service.py`; it now imports the canonical producers. 19 new unit tests pass; existing 4 `test_run_execution_analysis_service.py` tests still pass — behavior-preserving. Registered as canonical producer in X.5 below. | Backend |
| 0.4 | **Grep + replace bare run-type string literals** (`"easy"`, `"tempo"`, `"steady"`, `"recovery"`, `"long"`) with constants from `src/utils/run_type_constants.py`; required across backend Python and mobile TS | **Partial** — 2 comparison sites fixed in `plan_storage_service.py` and `pace/adjustments.py` (2026-04-21). **Still open:** v2 workout-taxonomy raw keys in `workout_placement_engine.py` (`"long_run"`) and pre-normalization raw types in `week_log_service.py` (`"steady", "threshold", "tempo", "interval"`); dict-key usages (~25 files). Remaining work lives in a separate pass. | Backend + mobile |
| 0.5 | **Pin `classify_turn` / `derive_interaction_mode` / `infer_intent` return values** as typed enums or `Literal[...]` unions in `dialogue_manager.py`; consumers (prompt builder, validator) import from one place | **Done** (2026-04-21) — added `TurnType` / `InteractionMode` / `Intent` `Literal` unions, named constants, frozensets, and `is_action_oriented_exempt(...)` helper (§19.6 single source of truth). Consumers updated: `orchestrator.py`, `run_recap_fastpath.py`. Zero remaining bare-string literals for these enums outside `dialogue_manager.py`. | Backend (`src/smartcoach_mobile_coach/`) |

### Pre-Phase A — Existing-path consolidation (items A–E from design review)

| ID | Requirement | Status | Scope |
|----|----|----|----|
| 0.A | **`run_insight.py` becomes single source** for per-run `planned.*` / `actual.*` namespaced blocks; `get_run_summary` and `GET /api/plan/current-week` both read from it; no parallel "plan vs actual" builder in `plan_routes.py` | **Done** (2026-04-21) — Added the canonical V1.6 `planned.*` / `actual.*` block builder `build_run_execution_block(act)` to `src/smartcoach_mobile_coach/run_insight.py`. It is now the ONLY place in the codebase that reads planned / actual fields off an `Activity` for payload construction (single-source-of-truth per §X.5). Two byte-exact legacy-shape adapters ship alongside it: (1) `execution_block_to_weekly_plan_shape(block, act)` reproduces the pre-0.A `_execution_payload` dict for mobile `CurrentWeekExecutionPayload`, (2) `execution_block_to_insight_summary_shape(block)` reproduces the pre-0.A `facts.execution_summary` dict literal for the LLM `get_run_summary` tool. Deleted `plan_routes._execution_payload` and `plan_routes._avg_pace_per_mile_display`; the `/api/plan/current-week` route now delegates via `execution_block_to_weekly_plan_shape(build_run_execution_block(act), act)`. `build_get_run_insight_payload` now calls `execution_block_to_insight_summary_shape` for `facts.execution_summary` and collapses its duplicate `facts` dict construction to a single spread. Parity is locked by 8 new unit tests in `tests/test_run_execution_block.py` covering: namespaced block contract, unplanned activity handling, byte-exact parity with both pre-0.A shapes, single-source-of-truth drift check between adapters, and duck-typed input acceptance. 0.E and Phase B will flip mobile / LLM tools to consume the namespaced block directly; the legacy adapters then become deprecation targets. | Backend (`src/smartcoach_mobile_coach/run_insight.py`, `src/routes/plan_routes.py`) |
| 0.B | **One `completion_pct` computation** feeds per-run score, weekly `adherence_runs_pct`, and coach payload; the 0.50 "completed" threshold lives as a named constant (e.g. `COMPLETION_THRESHOLD = 0.50` in `run_type_constants.py` or a new `adherence_constants.py`), not inlined | **Done** (2026-04-21) — Added `src/services/scoring/completion.py` as the single source of truth (colocated with `zone_compliance.py` under the `scoring/` primitives package). Exports: (1) `COMPLETION_THRESHOLD_RATIO = 0.50` — V1.6 §7 canonical ratio form; (2) `COMPLETION_THRESHOLD_PCT = 50.0` — derived (`100 × ratio`) for direct comparison against stored percent-scale values; (3) `compute_completion_pct(actual_miles, planned_miles) -> Optional[float]` — the ONLY `actual / planned × 100` formula in the codebase; returns `None` for undefined completion (missing / zero / negative planned, or missing actual); does NOT round (callers round per persistence vs display needs); (4) `is_run_completed(completion_pct_value) -> bool` — V1.6 §7 gate (`>= COMPLETION_THRESHOLD_PCT`), `None` → `False`. Refactored both prior inline producers: `src/services/run_execution_analysis_service.py` (per-run `activity.completion_pct`) and `src/services/gyr_metrics_service.py` (weekly GYR aggregate) now consume `compute_completion_pct`. 14 unit tests in `tests/services/scoring/test_completion.py` lock threshold values, producer semantics (overshoot unclipped, `None` contracts, no rounding), and the `is_run_completed` gate (including constant-linked regression guard). Future Phase A `adherence_runs_pct` producer will use `is_run_completed(act.completion_pct)` directly. | Backend (`src/services/scoring/completion.py`) |
| 0.C | **Resolve `get_weekly_training_insight` vs `get_weekly_plan`** — either deprecate `get_weekly_training_insight` (fold into `get_weekly_plan` when the question centers on the plan) or document the scope split explicitly; mark deprecations with `# DEPRECATED V1.6 (PHASE_3_IMPLEMENTATION_CHECKLIST 0.C): ...` | **Decision made & Done** (2026-04-21) — **DEPRECATE.** Replacement is `get_weekly_plan` (V1.7, AGENTIC_COACH.md Topic 9), which will enforce V1.6 §6 namespace isolation and the future-week payload contract. Policy: **NO NEW CONSUMERS.** Existing consumers preserved so live coach flows do not break. Changes landed: (1) module-level deprecation block + `_GWTI_DEPRECATION_MESSAGE` constant + `DeprecationWarning` emitted on every `tool_get_weekly_training_insight()` call in `src/smartcoach_mobile_coach/agent_tools.py`; (2) `# DEPRECATED V1.6 (... 0.C): ...` comment on the `_TOOL_HANDLERS` entry and the `scripts/setup_coach_tools.py` OpenAI schema block; (3) LLM-facing description now opens with `[DEPRECATED — will be replaced by get_weekly_plan …]` to steer the model off the tool; (4) lock-in test `tests/test_get_weekly_training_insight_deprecation.py` (12 cases) that asserts the warning fires, names the replacement, cites 0.C, is filter-able, and that the return contract is preserved. See "0.C no-new-consumers enforcement" below. | Backend (`src/smartcoach_mobile_coach/agent_tools.py`) |
| 0.D | **Kill GET-time HR zone inference** in `plan_routes.py` (lines 59–67 infer zones from workout name strings); zones must be stored at plan-generation time in `plan_storage_service.py` and read unchanged on GET | **Done** (2026-04-21) — Deleted `_infer_run_type_key_for_hr` (substring text-matching over `workout_type`) and the two GET-time "zone revalidation" branches (`stored_zone != expected_zone → target_hr = expected_hr`) in `/api/plan/current` and `/api/plan/current-week`. Replaced with `_resolve_run_type_key_for_workout(w)` which normalizes through `LEGACY_TO_CANONICAL_RUN_TYPE` (single source of truth — `src/utils/run_type_constants.py`). Stored `target_hr` is now authoritative; the GET path only falls back to `PlanStorageService._calculate_hr_zone(canonical_key, profile)` when the DB value is missing (legacy rows predating `target_hr` persistence). No mutation. Dropped the now-unused `import re`. Test coverage added in `tests/test_plan_current_week_route.py`: (1) legacy `run_type_key="endurance"` normalizes to canonical `"long"` and stored `target_hr` is returned verbatim even when a recomputation would disagree; (2) missing `target_hr` gets a canonical Z-label via the narrow fallback. Backfill for legacy plans remains the dedicated responsibility of `recalculate_hr_zones_service.recalculate_hr_zones_for_plan` (invoked on profile/max-HR update), not the GET path. | Backend (`src/routes/plan_routes.py`) |
| 0.E | **Mobile `weekly-plan-panel.tsx` refactor** — consume `planned.*` / `actual.*` top-level keys directly from the new payload shape; no adapter that "unflattens" the current intermediate form; `weekly-plan-from-workouts.ts:56-60` string-match run-type inference removed (replaced by server-side canonical types only) | **Done** (2026-04-21) — Backend `execution_block_to_weekly_plan_shape` now dual-emits the canonical V1.6 §6 `planned` / `actual` sub-objects alongside the legacy flat fields, all sourced from the same `build_run_execution_block` single source so they cannot drift. `actual` on the wire is display-augmented (rounded-int `average_heartrate` + formatted `M:SS/mi` `avg_pace_per_mile`) so mobile renders directly. Mobile (`smartcoach_mobile`): `CurrentWeekExecutionPayload` in `smartcoach_app/lib/api/plan.ts` gains canonical `planned: CurrentWeekPlannedBlock` / `actual: CurrentWeekActualBlock` namespaces; every legacy flat field is JSDoc-`@deprecated` with a pointer to its canonical replacement. `smartcoach_app/features/plan/components/weekly-plan-panel.tsx` (the only runtime consumer of individual execution fields) now reads exclusively from `execution.planned?.miles` / `execution.actual?.miles` / `execution.actual?.avg_pace_per_mile` / `execution.actual?.average_heartrate`. Backend parity test `test_weekly_plan_shape_dual_emit_legacy_parity_and_namespaced` locks (a) byte-exact pre-0.A flat-field shape, (b) correct namespaced shape, (c) a drift guard asserting every legacy flat field equals its namespaced counterpart. `test_current_week_returns_days_and_execution` gains end-to-end assertions that `/api/plan/current-week` surfaces `day.execution.planned.*` / `day.execution.actual.*` with values matching the flat counterparts. Mobile `tsc --noEmit` passes. Flat fields remain on the wire during V1.6 for backward compat; removal is a follow-up once Phase B lands. Note on scope: the `weekly-plan-from-workouts.ts:56-60` string-match run-type inference removal is tracked separately — it is a secondary 0.4 concern (run-type literal) and does not depend on the payload shape addressed here. | Mobile (`smartcoach_app/`) + Backend (`railway-pg-test`) |

### Pre-Phase A gating rule

> **No Phase A schema work (field additions) may merge until 0.1–0.5 and 0.A–0.E are complete or explicitly deferred with a tracked ticket.** The gate prevents "land the field, clean up later" patterns that become permanent drift.

---

## Phase A — Schema discipline

| ID | Requirement | Status | Spec ref |
|----|----|----|----|
| 3A.1 | `deviation_direction` computed per activity (`too_hard` / `too_easy` / `on_target` / `null`) | **Done 2026-04-21** | §5 Deviation Direction |
| 3A.2 | Per-run-type thresholds enforced (Recovery 5/40, Easy 15/30, Tempo 20/25 main-block, Long 20/30) | **Done 2026-04-21** | §5 table |
| 3A.3 | Tie-breaker (both thresholds → `too_hard`) | **Done 2026-04-21** | §5 rule 1 |
| 3A.4 | Omission rules (`null` when HR missing, `duration_seconds < 600`, or `planned_type = Steady`) | **Done 2026-04-21** | §5 rule 2 |
| 3A.5 | Tempo evaluation scope = main block (warm-up/cool-down excluded) | **Partial — deferred 2026-04-21** | §5 rule 3 |

**3A.1 – 3A.4 rationale (Done 2026-04-21):**
- **Single source of truth** — new module `src/services/scoring/deviation.py` exposes:
  - `DeviationDirection(str, Enum)` — wire values `too_hard` / `too_easy` / `on_target`.
  - `DEVIATION_THRESHOLDS` — frozen V1 threshold table keyed by canonical run_type_key (recovery/easy/tempo/long).
  - `MIN_DEVIATION_DURATION_SECONDS = 600` — the §5-rule-2 floor.
  - `classify_deviation(...)` — pure threshold-classification function (no I/O), unit-testable.
  - `compute_deviation_direction_for_activity(act)` — activity-level adapter that handles all omission cases, planned-type normalization, HR-zone distribution derivation, and target-band-relative pct_above/pct_below computation before delegating to the pure classifier.
- **Derivation policy** — on-read, not persisted. Rationale: (a) avoid invalidation when thresholds evolve (V1.7 Steady/Tempo work); (b) deterministic output from existing persisted inputs (`hr_zone_1..5`, `moving_time`, `planned_type`); (c) §X.5 single-source-of-truth rule — only this module produces the value.
- **Target-band vs acceptable-band (deliberate)** — spec §5 wording "time-above-target" / "time-below-target" does not map to `zone_metrics_for_type`'s acceptable-band semantics (which make `too_easy` unreachable for Long). The deviation module therefore computes pct_above/pct_below relative to `RunTypeDefinition.target_zone_ids` directly. Module docstring "Target-band vs acceptable-band" captures the rationale; Easy/Recovery `too_easy` is unreachable by HR construction (no zone exists below Z1) and that is an intentional characteristic of the V1 HR model.
- **Planned-type vs executed-type zones (CRITICAL)** — `activity.pct_above_zone` / `activity.pct_below_zone` are persisted relative to the *executed* type; deviation must measure against the *planned* type. Adapter re-derives from `hr_zone_1..5` + `planned_type` on every call to avoid the bug. Covered by `test_easy_plan_tempo_execution_is_too_hard`.
- **Tie-breaker** — `classify_deviation` checks `above_exceeded` first so ties resolve to `too_hard` per spec §5 rule 1. Behavior is ordering-sensitive; comment in code calls this out.
- **Wiring** — ``build_run_execution_block`` places `deviation_direction` inside `actual.*` per spec §6 namespace isolation (NOT at block top level). `execution_block_to_insight_summary_shape` surfaces it as a flat key for the LLM `get_run_summary` tool. `/api/plan/current-week` route inherits it automatically via the `**actual` spread into `actual_namespaced` — no per-day-level duplication (the direction is a property of the run, not the plan day).
- **Mobile types** — `smartcoach_app/lib/api/plan.ts` adds `DeviationDirection` union and `deviation_direction?: DeviationDirection | null` on `CurrentWeekActualBlock`, with JSDoc warning mobile MUST NOT re-derive.
- **Testing** — 46 unit cases in `tests/services/scoring/test_deviation.py` locking the threshold table, tie-breaker, every omission branch, target-band-relative derivation, and legacy-key normalization; 5 new cases in `test_run_execution_block.py` for the canonical block + insight-summary adapter; 1 new assertion in `test_plan_current_week_route.py` for end-to-end route surfacing.

**3A.5 status (Partial — deferred 2026-04-21):** Spec §5 rule 3 requires Tempo to be evaluated on the main block only (warm-up/cool-down excluded). The current codebase stores a single full-run zone distribution on `activities.hr_zone_1..5` and has no persisted main-block distribution or reliable on-the-fly reconstruction path. Spec §5 explicitly forbids full-run approximation ("Approximation or inheritance is not permitted — deterministic correctness is preferred to temporary coverage"). The activity-level adapter therefore emits `None` for all Tempo runs in V1.6 while still keeping `tempo` in `DEVIATION_THRESHOLDS` so a future main-block-aware caller can call `classify_deviation` directly without touching this module. Tracked for a follow-up: add `hr_zone_1..5_main_block` columns (or equivalent stream-based reconstruction) and extend `compute_deviation_direction_for_activity` to consume them when `planned_type == 'tempo'`.
| 3A.6 | `plan_status` enum computed per plan-day / activity pair | **Done** (2026-04-21) — New module `src/services/plan/plan_status.py` (single source of truth per §X.5) with `PlanStatus(str, Enum)` (5 wire values locked: `planned_only`, `in_progress`, `executed`, `missed`, `unplanned`) and two specialized producers: `plan_status_for_activity(matched_plan_workout_id)` (binary `EXECUTED`/`UNPLANNED` — per-activity pairing, called by `build_run_execution_block`) and `plan_status_for_day(*, has_planned_workout, has_matching_activity, day_date, today)` (full 5-value derivation, returns `None` for empty rest/gap days which the spec does not enumerate). **Derived on read, not persisted** — trivially computable from `activity.matched_plan_workout_id` plus `(day_date, today)`, so a persisted column would introduce invalidation complexity (today moves daily; planned_only/in_progress/missed flip without writes). Wired: (a) canonical execution block carries `plan_status` at top level (neither `planned.*` nor `actual.*`, because it describes the pairing); (b) `execution_block_to_insight_summary_shape` surfaces it to `get_run_summary` (LLM tool needs all deterministic fields); (c) `/api/plan/current-week` route carries `day.plan_status` (day-level authoritative — deliberately NOT duplicated in `day.execution.plan_status` via `execution_block_to_weekly_plan_shape`, keeping the day as single source for the primary mobile route). Known gap: `/api/plan/current-week` iterates planned workouts only, so cannot emit `unplanned` day-state for activities on gap days — documented in `plan_status.py` docstring; Phase B `get_weekly_plan` will surface those. Tests: 14 cases in `tests/services/plan/test_plan_status.py` covering enum wire values, exactly-5-values invariant, per-activity binary, per-day full matrix (all 5 + `None`), and a Phase B readiness check for `UNPLANNED` via the day producer. Existing `test_run_execution_block.py` (+2 new cases) and `test_plan_current_week_route.py` (+1 new test covering missed/in_progress/planned_only) regression-check the wire surfacing. | §6 enum table |
| 3A.7 | `violated_rest_day` boolean on activities | **Done** (2026-04-21) — Colocated producer `derive_violated_rest_day(*, plan_status_value, day_weekday, plan_training_days)` in `src/services/plan/plan_status.py` (same module as `plan_status` per §X.5). Semantics lock the V1.6 §6 truth table: `True` iff `plan_status == UNPLANNED` AND the weekday is not in `plan.training_days`; `False` in every other branch including when `training_days` is `None`/empty (spec "false otherwise" — safe default so coach §19.7 does not escalate on ambiguous plan metadata). Rest days are implicit in this codebase: `PlanWorkout` rows are created only for training days, and `plans.training_days` is the nullable source of truth for the user's scheduled weekdays; producer accepts both full ("Monday") and abbreviated ("Mon") forms via `DAY_TO_WEEKDAY` and silently discards unknown tokens. **Derived on read, not persisted** — trivially recomputable from `(plan_status, activity.start_date.weekday(), plan.training_days)`; no new DB column. Wired: (a) `build_run_execution_block(act, *, plan_training_days=None)` gained a keyword-only parameter (backward-compatible); carries `violated_rest_day` at top level alongside `plan_status` and short-circuits on non-UNPLANNED cases to avoid reading `start_date`; (b) `execution_block_to_insight_summary_shape` surfaces it for the LLM `get_run_summary` tool (coach §19.7 stronger-tone rule depends on this flag); (c) `/api/plan/current-week` route: Plan query extended to include `training_days`, passed into the execution-block builder for matched activities, and every emitted day entry carries `day.violated_rest_day = False` (every day in this route is planned-workout-driven → by definition not a rest day). Deliberately NOT duplicated in `day.execution.violated_rest_day` — day level is authoritative, matching the plan_status non-duplication pattern. Mobile `CurrentWeekDayPayload.violated_rest_day?: boolean \| null` added to `smartcoach_app/lib/api/plan.ts`. TZ caveat (tracked for V1.7): weekday derived from `activity.start_date` (UTC); edge-case runs that straddle midnight vs local tz may drift by one weekday until activities carry a stored local date. Tests: 8 new cases in `tests/services/plan/test_plan_status.py` (executed/planned_only/in_progress/missed always False; unplanned × {None, empty, in training_days, not in training_days, full/abbreviated name mix, unknown tokens, exhaustive 7-weekday sweep}); 4 new cases in `tests/test_run_execution_block.py` for the execution block (executed=False, unplanned+no-training-days=False, unplanned+rest-day=True, unplanned+training-day=False) plus updated parity assertion for `insight_summary_shape`; `/api/plan/current-week` integration asserts `day.violated_rest_day=False` and no-duplication on `day.execution`. Total `tests/services/plan/test_plan_status.py` + execution block + current-week regression suite: 64 passing. | §6 derived flags |
| 3A.8 | `adherence_runs_pct` computed weekly (primary) with completion rule `completion_miles_pct ≥ 0.50` | **Done** (2026-04-21) — see 3A.8/9/10 rationale below | §7 metrics |
| 3A.9 | `completion_miles_pct` exposed as supporting field per run | **Done** (2026-04-21) — per-run surface already landed in 0.B (`src/services/scoring/completion.py::compute_completion_pct`, stored on `activities.completion_pct`, surfaced in `actual.completion_pct` and on the legacy flat field); weekly aggregate added by this item | §7 metrics |
| 3A.10 | Unplanned runs excluded from `adherence_runs_pct` numerator and denominator | **Done** (2026-04-21) — `compute_weekly_adherence` skips `PlanStatus.UNPLANNED` before touching the counters; locked by `TestComputeWeeklyAdherenceDenominator` (`test_unplanned_is_excluded_from_both_sides`, `test_only_unplanned_entries_returns_none_ratio`) and `test_unplanned_miles_do_not_inflate_aggregate` for the weekly miles aggregate | §7 unplanned rule |

**3A.8/9/10 rationale (Done 2026-04-21):**
- **Single source of truth** — new module `src/services/scoring/adherence.py` (colocated with the 0.B `completion.py` primitives under the `scoring/` package so no producer has to reach across service boundaries). Exposes:
  - `AdherenceBand(str, Enum)` — §7 wire values `low`/`medium`/`high`; invariant-locked to exactly three values.
  - Named constants `ADHERENCE_LOW_MAX_EXCLUSIVE_PCT = 70.0`, `ADHERENCE_HIGH_MIN_EXCLUSIVE_PCT = 90.0` — no inlined 70/90 literals at call sites.
  - `classify_adherence_band(pct)` — pure classifier. `None`-in / `None`-out (empty-week round-trip); closed 70–90 interval (exactly 70.0 and 90.0 are Medium, not Low / not High).
  - `WeeklyAdherenceEntry` NamedTuple — `(plan_status, completion_pct, planned_miles, actual_miles)`. Route / tool boundary assembles one per planned-workout day.
  - `WeeklyAdherenceResult` NamedTuple — `(adherence_runs_pct, completed_runs, planned_runs, band, completion_miles_pct_weekly, planned_miles_total, actual_miles_matched_total)`. Wire-safe primitives only.
  - `compute_weekly_adherence(entries)` — canonical aggregator; consumes `is_run_completed(completion_pct)` from `completion.py` so the §7 50 % threshold is defined in exactly one place (§X.5).
- **Numerator semantics** — a planned entry counts toward `completed_runs` iff (a) `plan_status ∈ {EXECUTED, IN_PROGRESS}` (matched activity exists) AND (b) `is_run_completed(completion_pct)`. `IN_PROGRESS` is deliberately eligible so mid-week reads give a faithful "so-far" snapshot; on closed-week reads `IN_PROGRESS` has rolled over to `EXECUTED` and the semantics converge. `MISSED` / `PLANNED_ONLY` never count in numerator. Matched-but-<50 % is MISSED for adherence regardless of `plan_status` — spec §7 "2-mi attempt on a planned 10-mi Long Run does not count".
- **Denominator semantics** — `planned_runs = count(plan_status ∈ {PLANNED_ONLY, IN_PROGRESS, EXECUTED, MISSED})`. `UNPLANNED` excluded from both numerator AND denominator per §7 "Unplanned Runs and Adherence".
- **Weekly `completion_miles_pct` aggregate** — `sum(actual_miles_on_planned) / sum(planned_miles)`; `None` when `planned_miles_total <= 0`. Denominator is planned (not matched-planned), so a dropped long run correctly lowers weekly mileage completion. Defensive: 0-mile or negative `planned_miles` rows are skipped; overshoot (actual > planned) is NOT clipped — the ratio is signal for §19 coach tone.
- **Empty-week contract** — `planned_runs == 0` ⇒ `adherence_runs_pct = None`, `band = None`. The coach must not treat an off-week as a 0 % Low signal (§4 null-vs-absent: "None = checked, no value").
- **Derivation policy** — on-read, not persisted (matches `plan_status`, `baseline_status`, `deviation_direction`). Aggregation is trivially fast; persistence would require invalidation on every matched-activity write.
- **Wiring (V1.6 Phase A scope — producer + current-week route only):**
  - `/api/plan/current-week` accumulates one `WeeklyAdherenceEntry` per planned workout inside the existing day loop, then emits a single week-level `adherence` block outside `days`. Entries are sourced directly from the matched `Activity` row (not the execution-block adapter's reshaped shape) so the signal is immune to future display-side reshaping.
  - Mobile `CurrentWeekPayload.adherence?: CurrentWeekAdherenceBlock | null` + `AdherenceBand` union added to `smartcoach_app/lib/api/plan.ts`, with JSDoc flagging "do NOT re-derive on mobile" per V1.6 §19 LLM/client contract.
  - Phase B `get_weekly_plan`, `get_plan_overview`, and §16 weekly adaptation pass will consume this same producer (marked in §X.5 row).
- **Testing** — 41 unit cases in `tests/services/scoring/test_adherence.py` locking enum wire values, named-constant thresholds, completion-threshold sanity (COMPLETION_THRESHOLD_PCT == 50.0), band-boundary behavior (None/0/69.999/70/80/90/90.001/100/125/-10), empty-week and all-unplanned returns, numerator matrix (executed ≥ 50, executed = 50, executed < 50, executed with null completion, in_progress counts, missed never counts, planned_only never counts), denominator matrix (unplanned exclusion, all-four-statuses-inclusion), full-week parameterized ratio+band matrix (8 scenarios), below-50 mixed-week scenario, weekly miles aggregate (spec formula, missed reduces aggregate, unplanned excluded, null-planned-miles ⇒ None, zero/negative-planned defensive), and `WeeklyAdherenceResult` public field contract. 3 new `/api/plan/current-week` integration tests: single-run 100 % week (HIGH), two-run 1-of-2-completed week with missed long run (LOW, weekly miles 25 %), empty week (nulls, not zeros). Full regression sweep: `tests/services/scoring/ tests/services/plan/ tests/services/baseline/ tests/test_plan_current_week_route.py tests/test_run_execution_block.py` — 209 passed.
| 3A.11 | `baseline_status` enum (`insufficient` / `thin` / `strong`) per user, recomputed weekly | **Done 2026-04-21** | §12 baseline_status |

**3A.11 rationale (Done 2026-04-21):**
- **Single source of truth** — new package `src/services/baseline/` with `baseline_status.py` exposing:
  - `BaselineStatus(str, Enum)` — wire values `insufficient` / `thin` / `strong`.
  - `classify_baseline_status(*, runs_in_last_4_weeks, weeks_with_runs_in_last_4)` — pure cascade classifier (no I/O).
  - `count_runs_and_weeks_in_window(activity_dates, *, today, window_days=28)` — rolling 7-day bucket helper, separately unit-testable and reusable by §16 adaptation callers.
  - `compute_baseline_status_for_athlete(session, athlete_id, *, today=None)` — DAO-backed adapter that queries `activities` (Run-typed, last 28 days) and dispatches to the pure classifier.
- **Cascade ordering (spec §12)** — most-restrictive first: `insufficient` (weeks < 2 OR runs < 3) → `strong` (weeks ≥ 4 AND runs ≥ 6) → `thin` (everything else). Ordering is correctness-sensitive: a runner with 4 weeks but only 2 runs must classify as `insufficient`, not `thin`. Locked by `test_four_weeks_two_runs_is_insufficient`.
- **Window semantics** — rolling 7-day buckets relative to `today` (`bucket = (today - activity_date).days // 7`, 4 buckets). Chosen over ISO-week bucketing to avoid calendar-boundary and locale artefacts; same-day runs count (bucket 0); activities strictly older than 28 days or future-dated activities are excluded. Documented in the module docstring.
- **Derivation policy** — on-read, not persisted. Matches §12's "recomputed each week when the weekly adaptation pass runs" without the write-invalidation problems persisting the value would introduce; a previously `strong` baseline that erodes as weeks roll out of the window is automatically re-evaluated on next read.
- **Defensive clamping** — the pure classifier clamps negative and above-cap inputs (`max(0, runs)`, `min(4, weeks)`) rather than raising, so a caller bug in window math returns a safe default rather than crashing the coach.
- **Wiring posture for V1.6** — producer only. Phase A item 4 ships `BaselineStatus` + both classifier layers so 3B.10's `get_user_context()` tool can consume it directly without touching any classification logic. No mobile type addition yet — the payload surface is defined by the `get_user_context` tool in Phase B.
- **Testing** — 35 unit cases in `tests/services/baseline/test_baseline_status.py` cover: enum wire values + "exactly three values" invariant + window constants; every cascade branch including all three boundary-exact triples (2 weeks/3 runs, 4 weeks/6 runs, 4 weeks/5 runs); defensive clamping of negative and over-cap inputs; bucket helper for empty iterables, same-day, 7-day boundary, 27/28-day window edges, future-dated skew, distinct-bucket counting, and mixed in-/out-of-window data; DAO-backed adapter against in-memory SQLite for no-activities, 1-run, thin, strong, cross-athlete isolation, stale-history exclusion, non-run-type filtering, and default-`today` fallback.
| 3A.12 | `phase_kpi_priority` emitted per week (ordered list) | **Not started** | §8 phase_kpi_priority |
| 3A.13 | Phase transition week resolution (majority-of-days rule; ties → later phase) | **Not started** | §7 transition |
| 3A.14 | Namespace isolation: every coach-facing tool payload splits `planned.*` and `actual.*` | **Not started** | §6 namespace |
| 3A.15 | Future-week payload contract: `actual.*` fields and derived-outcome fields omitted/null | **Not started** | §6 future-week |

**Deliverables:**
- New columns or derived fields in `activities`, `plan_workouts`, `weekly_snapshots` (or equivalent).
- Unit tests per threshold row; boundary tests for 10-minute omission and Steady-null rule.
- Migration plan for historical activities (backfill `deviation_direction` where HR + duration permit).

---

## Phase B — Plan read tools + user context + metric glossary

Phase B covers **four** plan read tools, a cross-cutting **user-context** tool, and a **metric glossary** baked into the system prompt. Together these close ~15–20 percentage points of the question-coverage gap identified in the V1.6 design review (raising coverage from ~70–80 % to ~85–90 %).

### Plan read tools

| ID | Requirement | Status | Spec / doc ref |
|----|----|----|----|
| 3B.1 | Extend `get_run_summary` with `planned`, `actual`, `plan_status`, `violated_rest_day`, `deviation_direction` blocks | **Not started** | Topic 9 tool table; §6 |
| 3B.2 | New tool `get_weekly_plan(week_start_iso)` backed by `GET /api/plan/current-week` (generalized for any week) | **Not started** | Topic 9 |
| 3B.3 | `get_weekly_plan` enforces future-week payload contract deterministically | **Not started** | §6; Topic 9 future-week |
| 3B.4 | `get_weekly_plan` includes `phase_kpi_priority` and weekly `adherence_runs_pct` when past/present | **Not started** | §7, §8 |
| 3B.5 | New tool `get_plan_overview()` — phase blocks + volume curve + long-run progression, **no actuals** | **Not started** | Topic 9 |
| 3B.6 | New tool `get_phase_analysis(phase_id)` — per-type KPI trend for phase-to-date | **Not started** | Topic 9 |
| 3B.7 | All plan tools return display-ready strings (pace `M:SS/mi`, HR `142 bpm`, distance with unit) per Topic 4 | **Not started** | AGENTIC_COACH.md Topic 4 |
| 3B.8 | Tools follow Topic 5 caching: past-week cache-friendly, future-week invalidates on adaptation rewrite | **Not started** | AGENTIC_COACH.md Topic 5 |
| 3B.9 | Tool descriptions added to orchestrator registry in `src/smartcoach_mobile_coach/agent_tools.py` | **Not started** | orchestrator integration |

### User context tool (new, V1.6 coverage booster)

| ID | Requirement | Status | Notes |
|----|----|----|----|
| 3B.10 | New tool `get_user_context()` returning: race goal (name, date, goal_time if set), overarching plan objective, `baseline_status`, current phase, `coaching_level` (from `user_coach_preferences`), most recent session summary excerpt (when available), stated preferences (e.g. "prefers Saturday long runs") | **Not started** | Enables the coach to read user-level context in one call instead of inferring across several tools |
| 3B.11 | `get_user_context` returns light payload (≤ 2 KB); structured JSON with stable keys; no PII beyond what is already in `user_profile` | **Not started** | Payload size bounded per Topic 4 |
| 3B.12 | `get_user_context` is read-only and idempotent; participates in per-request dedup (Topic 5) | **Not started** | Caching strategy same as plan overview — invalidates on profile update |
| 3B.13 | Orchestrator nudges the model to call `get_user_context` early when `turn_type == "opening"` or on new-conversation turns | **Not started** | Prompt hint, not a hard rule |

### Metric glossary in system prompt

| ID | Requirement | Status | Notes |
|----|----|----|----|
| 3B.14 | Metric glossary block added to the coach system prompt — Z1–Z5 descriptions, HR Drift, Aerobic Efficiency, Pace Consistency, Zone Compliance, `deviation_direction` values, adherence bands | **Not started** | Prevents the coach from needing a tool call to answer "what's Z2?" — answers from prompt memory |
| 3B.15 | Glossary wording matches the definitions in `SMARTCOACH_SYSTEM_SPEC_V1.md` §3–§9 verbatim where possible; single source of truth for definitions | **Not started** | Spec ↔ prompt drift prevention |
| 3B.16 | Glossary is versioned in the prompt (e.g. `# glossary_version: 1`); bump when definitions change | **Not started** | Enables A/B comparison if glossary wording is tuned |

**Deliverables:**
- New tool implementations in `src/smartcoach_mobile_coach/agent_tools.py` (plan tools + `get_user_context`).
- Glossary block added to prompt builder in `src/smartcoach_mobile_coach/` (or wherever system prompt is composed).
- Fixture-driven tests in `tests/` for past / current / future week payload shapes.
- Snapshot tests confirming namespace isolation and `null` future-week fields.
- Test: ask "what's Z2?" in a factual turn → expect answer without a tool call.

---

## Phase C — In-chat plan rendering (coach contract)

| ID | Requirement | Status | Spec ref |
|----|----|----|----|
| 3C.1 | System prompt enforces §19.2 reasoning order (PLAN → ACTUAL → GAP → ACTION) | **Not started** | §19.2 |
| 3C.2 | Prompt includes §19.3 language-separation rules (plan / actual / comparison phrasing) | **Not started** | §19.3 |
| 3C.3 | Prompt includes §19.4 phase-aware KPI emphasis (reads `phase_kpi_priority`) | **Not started** | §19.4 |
| 3C.4 | Prompt enforces §19.5 future-week rules (no outcome prediction, no invented actuals) | **Not started** | §19.5 |
| 3C.5 | Prompt enforces §19.6 action-oriented requirement + four exempt categories using real enums | **Not started** | §19.6; `dialogue_manager.py` |
| 3C.6 | Prompt enforces §19.7 unplanned-run first-sentence acknowledgment; stronger tone when `violated_rest_day` | **Not started** | §19.7 |
| 3C.7 | Prompt enforces §19.8 adherence-informed tone (bands low / medium / high) | **Not started** | §19.8 |
| 3C.8 | Post-response validator checks the six read-only fields (§19.9) are not contradicted | **Not started** | §19.9 |
| 3C.9 | Validator: numeric-grounding check extended to new fields (`adherence_runs_pct`, `deviation_direction`, etc.) | **Not started** | §19.1 |

### Session-summary injection (pulled forward from Phase F)

The "real coach" quality of the experience depends heavily on cross-session memory. V1.6 pulls minimal session-summary injection forward into Phase C (was Phase F in the original design review) so the coach is not amnesiac between sessions while full Layer C user-memory work lands later.

| ID | Requirement | Status | Notes |
|----|----|----|----|
| 3C.10 | On new-conversation turn (`turn_type == "opening"` with no prior assistant messages in this thread), orchestrator injects the **most recent session summary** (if one exists) into the system prompt as short context (≤ 500 tokens) | **Not started** | Topic 6 Layer B exists in spec — this is the minimal read path |
| 3C.11 | Session summary injection follows the same privacy/cap rules as Topic 6 (no raw messages, only curated summary text) | **Not started** | AGENTIC_COACH.md Topic 6 guardrails |
| 3C.12 | Injected summary is clearly labeled in the prompt (e.g. `## PRIOR SESSION SUMMARY`) so the coach can reference or ignore it cleanly; the coach **must not** invent details not in the summary | **Not started** | §19.1 strict contract |
| 3C.13 | If no prior session summary exists (first-ever conversation), no injection — coach starts fresh | **Not started** | — |
| 3C.14 | End-of-session summary **writer** (Layer B) remains on the Phase F roadmap; 3C.10–3C.13 cover only the **read path** from summaries already stored | **Not started** | Split read vs write intentionally |

**Mapping: exempt turn classifications → real enums** (verified in `src/smartcoach_mobile_coach/dialogue_manager.py`):

| Spec exemption | Real condition |
|---|---|
| `turn_type == "acknowledgment"` | `classify_turn` returns `"acknowledgment"` |
| `turn_type == "clarification"` | `classify_turn` returns `"clarification"` |
| `interaction_mode == "factual"` | `derive_interaction_mode` returns `"factual"` |
| `interaction_mode == "ambiguous"` | `derive_interaction_mode` returns `"ambiguous"` |
| `intent == "preference_update"` | `infer_intent` returns `"preference_update"` |

**Deliverables:**
- Prompt builder changes in `coach/prompts/` and `src/smartcoach_mobile_coach/prompts/` (or wherever orchestrator composes system text).
- Validator layer in `src/smartcoach_mobile_coach/` that runs after the model reply and flags violations.
- Golden-path conversation tests: past run (executed), missed run, unplanned run with `violated_rest_day=true`, future-week question, factual snapshot (exempt).

---

## Phase D — Phase goals

| ID | Requirement | Status | Spec ref |
|----|----|----|----|
| 3D.1 | Table `user_phase_goals` — `(user_id, plan_id, phase, goal_text, goal_kpi_refs JSONB, created_at, completed_at)` | **Not started** | Topic 9; §19.4 |
| 3D.2 | Tool `save_phase_goal(phase, goal_text)` with explicit user-consent UI gate (see COACH_TOOLKIT_PROFILE_UPDATES_WITH_CONSENT pattern) | **Not started** | Topic 9 |
| 3D.3 | `get_phase_analysis(phase_id)` includes saved goals in payload | **Not started** | Topic 9 |
| 3D.4 | Coach language evaluates phase-to-date KPIs against saved goals (§19.4) | **Not started** | §19.4 |
| 3D.5 | Mobile UI to surface phase goals (optional V1.6; may defer to V1.7) | **Deferred** | — |

---

## Phase E — Plan adjustments

| ID | Requirement | Status | Spec ref |
|----|----|----|----|
| 3E.1 | LLM may propose adjustments in natural language; system parses into structured operations | **Not started** | §16 |
| 3E.2 | Volume-change proposals validated against ± 10 % cap | **Not started** | §16 Volume |
| 3E.3 | Quality-increase proposals validated against + 1/week cap + §14 gates | **Not started** | §16 Intensity |
| 3E.4 | Quality-decrease proposals accepted unbounded (safety) | **Not started** | §16 asymmetry |
| 3E.5 | Sub-phase-minimum quality requires `reason_code` on adaptation record | **Not started** | §16 phase integrity |
| 3E.6 | Mileage rounding to 0.5 mile granularity | **Not started** | §16 Volume |
| 3E.7 | No phase skipping — validator rejects proposals that leapfrog phase order | **Not started** | §16 phase integrity |
| 3E.8 | Long-run recovery day cannot be converted to training (§17 hard rule) — adaptation validator rejects | **Not started** | §17 |
| 3E.9 | Adaptation audit log records applied caps + `reason_code` per change, exposed to coach for transparency | **Not started** | §16 cap table summary |

---

## Phase F — Plan-aware long-term memory

**Scope note:** Minimal session-summary **read** path was pulled forward to Phase C (3C.10–3C.13). Phase F covers the **write** path and the full Layer C user-memory work.

| ID | Requirement | Status | Doc ref |
|----|----|----|----|
| 3F.1 | **Session summary writer** (Topic 6 Layer B) — writes a session summary row at conversation end with plan-related thread tags (e.g. "asked about Peak volume", "expressed knee concern") | **Not started** | AGENTIC_COACH.md Topic 6 |
| 3F.2 | User memory (Layer C) stores stated plan preferences (e.g. "prefers Saturday long runs") | **Not started** | Topic 6 |
| 3F.3 | User memory surfaced in `get_user_context` (backward-compatible extension of 3B.10) | **Not started** | Topic 9 composition |
| 3F.4 | Plan generator / weekly rebuild reads user memory for preference signals | **Not started** | Topic 9 composition |
| 3F.5 | Privacy + retention policy covers plan-derived memory | **Not started** | Topic 6 guardrails |

---

## Cross-cutting

| ID | Requirement | Status |
|----|----|----|
| X.1 | Feature flag for plan-aware tools (reuse existing `AGENT_MESSAGES_ENABLED` pattern) | **Not started** |
| X.2 | Plan tool payloads participate in Topic 5 insight cache | **Not started** |
| X.3 | Plan tool invocations logged per Topic 7 (tool name + success/error, no PII) | **Not started** |
| X.4 | Rate limits: plan tools counted within existing per-user agent-messages ceiling | **Not started** |
| X.5 | **Single-source-of-truth rule for deterministic fields** — see below | **Not started** |
| X.6 | Typed payloads via Pydantic (or equivalent) for every new tool return shape; no `Dict[str, Any]` for Topic 9 blocks | **Not started** |
| X.7 | `schema_version` on every new tool payload; bump on breaking changes; backward-compatible additions grandfathered | **Not started** |
| X.8 | Fixture-driven tests for V1.6 deviation thresholds (four-row table + tie-breaker + omission rules) | **Not started** |
| X.9 | Deprecation annotations (`# DEPRECATED V1.6 (PHASE_3_IMPLEMENTATION_CHECKLIST <id>): ...`) on any subsumed code paths; V1.7 cleanup ticket filed for each | **Not started** |
| X.10 | **Spec ↔ code traceability gate** — no PR merges without flipping the relevant checklist row to **Pass** with PR link as evidence | **Not started** |

### X.5 — Single-source-of-truth rule (normative, enforced in code review)

Every deterministic field listed in Appendix B of `SMARTCOACH_SYSTEM_SPEC_V1.md` has **exactly one producer function** and **zero re-derivations elsewhere**. Violations are blocking in code review.

| Field | Canonical producer (target location) | Readers |
|---|---|---|
| `deviation_direction` | `src/services/scoring/deviation.py::compute_deviation_direction_for_activity(...)` + pure `classify_deviation(...)` (**landed 2026-04-21, Phase A item 3**) | `run_insight.build_run_execution_block` (inside `actual.*`), `run_insight.execution_block_to_insight_summary_shape` (flat for LLM tool), `/api/plan/current-week` (via `**actual` spread); mobile `CurrentWeekActualBlock.deviation_direction` |
| `plan_status` | `src/services/plan/plan_status.py::plan_status_for_activity(matched_plan_workout_id)` + `plan_status_for_day(*, has_planned_workout, has_matching_activity, day_date, today)` (**landed 2026-04-21, Phase A item 1**) | `run_insight.build_run_execution_block` (per-activity top-level), `execution_block_to_insight_summary_shape` → LLM `get_run_summary`, `/api/plan/current-week` route (day-level authoritative), future Phase B `get_weekly_plan` (will also emit `unplanned` day-state) |
| `violated_rest_day` | `src/services/plan/plan_status.py::derive_violated_rest_day(*, plan_status_value, day_weekday, plan_training_days)` (**landed 2026-04-21, Phase A item 2** — colocated with `plan_status` producers) | `run_insight.build_run_execution_block` (top-level, alongside `plan_status`; keyword-only `plan_training_days` argument), `execution_block_to_insight_summary_shape` → LLM `get_run_summary` (coach §19.7 stronger-tone gate), `/api/plan/current-week` route (day-level, always `False` by construction; Phase B `get_weekly_plan` will surface the `True` case) |
| `adherence_runs_pct` | `src/services/scoring/adherence.py::compute_weekly_adherence(...)` + pure `classify_adherence_band(...)` + `AdherenceBand` enum (**landed 2026-04-21, Phase A item 5**) | `/api/plan/current-week` (week-level `adherence` block), future Phase B `get_weekly_plan` / `get_plan_overview`, §16 weekly adaptation pass, coach §19.8 tone gate |
| `completion_miles_pct` | Per run: `src/services/scoring/completion.py::compute_completion_pct(actual_miles, planned_miles)` (**0.B**). Weekly aggregate: `src/services/scoring/adherence.py::compute_weekly_adherence(...)` (**Phase A item 5**) — read `completion_miles_pct_weekly` off the `WeeklyAdherenceResult` | Per-run: `run_execution_analysis_service` (persisted on `activities.completion_pct`), canonical `actual.completion_pct`, legacy flat `completion_pct`. Weekly: `/api/plan/current-week` `adherence.completion_miles_pct`, Phase B tools |
| `baseline_status` | `src/services/baseline/baseline_status.py::compute_baseline_status_for_athlete(...)` + pure `classify_baseline_status(...)` + helper `count_runs_and_weeks_in_window(...)` (**landed 2026-04-21, Phase A item 4**) | Phase B 3B.10 `get_user_context`; §16 weekly adaptation pass; plan generator baseline-fallback branch |
| `phase_kpi_priority` | `src/services/phase/phase_priority.py::phase_kpi_priority_for(week_start, plan_id)` (new) | `get_weekly_plan`, `get_phase_analysis`, prompt builder |
| Week temporality (past / current / future) | `src/utils/date_helpers.py::classify_week_temporality(...)` (**landed 2026-04-21, 0.2**) | `get_weekly_plan`, `run_insight.py`, future-week contract enforcement, adaptation gate |
| Calendar week bounds (Mon–Sun) | `src/utils/date_helpers.py::get_week_bounds_for_date(...)` (**landed 2026-04-21, 0.2**) | `plan_routes.py::/current-week`, any future Mon–Sun range consumer |
| HR zone distribution (percent-of-time per zone) | `src/services/scoring/zone_compliance.py::zone_distribution_from_activity(...)` (**landed 2026-04-21, 0.3**) | `run_execution_analysis_service`, future `deviation_direction` producer |
| `(zone_compliance_pct, pct_above_zone, pct_below_zone)` | `src/services/scoring/zone_compliance.py::zone_metrics_for_type(...)` (**landed 2026-04-21, 0.3**) | `run_execution_analysis_service`, `deviation_direction` producer (Phase A), any future per-run-type zone scorer |
| Per-run `planned.*` / `actual.*` block (extraction from `Activity`) | `src/smartcoach_mobile_coach/run_insight.py::build_run_execution_block(act)` (**landed 2026-04-21, 0.A**) | `GET /api/plan/current-week` (via `execution_block_to_weekly_plan_shape`), `get_run_summary` → `facts.execution_summary` (via `execution_block_to_insight_summary_shape`), future Phase B plan-aware tools (namespaced shape direct) |
| Per-run `completion_pct` (formula) | `src/services/scoring/completion.py::compute_completion_pct(actual_miles, planned_miles)` (**landed 2026-04-21, 0.B**) | `run_execution_analysis_service.analyze_activity_execution` (stored on `activities.completion_pct`), `gyr_metrics_service` (weekly GYR aggregate), future Phase A `adherence_runs_pct` producer |
| V1.6 §7 completed-run threshold (`>= 50% of plan`) | `src/services/scoring/completion.py::COMPLETION_THRESHOLD_RATIO` / `COMPLETION_THRESHOLD_PCT` + `is_run_completed(...)` (**landed 2026-04-21, 0.B**) | future Phase A `adherence_runs_pct` producer, any coach-facing "this run counted" predicate |

### 0.C — `get_weekly_training_insight` no-new-consumers enforcement (normative)

Status: **Deprecated 2026-04-21.** Replacement is `get_weekly_plan` (Phase B, V1.7).

**Policy:** No PR may introduce a new caller of `tool_get_weekly_training_insight`, a new entry referencing the handler key `"get_weekly_training_insight"` outside the single existing dispatch line, or any new system-prompt snippet that instructs the LLM to prefer this tool. Existing consumers are preserved during V1.6 so live coach flows do not break.

**Enforcement mechanisms** (in order of precedence):

1. **Runtime — DeprecationWarning.** `tool_get_weekly_training_insight()` emits `DeprecationWarning` via `warnings.warn(_GWTI_DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=2)` on every call. The message cites `V1.6`, `0.C`, and names `get_weekly_plan`, making it grep-able in CI logs and log aggregators.
2. **Test lock-in.** `tests/test_get_weekly_training_insight_deprecation.py` pins:
   - exactly one `DeprecationWarning` per invocation,
   - the message mentions the replacement tool and cites `0.C`,
   - the return contract is behavior-preserved,
   - callers may filter the warning when they intentionally consume it.
   Dropping the warning or weakening the message turns the suite red — forcing a deprecation-policy conversation.
3. **Code-review checklist.** Reviewers flag any PR that (a) imports `tool_get_weekly_training_insight` outside `agent_tools.py`, (b) adds a new entry with the handler-key string, or (c) adds a new `orchestrator.py` system-prompt rule that tells the LLM to reach for this tool.
4. **LLM-facing signal.** The OpenAI tool description in `scripts/setup_coach_tools.py` now opens with `[DEPRECATED — will be replaced by get_weekly_plan …]`. The tool remains enabled and callable so live conversations keep working.

**Known current consumers** (grandfathered, do not expand):
- `src/smartcoach_mobile_coach/agent_tools.py` — the tool function, the `_TOOL_HANDLERS` dispatch entry, and the `execute_tool` handler-key branch.
- `src/smartcoach_mobile_coach/orchestrator.py` — system-prompt snippets (lines ~631, 657, 660–663, 856, 863, 1307). Rewrites happen in Phase C–F once `get_weekly_plan` is available.
- `scripts/setup_coach_tools.py` — OpenAI tool schema registration.
- `tests/test_weekly_insight_lazy_payload.py` — existing behavior tests (kept, now also surface the deprecation warning in pytest summary).

Any consumer not in this list is a new consumer and must be rejected in review.

> **Enforcement:** Each producer module has 100 % test coverage for the rules in the spec it implements. No other file in the repo re-computes these values. Grep check during code review: a commit that introduces `pct_above` arithmetic outside `deviation.py` fails review.

Actual paths above are **proposed locations**. If existing architecture already has a better home (e.g. an existing `scoring/` package), colocate. The rule is **one producer per field**, not the specific path.

---

## V1.7 (deferred) — Run-type consolidation

Tracked here so it is not lost:

1. Product decision on Steady mapping (Option A: demote to Easy with wider tolerance; Option B: extend Tempo down; Option C: modifier flag on Easy).
2. Appendix A redistribution (Build 20–25 % Steady and Peak 20 % Steady must redistribute when Steady is removed).
3. Steady-specific `deviation_direction` thresholds (or formal retirement of Steady from `CANONICAL_RUN_TYPES`).
4. Backward-compatible alias for existing plans with `run_type_key = "steady"`.
5. Data migration plan for in-flight and completed plans.

**Do not** start V1.7 work until Phase A lands — the six V1.6 deterministic fields are the foundation.

---

## Suggested next steps (V1.6 kickoff order)

### Step 1 — Pre-Phase A cleanup (mandatory before schema work)

Execute in this order — low-risk to higher-risk:

1. **0.1** — Document `null` vs absent convention in `AGENTIC_COACH.md` Topic 4 (docs-only, 5 min). **Done 2026-04-21**.
2. **0.5** — Pin enums in `dialogue_manager.py` to typed constants (low-risk, enables all subsequent §19.6 work). **Done 2026-04-21**.
3. **0.2** — Centralize "is future week" utility (enables future-week contract in 3A.15 and 3B.3). **Done 2026-04-21**.
4. **0.3** — Centralize zone-compliance / `pct_above` / `pct_below` computation (prerequisite for `deviation_direction`). **Done 2026-04-21**.
5. **0.4** — Grep + replace bare run-type string literals (enables Steady null-handling safely).
6. **0.A** — Consolidate `run_insight.py` as single source for `planned.*` / `actual.*` blocks. **Done 2026-04-21** — canonical block builder + two byte-exact legacy-shape adapters; `_execution_payload` deleted; parity locked by 8 unit tests.
7. **0.B** — One `completion_pct` compute + named `COMPLETION_THRESHOLD = 0.50`. **Done 2026-04-21** — canonical module `src/services/scoring/completion.py` with `compute_completion_pct`, `is_run_completed`, `COMPLETION_THRESHOLD_RATIO` / `COMPLETION_THRESHOLD_PCT`; both prior inline producers refactored to consume it; 14 unit tests lock the contract.
8. **0.C** — Resolve `get_weekly_training_insight` vs `get_weekly_plan`. **Done 2026-04-21** — deprecated with runtime `DeprecationWarning`, test lock-in, and a "no new consumers" governance rule above.
9. **0.D** — Kill GET-time HR zone inference in `plan_routes.py`. **Done 2026-04-21** — `_infer_run_type_key_for_hr` and zone-revalidation deleted; `_resolve_run_type_key_for_workout` normalizes through canonical `LEGACY_TO_CANONICAL_RUN_TYPE`; stored `target_hr` is authoritative.
10. **0.E** — Mobile refactor to consume `planned.*` / `actual.*` directly. **Done 2026-04-21** — backend dual-emits canonical namespaces alongside legacy flat fields (single source, cannot drift); mobile `weekly-plan-panel.tsx` and `CurrentWeekExecutionPayload` type refactored; legacy flat fields JSDoc-deprecated; mobile `tsc --noEmit` green.

### Step 2 — Phase A schema work

11. Confirm column/field placement in `activities` and `plan_workouts` for `deviation_direction`, `plan_status`, `violated_rest_day`.
12. ~~Confirm storage location for weekly `adherence_runs_pct` and `phase_kpi_priority` (weekly snapshot table vs. on-demand compute with cache).~~ **Resolved 2026-04-21 — on-demand compute, no persistence.** Applies to `adherence_runs_pct` (landed Phase A item 5) and will apply to `phase_kpi_priority` (Phase A item 6). Matches the derived-on-read policy used for `plan_status`, `deviation_direction`, and `baseline_status`: aggregation from per-day rows is trivially fast, and persistence would require invalidation on every matched-activity write. Revisit only if the aggregation becomes a measured hot-path.
13. Write unit tests for deviation thresholds **before** implementation (four-row table + tie-breaker + omission).
14. Land Phase A fields with non-breaking additions; Phase B tools then read them.

---

*Update this table as each phase / pre-phase item ships. Link PRs under the relevant row.*

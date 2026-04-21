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
| 0.A | **`run_insight.py` becomes single source** for per-run `planned.*` / `actual.*` namespaced blocks; `get_run_summary` and `GET /api/plan/current-week` both read from it; no parallel "plan vs actual" builder in `plan_routes.py` | **Not started** | Backend |
| 0.B | **One `completion_pct` computation** feeds per-run score, weekly `adherence_runs_pct`, and coach payload; the 0.50 "completed" threshold lives as a named constant (e.g. `COMPLETION_THRESHOLD = 0.50` in `run_type_constants.py` or a new `adherence_constants.py`), not inlined | **Not started** | Backend |
| 0.C | **Resolve `get_weekly_training_insight` vs `get_weekly_plan`** — either deprecate `get_weekly_training_insight` (fold into `get_weekly_plan` when the question centers on the plan) or document the scope split explicitly; mark deprecations with `# DEPRECATED V1.6 (PHASE_3_IMPLEMENTATION_CHECKLIST 0.C): ...` | **Decision made & Done** (2026-04-21) — **DEPRECATE.** Replacement is `get_weekly_plan` (V1.7, AGENTIC_COACH.md Topic 9), which will enforce V1.6 §6 namespace isolation and the future-week payload contract. Policy: **NO NEW CONSUMERS.** Existing consumers preserved so live coach flows do not break. Changes landed: (1) module-level deprecation block + `_GWTI_DEPRECATION_MESSAGE` constant + `DeprecationWarning` emitted on every `tool_get_weekly_training_insight()` call in `src/smartcoach_mobile_coach/agent_tools.py`; (2) `# DEPRECATED V1.6 (... 0.C): ...` comment on the `_TOOL_HANDLERS` entry and the `scripts/setup_coach_tools.py` OpenAI schema block; (3) LLM-facing description now opens with `[DEPRECATED — will be replaced by get_weekly_plan …]` to steer the model off the tool; (4) lock-in test `tests/test_get_weekly_training_insight_deprecation.py` (12 cases) that asserts the warning fires, names the replacement, cites 0.C, is filter-able, and that the return contract is preserved. See "0.C no-new-consumers enforcement" below. | Backend (`src/smartcoach_mobile_coach/agent_tools.py`) |
| 0.D | **Kill GET-time HR zone inference** in `plan_routes.py` (lines 59–67 infer zones from workout name strings); zones must be stored at plan-generation time in `plan_storage_service.py` and read unchanged on GET | **Done** (2026-04-21) — Deleted `_infer_run_type_key_for_hr` (substring text-matching over `workout_type`) and the two GET-time "zone revalidation" branches (`stored_zone != expected_zone → target_hr = expected_hr`) in `/api/plan/current` and `/api/plan/current-week`. Replaced with `_resolve_run_type_key_for_workout(w)` which normalizes through `LEGACY_TO_CANONICAL_RUN_TYPE` (single source of truth — `src/utils/run_type_constants.py`). Stored `target_hr` is now authoritative; the GET path only falls back to `PlanStorageService._calculate_hr_zone(canonical_key, profile)` when the DB value is missing (legacy rows predating `target_hr` persistence). No mutation. Dropped the now-unused `import re`. Test coverage added in `tests/test_plan_current_week_route.py`: (1) legacy `run_type_key="endurance"` normalizes to canonical `"long"` and stored `target_hr` is returned verbatim even when a recomputation would disagree; (2) missing `target_hr` gets a canonical Z-label via the narrow fallback. Backfill for legacy plans remains the dedicated responsibility of `recalculate_hr_zones_service.recalculate_hr_zones_for_plan` (invoked on profile/max-HR update), not the GET path. | Backend (`src/routes/plan_routes.py`) |
| 0.E | **Mobile `weekly-plan-panel.tsx` refactor** — consume `planned.*` / `actual.*` top-level keys directly from the new payload shape; no adapter that "unflattens" the current intermediate form; `weekly-plan-from-workouts.ts:56-60` string-match run-type inference removed (replaced by server-side canonical types only) | **Not started** | Mobile (`smartcoach_app/`) |

### Pre-Phase A gating rule

> **No Phase A schema work (field additions) may merge until 0.1–0.5 and 0.A–0.E are complete or explicitly deferred with a tracked ticket.** The gate prevents "land the field, clean up later" patterns that become permanent drift.

---

## Phase A — Schema discipline

| ID | Requirement | Status | Spec ref |
|----|----|----|----|
| 3A.1 | `deviation_direction` computed per activity (`too_hard` / `too_easy` / `on_target` / `null`) | **Not started** | §5 Deviation Direction |
| 3A.2 | Per-run-type thresholds enforced (Recovery 5/40, Easy 15/30, Tempo 20/25 main-block, Long 20/30) | **Not started** | §5 table |
| 3A.3 | Tie-breaker (both thresholds → `too_hard`) | **Not started** | §5 rule 1 |
| 3A.4 | Omission rules (`null` when HR missing, `duration_seconds < 600`, or `planned_type = Steady`) | **Not started** | §5 rule 2 |
| 3A.5 | Tempo evaluation scope = main block (warm-up/cool-down excluded) | **Not started** | §5 rule 3 |
| 3A.6 | `plan_status` enum computed per plan-day / activity pair | **Not started** | §6 enum table |
| 3A.7 | `violated_rest_day` boolean on activities | **Not started** | §6 derived flags |
| 3A.8 | `adherence_runs_pct` computed weekly (primary) with completion rule `completion_miles_pct ≥ 0.50` | **Not started** | §7 metrics |
| 3A.9 | `completion_miles_pct` exposed as supporting field per run | **Not started** | §7 metrics |
| 3A.10 | Unplanned runs excluded from `adherence_runs_pct` numerator and denominator | **Not started** | §7 unplanned rule |
| 3A.11 | `baseline_status` enum (`insufficient` / `thin` / `strong`) per user, recomputed weekly | **Not started** | §12 baseline_status |
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
| `deviation_direction` | `src/services/scoring/deviation.py::compute_deviation_direction(...)` (new) | `run_insight.py`, `agent_tools.py`, validator |
| `plan_status` | `src/services/plan/plan_status.py::derive_plan_status(...)` (new) | `run_insight.py`, `plan_routes.py`, agent tools |
| `violated_rest_day` | Same module as `plan_status` — colocated derivation | Same readers as `plan_status` |
| `adherence_runs_pct` | `src/services/scoring/adherence.py::compute_weekly_adherence(...)` (new) | weekly insight, `get_weekly_plan`, coach payloads |
| `completion_miles_pct` | Same module as `adherence_runs_pct` | per-run score, weekly adherence, coach payloads |
| `baseline_status` | `src/services/baseline/baseline_status.py::derive_baseline_status(...)` (new) | plan generator, `get_user_context`, adaptation |
| `phase_kpi_priority` | `src/services/phase/phase_priority.py::phase_kpi_priority_for(week_start, plan_id)` (new) | `get_weekly_plan`, `get_phase_analysis`, prompt builder |
| Week temporality (past / current / future) | `src/utils/date_helpers.py::classify_week_temporality(...)` (**landed 2026-04-21, 0.2**) | `get_weekly_plan`, `run_insight.py`, future-week contract enforcement, adaptation gate |
| Calendar week bounds (Mon–Sun) | `src/utils/date_helpers.py::get_week_bounds_for_date(...)` (**landed 2026-04-21, 0.2**) | `plan_routes.py::/current-week`, any future Mon–Sun range consumer |
| HR zone distribution (percent-of-time per zone) | `src/services/scoring/zone_compliance.py::zone_distribution_from_activity(...)` (**landed 2026-04-21, 0.3**) | `run_execution_analysis_service`, future `deviation_direction` producer |
| `(zone_compliance_pct, pct_above_zone, pct_below_zone)` | `src/services/scoring/zone_compliance.py::zone_metrics_for_type(...)` (**landed 2026-04-21, 0.3**) | `run_execution_analysis_service`, `deviation_direction` producer (Phase A), any future per-run-type zone scorer |

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
6. **0.A** — Consolidate `run_insight.py` as single source for `planned.*` / `actual.*` blocks.
7. **0.B** — One `completion_pct` compute + named `COMPLETION_THRESHOLD = 0.50`.
8. **0.C** — Resolve `get_weekly_training_insight` vs `get_weekly_plan`. **Done 2026-04-21** — deprecated with runtime `DeprecationWarning`, test lock-in, and a "no new consumers" governance rule above.
9. **0.D** — Kill GET-time HR zone inference in `plan_routes.py`. **Done 2026-04-21** — `_infer_run_type_key_for_hr` and zone-revalidation deleted; `_resolve_run_type_key_for_workout` normalizes through canonical `LEGACY_TO_CANONICAL_RUN_TYPE`; stored `target_hr` is authoritative.
10. **0.E** — Mobile refactor to consume `planned.*` / `actual.*` directly. **← Next**

### Step 2 — Phase A schema work

11. Confirm column/field placement in `activities` and `plan_workouts` for `deviation_direction`, `plan_status`, `violated_rest_day`.
12. Confirm storage location for weekly `adherence_runs_pct` and `phase_kpi_priority` (weekly snapshot table vs. on-demand compute with cache).
13. Write unit tests for deviation thresholds **before** implementation (four-row table + tie-breaker + omission).
14. Land Phase A fields with non-breaking additions; Phase B tools then read them.

---

*Update this table as each phase / pre-phase item ships. Link PRs under the relevant row.*

# Plan cleanup tracker

Lightweight record of plan-generation legacy vs V2. Source: codebase audit (orchestrator, Pass1, spine, coach/API consumers). **Ambition gap / readiness / intake alignment** inventory and post-migration cleanup gates are in § [Ambition gap, readiness, and intake alignment](#ambition-gap-readiness-and-intake-alignment-phases-23-and-44) below.

## Findings (short)

- **V2** (`PlanGenerationOrchestratorV2`, `plan_generation_v2` routes) is the live path; Step 1 fitness uses the **materialized view**.
- **InsightsCalculationService (L2)** — **LEGACY REMOVED**, including **`RecommendationsGenerator`** and **`fitness_calculator`** modules under `calculations/`.
- **`Pass1WeeksSelectorV2`**: orchestrator uses **`_map_weeks`** only; calendar length is Steps 3–4 in the orchestrator.
- **Plan validation:** production uses **`PlanValidationServiceV2`** only; v1 module removed.
- **Old 6-layer orchestrator:** `training_plan_orchestrator_service.py` is not in the repo; historical notes remain in some docs.
- **`pass1_rationale`** is active: orchestrator attaches it to validation; API draft payload and coach (`agent_tools`) read it for baseline copy.
- **Peak week** appears twice in spirit: spine assigns phases / `is_peak_week`; `compute_long_run_peak_week_metadata` runs in spine and again for Pass1 rationale (redundant work, not a user-facing conflict).

## Artifacts

| Artifact | Location | Classification | Action | Safe? | Status |
|----------|----------|----------------|--------|-------|--------|
| V2 pipeline (orchestrator, Pass1 LR-first, Pass3/4, MV Step 1) | `v2/plan_generation_orchestrator_v2.py`, `v2/marathon/pass1_longrun_first_v2.py`, `routes/plan_generation_v2.py` | ACTIVE | Keep | NO | TODO |
| Long-run spine + curve validation | `v2/shared_v2/long_run_spine_v2.py`, `v2/shared_v2/long_run_curve_validation.py` | ACTIVE | Keep | NO | TODO |
| Weekly totals from long runs | `v2/marathon/weekly_total_calculator_v2.py` | ACTIVE | Keep | NO | TODO |
| Adaptive marathon peak LR | `v2/marathon/adaptive_marathon_peak.py` | ACTIVE | Keep | NO | TODO |
| Long-run signals | `v2/shared_v2/long_run_signals.py` | ACTIVE | Keep | NO | TODO |
| Pass1 rationale / `pass1_rationale` | `pass1_longrun_first_v2.py` → orchestrator → API + coach | ACTIVE | Keep | NO | TODO |
| Pass1 weeks `_map_weeks` | `v2/shared_v2/pass1_weeks_selector_v2.py` | ACTIVE | Keep | NO | TODO |
| Pass1WeeksSelectorV2 `select_weeks` (removed) | `v2/shared_v2/pass1_weeks_selector_v2.py` | SHADOW | Removed | YES | DONE |
| Constraints, race-date validation, scenario adjustments | `v2/plan_constraints_service.py`, `v2/race_date_validation_service.py`, `v2/scenario_adjustments_service.py` | ACTIVE | Keep | NO | TODO |
| PlanValidationServiceV2 | `v2/plan_validation_service_v2.py` | ACTIVE | Keep | NO | TODO |
| `calculate_weekly_mileage_from_workouts` | `workout_utils.py` | ACTIVE | Keep | NO | TODO |
| `get_initial_pace_seed` | `pace/calculator.py` | ACTIVE | Keep | NO | TODO |
| Decision trace (weekday / LR day strings) | `decision_trace.py` | ACTIVE | Keep | NO | TODO |
| Pass1 `_validate_weeks` (removed) | `v2/marathon/pass1_longrun_first_v2.py` | SHADOW | Removed | YES | DONE |
| Pass1WeeksSelector (v1) | `pass1_weeks_selector.py` (removed) | LEGACY | Removed | YES | DONE |
| InsightsCalculationService | `insights_calculation_service.py` (removed) | LEGACY | **LEGACY REMOVED** | YES | DONE |
| RecommendationsGenerator | `calculations/recommendations_generator.py` (removed) | LEGACY | **LEGACY REMOVED** | YES | DONE |
| fitness_calculator | `calculations/fitness_calculator.py` (removed) | LEGACY | **LEGACY REMOVED** | YES | DONE |
| PlanValidationService (v1) | `plan_validation_service.py` (removed) | LEGACY | Removed | YES | DONE |
| TrainingPlanOrchestratorService tests + doc refs | `tests/.../test_training_plan_orchestrator_service.py` (removed), docs | LEGACY | Removed tests; docs marked LEGACY | NO | DONE |
| DataCollectionService | `data_collection_service.py` | ACTIVE | Keep (non–V2-gen callers) | NO | TODO |
| PlanStorageService | `plan_storage_service.py` | ACTIVE | Keep | NO | TODO |

## Notes

- V2 plan generation is the source of truth.
- Legacy components should not be used for new development.
- Prefer **MV** for product-facing “current fitness” in plan flows; activity-list rollups are not used for V2 generation after L2 removal.

---

## Ambition gap, readiness, and intake alignment (phases 2.3 and 4.4)

**Purpose:** Single place to record what is **canonical** vs **legacy/compatibility** for `ambition_gap`, `plan_generation_readiness`, and intake alignment — so future changes do not re-introduce `stance`-only branching or divergent tension logic.

### Shipped (current implementation — what “done” means)

| Area | Behavior |
|------|----------|
| **Canonical signal** | Prefer `ambition_gap["attributions"]` (especially `STANCE_HIGH_TENSION_TIME_VS_THIN_BASELINE`, `STANCE_MANAGEABLE_TENSION_TIME_VS_MODERATE_BASELINE`, goal/baseline `RULE_*` codes) for tension and related branching. |
| **Intake alignment** | `evaluate_intake_alignment_state(..., ambition_attributions=...)` resolves effective tension from those codes when present; see `src/coaching_intelligence/intake_alignment.py`. |
| **Wiring** | `pre_generation_runner_assessment` passes ambition attributions; `agent_tools` stores `ambition_attributions` on `alignment`; `plan_intake_flow._recompute_alignment_branch` prefers that list. |
| **Readiness facts / digest** | Still emit `ambition_stance` for observability alongside attribution lists (snapshot). |
| **Suggestions** | Pace-gap `adjust_goal` suggestion can set `proposed_value` (softened marathon clock from `target_time` + pace deficit × ~26.2 mi); see `src/coaching_intelligence/policy/suggestions.py`. |
| **Documentation** | `src/coaching_intelligence/ambition_gap.py` module doc states that **`stance` is a legacy snapshot** for APIs/display and new logic should prefer **attributions**. |

### Legacy / compatibility layer (explicit — **do not extend** without updating this table)

These paths exist **on purpose** until all producers and tests always carry full attributions. **New product logic should not add more `stance`-first branches.**

| Location | What is legacy | Why it remains |
|----------|----------------|----------------|
| `ambition_gap.evaluate_ambition_gap` | Still sets `stance` string | API contract, analytics, mobile/coach payloads; paired with attributions in normal production. |
| `plan_generation_readiness._ReadinessBuilder` | `ambition_stance` property (observability in facts/digest only); **`ambition_time_goal_tension()` / `ambition_high_tension_thin_baseline()` use `attributions` only** (Step 2 done — no stance+band fallback). | Any hand-built API with empty `attributions` no longer gets tension rules from `stance` alone. |
| `intake_alignment._effective_ambition_stance` | If no tension codes in `ambition_attributions`, uses the `ambition_stance` argument | Callers that omit attribution list or pass empty list. |
| `pre_generation_runner_assessment` | Still passes `ambition_stance=str(ambition.get("stance") or "")` | Required parameter + backward compatibility. |
| `plan_intake_flow._recompute_alignment_branch` | Uses **only** ``alignment["ambition_attributions"]`` for attribution-first tension (no mining merged ``attributions``). | Persisted states without that key rely on **``ambition_stance``** inside ``evaluate_intake_alignment_state`` only. |
| `pre_generation_runner_review` | `_copy_lines_for_v1` uses **`_tension_plain_summary_from_ambition`** when `RULE_TENSION_AFTER_ALIGNMENT` and codes present; else **`stance`** for summary. | Narrative aligned with attribution-first policy. |
| `agent_tools` alignment / brief | Still sets `ambition_stance` on alignment blob; **`posture_context` adds `ambition_attributions`**; `stance` in brief remains legacy snapshot. | Coach UX reads attributions first from prompt + brief. |

### Cleanup backlog (after implementation is stable — **planned removal order**)

Do **not** delete these until the **exit criteria** are met; otherwise production or fixtures will silently drift.

| Step | Action | Exit criteria (minimum) |
|------|--------|------------------------|
| 1 | Audit **all** builders of `assessment_api` / `ambition_gap` (tests, fixtures, any cached JSON): ensure `attributions` always includes the same `STANCE_*` / `RULE_*` codes that `evaluate_ambition_gap` would emit for that scenario. **Backend tests:** shared helper `tests/coaching_intelligence/ambition_gap_fixtures.py` → `synthetic_ambition_attributions`; `_assessment` in `test_plan_generation_readiness.py` uses it. | No intentional empty `attributions` for meaningful ambition scenarios in **this** repo’s tests; scan any external fixtures / golden files separately. |
| 2 | Remove **readiness** fallbacks in `ambition_time_goal_tension()` and `ambition_high_tension_thin_baseline()` that key only on `stance` + band (keep `ambition_stance` in **output** facts if still needed for dashboards). | **Done in repo** (2026-05-12): attributions-only for these two gates; staging soak still advised for non-repo clients. |
| 3 | Tighten **intake** `ambition_attributions` contract: require non-optional list from server for alignment-enabled flows; narrow or delete merged-`attributions` filter fallback in `plan_intake_flow`. | **Done in repo** (2026-05-13): recompute uses `ambition_attributions` only; `agent_tools` continues to set it for new alignment blobs. |
| 4 | **Optional:** Deprecate then remove `ambition_stance` from client-facing alignment types / prompts; keep server-only snapshot if analytics still needs it. | **Done in repo** (2026-05-13): coach prompt leads with **ambition attributions**; `posture_context` includes **ambition_attributions**; mobile intake UI attention prefers attribution tension codes with stance fallback. `ambition_stance` retained on wire. |
| 5 | **Optional hygiene:** extract shared clock parse/format for suggestions vs readiness. | **Done** — `src/coaching_intelligence/time_clock.py` (`parse_clock_seconds`, `format_clock_seconds`). |

### Follow-on (post backlog Steps 1–5)

| Item | Status |
|------|--------|
| Runner-review tension copy | Uses ambition **attributions** for `RULE_TENSION_AFTER_ALIGNMENT` when `STANCE_*` codes present (`pre_generation_runner_review._tension_plain_summary_from_ambition`). |
| Mobile `proposed_value` | **Runner Analysis** card parses readiness **`suggestions`** and shows **Suggested inputs** with optional “try {clock}” (`runner-analysis-card.tsx`). |

### Refactor roadmap — Phase 2 / 3 checkpoint (readiness + evidence)

**Phase 2 (consolidate readiness)** — *aligned with single-source policy:*

| Item | Status |
|------|--------|
| 2.1 Review status from readiness only | **`assessment_status_from_readiness`**: `allow` → `ready_to_generate`; **`defer` + `insufficient_data`** → `needs_more_info`; else `needs_user_decision`. No `required_changes` sub-filter for “more info” vs “decision.” |
| 2.1 Narrative | **`_copy_lines_for_v1`** tailors `needs_more_info` for alignment vs activity collection vs goal context; **`RULE_TENSION_AFTER_ALIGNMENT`** uses attribution phrase or baseline-band copy only (no legacy `stance` string in user-facing summary). |
| 2.2 Orchestrator / tool | Runner review bundle uses **`build_pre_generation_runner_review_v1`**. **`agent_tools`** does not call **`classify_assessment_status_v1`**; it reads **`runner_review_assessment_status`** from UX state when gating. |
| 2.3 Readiness vs ambition | **`_apply_fact_category_severity`** already keys goal-demand tension on **`ambition_time_goal_tension()`** (attributions). **`ambition_stance`** remains on digest/API for observability only. |

**Phase 3 (runner evidence layer)** — *quick assessment:*

| Item | Status |
|------|--------|
| 3.1–3.2 Evidence build + history window | **`build_runner_evidence`** in `plan_intake_activity_context.py`; **`runner_evidence`** on assessment API; history lookback via env (e.g. `SMARTCOACH_PLAN_INTAKE_HISTORY_WEEKS`). **Done.** |
| 3.3 Typed path through readiness | **`_assessment_parts`** merges selected `runner_evidence` keys into the internal **`activity`** dict; readiness still uses **`builder.activity`** accessors — **optional future cleanup**: dedicated **`builder.evidence`** / fewer dict merges. |
| 3.4 Evidence snapshot id | **`evidence_snapshot_id`** on readiness and assessments. **Done.** |

### Drift risks to watch

- Adding new tension or goal-context rules in **`evaluate_ambition_gap`** without corresponding consumers in **readiness** and **intake_alignment** (or vice versa).
- New code that branches on **`stance` alone** instead of attributions + effective stance helper.
- **Apply chip actions** from `suggestions` (beyond display-only hint) — not wired; card is informational.

*Last updated: 2026-05-12 — Phase 2 status mapping + Phase 3 checkpoint; runner-review `needs_more_info` now includes all `insufficient_data` deferrals.*

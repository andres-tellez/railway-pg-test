# Plan cleanup tracker

Lightweight record of plan-generation legacy vs V2. Source: codebase audit (orchestrator, Pass1, spine, coach/API consumers).

## Findings (short)

- **V2** (`PlanGenerationOrchestratorV2`, `plan_generation_v2` routes) is the live path; Step 1 fitness uses the **materialized view**, not `InsightsCalculationService`.
- **InsightsCalculationService** + **RecommendationsGenerator** + **fitness_calculator** remain for tests and ad-hoc scripts; they are **not** wired into the V2 orchestrator.
- **`Pass1WeeksSelectorV2`**: orchestrator uses **`_map_weeks`** only; calendar length is Steps 3–4 in the orchestrator.
- **`Pass1LongRunFirstV2._validate_weeks`** has no callers.
- **`PlanValidationService` (v1)** is still tested; production V2 generation uses **`PlanValidationServiceV2`**.
- **`training_plan_orchestrator_service.py`** is referenced by tests/docs but the module path is missing — tests are stale or file was removed.
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
| Pass1 `_validate_weeks` | `v2/marathon/pass1_longrun_first_v2.py` | SHADOW | Delete | YES | TODO |
| Pass1WeeksSelector (v1) | `pass1_weeks_selector.py` (removed) | LEGACY | Removed | YES | DONE |
| InsightsCalculationService | `insights_calculation_service.py` | LEGACY | Investigate | NO | TODO |
| RecommendationsGenerator | `calculations/recommendations_generator.py` | LEGACY | Investigate | NO | TODO |
| fitness_calculator | `calculations/fitness_calculator.py` | LEGACY | Investigate | NO | TODO |
| PlanValidationService (v1) | `plan_validation_service.py` | LEGACY | Delete after tests migrated or dropped | NO | TODO |
| TrainingPlanOrchestratorService tests + doc refs | `tests/.../test_training_plan_orchestrator_service.py`, various `docs/` | LEGACY | Fix (remove tests or restore module) | NO | TODO |
| DataCollectionService | `data_collection_service.py` | ACTIVE | Keep (non–V2-gen callers) | NO | TODO |
| PlanStorageService | `plan_storage_service.py` | ACTIVE | Keep | NO | TODO |

## Notes

- V2 plan generation is the source of truth.
- Legacy components should not be used for new development.
- MV-based mpw vs activity-list mpw (Insights) can disagree; do not mix for one product surface without an explicit policy.

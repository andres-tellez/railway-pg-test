# Plan creation (V2) — overview

This document is the **single source of truth** for how a training plan is generated in the current codebase.

## End-to-end flow

**MV → OrchestratorV2 → Pass1 → Spine → Totals → Validation → Plan**

- **MV** — Weekly fitness comes from the **materialized view** (same source as metrics), via `get_weekly_fitness_from_materialized_view` in `src/services/metrics_helper_service.py`.
- **OrchestratorV2** — `PlanGenerationOrchestratorV2` in `src/services/training_plan/v2/plan_generation_orchestrator_v2.py` runs the deterministic long-run-first pipeline (`generate_longrun_first`).
- **Pass1** — `Pass1LongRunFirstV2` (`src/services/training_plan/v2/marathon/pass1_longrun_first_v2.py`) chooses progression inputs; the **long-run spine** is built by `build_long_run_spine_weeks` in `src/services/training_plan/v2/shared_v2/long_run_spine_v2.py`, with curve checks from `validate_long_run_curve` in `src/services/training_plan/v2/shared_v2/long_run_curve_validation.py`.
- **Totals** — `calculate_weekly_totals_from_long_runs` in `src/services/training_plan/v2/marathon/weekly_total_calculator_v2.py` derives weekly volume from the spine.
- **Validation** — `PlanValidationServiceV2` in `src/services/training_plan/v2/plan_validation_service_v2.py` validates the assembled plan (and related checks inside the orchestrator, e.g. spine quality).
- **Plan** — The orchestrator returns a validation-style payload (`valid`, `validated_plan` / draft fields, violations, traces). **Create** persists a valid plan; **draft** returns a preview only.

Between totals and validation, the orchestrator **places workouts** (`Pass3WorkoutDistribution`) and **fills workout details** (`Pass4WorkoutDetails`) — still deterministic V2 code, same module tree as above.

## HTTP entry points

Both **`POST /api/plan/draft`** and **`POST /api/plan/create`** call `run_v2_plan_generation` from `src/smartcoach_mobile_coach/plan_generation/facade.py`, which constructs `PlanGenerationOrchestratorV2` and invokes `generate_longrun_first`. Draft responses are shaped with `build_standard_draft_payload` in `src/smartcoach_mobile_coach/plan_generation/draft_payload.py`; create persists via `PlanStorageService` when validation passes (`src/routes/plan_routes.py`).

## What this doc intentionally omits

Older alternate pipelines (orchestrators, coach passes, non-V2 create branches) are **not** documented here; they are not part of the supported plan-generation path above.

# Pre-generation runner review (v1)

## Purpose

Provide a **small, deterministic** snapshot (`pre_generation_runner_review`) plus an optional **system-section** block so the coach model can ground holistic “runner assessment” copy **before** final confirmation / plan generation—without inventing numbers or contradicting tool-derived facts.

## Inputs (v1)

The review is built **only** from:

1. The **`pre_generation_runner_assessment`** API dict (`assessment.as_api_dict()`), and
2. The validated **`plan_request`** from `build_plan_request_from_state(plan_intake_state)`.

No weekly insights, no scoring engine, no `run_v2` / planner inputs.

## Three statuses

Exactly one of:

| Status | Meaning (coarse) |
|--------|------------------|
| `needs_more_info` | Required alignment answers are still missing (`intake_alignment_state.unresolved_flags` while not `generation_ready`), **or** ambition reports `INSUFFICIENT_GOAL_CONTEXT`. |
| `needs_user_decision` | Tradeoff / thin-signal paths: e.g. **`activities_found == 0`** (always this status—not `needs_more_info`), goal–volume tension (`HIGH_TENSION` / `MANAGEABLE_TENSION`), `thin_baseline_data`, alignment not ready **without** unresolved flags, or (when alignment evaluation is off) **Target Time** with average weekly mileage under ~15 mi/wk in the lookback. |
| `ready_to_generate` | Else — coherent enough to proceed if the athlete confirms. |

## Feature flag

- **`SMARTCOACH_PRE_GENERATION_RUNNER_REVIEW_V1`** — default **on** (`1` if unset). Opt out with `0`, `false`, `no`, or `off`.

## Orchestrator behavior

When plan-creation uses the **minimal** system prompt and intake is **`ready_to_generate`**, the orchestrator may attach:

- Extra **system** markdown (`pre_generation_runner_review_system_section`) after the activity context block, and
- **`data.pre_generation_runner_review`** on structured `text` responses alongside `plan_intake_state`.

If building the bundle fails, the turn continues with a **warning** log (no user-visible error).

## Explicit non-goals (v1)

- No hard gate on `generate_training_plan`.
- No persistence of the review in the database.
- No client-required UI (mobile may ignore `data.pre_generation_runner_review`; styling can bind later).

## v2 backlog (ideas)

- Optional athlete acknowledgement before generate.
- Tool-level gate or stronger coupling to `generate_training_plan`.
- Cache / reuse assessment within the same turn to avoid duplicate work.

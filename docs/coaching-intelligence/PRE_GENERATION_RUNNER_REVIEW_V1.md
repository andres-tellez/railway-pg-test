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
| `needs_user_decision` | Tradeoff / thin-signal paths: e.g. **`activities_found == 0`** (always this status—not `needs_more_info`), goal–volume tension (`HIGH_TENSION` / `MANAGEABLE_TENSION`), `thin_baseline_data`, alignment not ready **without** unresolved flags, (when alignment evaluation is off) **Target Time** with low average weekly mileage, **and** minimal **goal-realism** rules: sub‑3 marathon (clock target **≤ 3:00:00**, including exactly **3:00:00**) with **≤3** or **4** non‑established training days, marathon **Target Time** with **THIN** baseline, short timeline to race, etc. (see `classify_assessment_status_v1` in `pre_generation_runner_review.py`). |
| `ready_to_generate` | Else — coherent enough to proceed the **review narrative** (not the same as `plan_intake_state.ready_to_generate`). |

## Split confirmation (plan creation)

**`SMARTCOACH_PLAN_CREATION_SPLIT_CONFIRM_V1`** (default **on**): separates **intake recap confirm**, **runner assessment** (this review), and **explicit plan build** (`plan_intake_state.ux`: `intake_confirmed`, `runner_review_delivered`, `plan_generation_confirmed`). `generate_training_plan` is rejected until all three are satisfied. Generic **yes** after intake recap does **not** set plan-generation consent; use **Create my plan** / **create my plan** / **build my plan** / **generate the plan**.

Material edits to **race_distance**, **race_date**, **primary_goal**, **target_time**, **training_days**, or **long_run_day** clear the three flags.

### Tradeoff chips (`needs_user_decision`)

When **`assessment_status`** is **`needs_user_decision`**, the API stamps **`ux.runner_tradeoff_pending`** until the athlete picks an option. Inline **`ui_prompt`** shows four chips (`runner_tradeoff_choice`): **Add another training day**, **Adjust my marathon goal**, **Move my goal race farther out**, **Keep the current goal and schedule**. **Create my plan** stays hidden until **`runner_tradeoff_pending`** is cleared (last option or material edits that reset UX). **`runner_tradeoff_resolved`** is set when the user picks **Keep the current goal and schedule** (or another branch) so a later review snapshot that still classifies as high-friction does not loop chips forever.

**Add another training day:** choosing that chip sets **`runner_tradeoff_pending`** false, **`runner_tradeoff_resolved`** true, and **`ux.runner_add_day_pick_pending`** + **`expansion_base_training_days`** so the next **`ui_prompt`** is single-select weekdays not already in the base list (`field_key`: **`plan_intake.collect_additional_training_day`**), not the four-way prompt again.

## Feature flag (runner review payload)

- **`SMARTCOACH_PRE_GENERATION_RUNNER_REVIEW_V1`** — default **on** (`1` if unset). Opt out with `0`, `false`, `no`, or `off`.

## Orchestrator behavior

When plan-creation uses the **minimal** system prompt, intake is **`ready_to_generate`**, and (with split confirm on) **`ux.intake_confirmed`**, the orchestrator may attach:

- Extra **system** markdown (`pre_generation_runner_review_system_section`) after the activity context block, and
- **`data.pre_generation_runner_review`** on structured `text` responses alongside `plan_intake_state`.

If building the bundle fails, the turn continues with a **warning** log (no user-visible error).

## Explicit non-goals (v1)

- No duplicate ambition/alignment evaluators (review consumes their outputs).
- No persistence of the review in the database.
- No client-required UI (mobile may ignore `data.pre_generation_runner_review`; styling can bind later).

## v2 backlog (ideas)

- Optional athlete acknowledgement before generate.
- Tool-level gate or stronger coupling to `generate_training_plan`.
- Cache / reuse assessment within the same turn to avoid duplicate work.

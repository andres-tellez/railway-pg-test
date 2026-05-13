# Pre-generation runner review (v1)

## Purpose

Provide a **small, deterministic** snapshot (`pre_generation_runner_review`) plus an optional **system-section** block so the coach model can ground holistic “runner assessment” copy **before** final confirmation / plan generation—without inventing numbers or contradicting tool-derived facts.

## Inputs (v1)

The review is built **only** from:

1. The **`pre_generation_runner_assessment`** API dict (`assessment.as_api_dict()`), and
2. The validated **`plan_request`** from `build_plan_request_from_state(plan_intake_state)`.

No weekly insights, no scoring engine, no `run_v2` / planner inputs.

## Three statuses

Exactly one of (derived **only** from ``plan_generation_readiness.decision`` + ``readiness_level`` — see ``assessment_status_from_readiness``; no parallel classifiers):

| Status | Meaning (coarse) |
|--------|------------------|
| `ready_to_generate` | `decision == "allow"`. |
| `needs_more_info` | `decision == "defer"` and `readiness_level == "insufficient_data"` — missing required fields, alignment, and/or activity coverage (e.g. zero activities, unresolved alignment, incomplete goal context). |
| `needs_user_decision` | All other deferred/blocked readiness — tradeoffs, stretch goals, thin baseline vs aggressive target time, sub‑3 frequency rules, pace gaps, etc. Narrative branches on ``reason_codes`` inside ``_copy_lines_for_v1``, not on raw ambition ``stance``. |

## Split confirmation (plan creation)

**`SMARTCOACH_PLAN_CREATION_SPLIT_CONFIRM_V1`** (default **on**): separates **intake recap confirm**, **runner assessment** (this review), and **explicit plan build** (`plan_intake_state.ux`: `intake_confirmed`, `runner_review_delivered`, `plan_generation_confirmed`). `generate_training_plan` is rejected until all three are satisfied. Generic **yes** after intake recap does **not** set plan-generation consent; use **Create my plan** / **create my plan** / **build my plan** / **generate the plan**.

**Plan-creation phase:** when split confirm is on, **`ux.plan_creation_phase`** is the single source of truth for where the athlete is in the plan-creation UX (e.g. `awaiting_intake_confirmation`, `awaiting_tradeoff_choice`, `collecting_additional_training_day`, `awaiting_plan_generation_confirmation`). **`compute_plan_creation_ui`** is the only server entry that builds plan-creation structured chips (plus alignment pause chips, same precedence as before). **`runner_tradeoff_pending`** / **`runner_tradeoff_resolved`** are derived from phase for backward compatibility for one release.

Material edits to **race_distance**, **race_date**, **primary_goal**, **target_time**, **training_days**, or **long_run_day** clear the three flags (and phase is recomputed after `update_plan_intake_state`).

### Tradeoff chips (`needs_user_decision`)

When **`assessment_status`** is **`needs_user_decision`** and the phase is **`awaiting_tradeoff_choice`**, inline **`ui_prompt`** shows four chips (`runner_tradeoff_choice`): **Add another training day**, **Adjust my marathon goal**, **Move my goal race farther out**, **Keep the current goal and schedule**. **Create my plan** stays hidden until the phase advances (e.g. **keep goal and schedule** or completing a sub-flow). **`runner_tradeoff_resolved`** is still driven by tool updates (`runner_tradeoff_choice`) and kept in sync with phase so a later review snapshot that still classifies as high-friction does not loop chips forever.

**Add another training day:** choosing that chip moves phase to **`collecting_additional_training_day`** and sets **`ux.runner_add_day_pick_pending`** + **`expansion_base_training_days`** so the next **`ui_prompt`** is single-select weekdays not already in the base list (`field_key`: **`plan_intake.collect_additional_training_day`**), not the four-way prompt again.

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

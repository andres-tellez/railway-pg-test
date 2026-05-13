# Pre-generation runner review (v1)

## Purpose

Provide a **small, deterministic** snapshot (`pre_generation_runner_review`) plus an optional **system-section** block so the coach model can ground holistic “runner assessment” copy **before** final confirmation / plan generation—without inventing numbers or contradicting tool-derived facts.

## Inputs (v1)

The review is built **only** from:

1. The **`pre_generation_runner_assessment`** API dict (`assessment.as_api_dict()`), and
2. The validated **`plan_request`** from `build_plan_request_from_state(plan_intake_state)`.

No weekly insights, no scoring engine, no `run_v2` / planner inputs.

## Assessment statuses (v1)

Exactly one string is emitted as **`assessment_status`** (from ``assessment_status_from_readiness`` — **two values only** as of **Phase 6**):

| Status | When |
|--------|------|
| `ready_to_generate` | `plan_generation_readiness.decision == "allow"`. |
| `needs_user_decision` | Any non-allow decision (defer/block). This includes **insufficient-data** cases (`decision == "defer"` and `readiness_level == "insufficient_data"` — missing fields, alignment, activity coverage). Tell those apart from tradeoff-style defers using **`plan_generation_readiness`** (`readiness_level`, **`allowed_user_actions`**, **`suggestions`**), not a separate status. Legacy clients may still see the string **`needs_more_info`** in old persisted UX; new payloads do not emit it as `assessment_status`. |

Narrative inside **`_copy_lines_for_v1`** branches on **`readiness_is_insufficient_data`** vs other **`reason_codes`** for `needs_user_decision`, not on raw ambition **`stance`** alone.

## Split confirmation (plan creation)

**`SMARTCOACH_PLAN_CREATION_SPLIT_CONFIRM_V1`** (default **on**): separates **intake recap confirm**, **runner assessment** (this review), and **explicit plan build** (`plan_intake_state.ux`: `intake_confirmed`, `runner_review_delivered`, `plan_generation_confirmed`). `generate_training_plan` is rejected until all three are satisfied. Generic **yes** after intake recap does **not** set plan-generation consent; use **Create my plan** / **create my plan** / **build my plan** / **generate the plan**.

**Plan-creation phase:** when split confirm is on, **`ux.plan_creation_phase`** is the single source of truth for where the athlete is in the plan-creation UX (e.g. `awaiting_intake_confirmation`, `awaiting_tradeoff_choice`, `collecting_additional_training_day`, `awaiting_plan_generation_confirmation`). **`compute_plan_creation_ui`** is the only server entry that builds plan-creation structured chips (plus alignment pause chips, same precedence as before). **`runner_tradeoff_pending`** / **`runner_tradeoff_resolved`** are derived from phase for backward compatibility for one release.

Material edits to **race_distance**, **race_date**, **primary_goal**, **target_time**, **training_days**, or **long_run_day** clear the three flags (and phase is recomputed after `update_plan_intake_state`).

### Tradeoff chips (`needs_user_decision`)

When **`assessment_status`** is **`needs_user_decision`** and the phase is **`awaiting_tradeoff_choice`**, inline **`ui_prompt`** shows four chips (`runner_tradeoff_choice`): **Add another training day**, **Adjust my marathon goal**, **Move my goal race farther out**, **Keep the current goal and schedule**. **Create my plan** stays hidden until the phase advances (e.g. **keep goal and schedule** or completing a sub-flow). **`runner_tradeoff_resolved`** is still driven by tool updates (`runner_tradeoff_choice`) and kept in sync with phase so a later review snapshot that still classifies as high-friction does not loop chips forever.

**Add another training day:** choosing that chip moves phase to **`collecting_additional_training_day`** and sets **`ux.runner_add_day_pick_pending`** + **`expansion_base_training_days`** so the next **`ui_prompt`** is single-select weekdays not already in the base list (`field_key`: **`plan_intake.collect_additional_training_day`**), not the four-way prompt again.

## Feature flag (runner review payload)

- **`SMARTCOACH_PRE_GENERATION_RUNNER_REVIEW_V1`** — default **on** (`1` if unset). Opt out with `0`, `false`, `no`, or `off`.
- **`SMARTCOACH_RUNNER_REVIEW_REQUIRED_BEFORE_GENERATE`** — default **on**. When split-confirm is enabled, **off** restores the older rule: runner-review system/API waits for **`ready_to_generate`** even after **`intake_confirmed`**.

## Orchestrator behavior

When plan-creation uses the **minimal** system prompt, split confirm is on, and **`ux.intake_confirmed`** is true (and goal-adjustment chip focus is not active), the orchestrator may build the runner-review bundle **even if `ready_to_generate` is still false** — so the Runner Analysis card can render in more readiness states (**Phase 6**). With **`SMARTCOACH_RUNNER_REVIEW_REQUIRED_BEFORE_GENERATE=0`**, the bundle again requires **`ready_to_generate`** under split-confirm.

Without split confirm, the bundle still requires **`ready_to_generate`** as before.

When built, the turn may attach:

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

# Policy extensibility — adding a new evidence axis

This folder holds **threshold tables**, **demand scoring**, **deficit math**, and **suggestion copy** that feed deterministic readiness. The goal is to grow signals (e.g. HR drift, grade-adjusted pace, weekly variance, terrain) without rewriting the whole gate.

Below is the standard extension pattern. Names are illustrative; follow existing modules for exact types and naming.

## 1. Model the signal on `RunnerEvidence`

- Add fields to `RunnerEvidenceSummary` (or the dataclass backing `RunnerEvidence` in `src/coaching_intelligence/contracts/runner_evidence.py`).
- Populate them in `compute_plan_intake_activity_summary` / `build_runner_evidence` (`src/smartcoach_mobile_coach/plan_intake_activity_context.py`): one DB read path, same weekly window rules as today.
- Expose the numbers on the API-shaped `runner_evidence` dict used in assessments (see `to_api_dict()` patterns elsewhere).

## 2. Encode thresholds in `policy_table.py`

- Add versioned constants (bands, floors, “bad/warn” cutoffs) next to related marathon / volume rules.
- Keep policy numbers **here**, not scattered in readiness prose builders.

## 3. Derive a structured deficit in `policy/deficits.py`

- Extend `compute_deficits` (and the deficit result type) to turn the new evidence fields + goal context into a numeric or ordinal “gap” the UI can show.
- Reuse existing patterns: small functions, no DB, goal-aware branches only when necessary.

## 4. Map to reason codes and readiness behavior

- In `plan_generation_readiness.py`, add rule helpers that read the new deficit / evidence and attach **`reason_codes`**, **`limiting_factors`**, and **`required_changes`** consistent with existing enums in `readiness_constants.py`.
- If the user-visible card should mention the axis, thread copy through **`runner_analysis_display`** builders (`composers/display.py`) rather than inventing strings in multiple places.

## 5. Tests

- Add unit tests for the deficit math and any new table lookups.
- Add or extend matrix-style tests under `tests/coaching_intelligence/` so monotonicity and regressions stay pinned when the new axis moves.

## Examples of future axes

| Axis | Typical evidence source | Notes |
|------|-------------------------|-------|
| HR drift vs pace | Streams / per-run enrichment | Reliability gates matter; align with existing pace-reliability patterns. |
| Grade-adjusted pace | Elevation + pace models | Often paired with “performance alignment” categories. |
| Weekly variance | `weekly_mileage_history` | May tie to existing consistency rules before adding new surface area. |
| Terrain / surface mix | Activity tags or route meta | Often softer signal; keep thresholds conservative at first. |

Keeping new physics on **evidence → table → deficits → readiness reasons** preserves one forensic story: logs + `trace_id` + replay scripts can reproduce the same numbers end-to-end. The readiness gate’s in-process cache also partitions by **device anchor date** (`get_or_compute_readiness_gate(..., anchor_local_date=...)`) so calendar-week evidence does not collide across different local “today” values for the same user digest.

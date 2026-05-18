# Run Review Lab Foundation

This document defines the target architecture for run-question replies and the
deprecation direction for older run-response paths.

## Core pattern

Run-question turns should follow one shape:

1. Deterministic gather (`classifier`, `context_builder`, `coach_snapshot`, evidence).
2. LLM-facing compact serialization (`to_compact_dict(for_llm=True)`).
3. Single completion (no tools during generation).
4. Deterministic response envelope (`run_summary` data + telemetry traces).

This keeps data deterministic while allowing the LLM to perform narrative
reasoning and explanation.

## Deterministic vs LLM responsibilities

- Deterministic:
  - Run resolution and classifier scope
  - Facts/KPI collection, evidence pack and plan/phase context
  - Card payload shape and telemetry fields
  - Post-response validation
- LLM:
  - Interpretation and emphasis
  - Coaching phrasing and clarity
  - User-facing narrative ordering

## Lab scopes

Lab should support these scopes over time:

- `single_run`: opening "how was my run?" recap.
- `splits_only`: split-detail follow-ups.
- `follow_up`: same-run targeted follow-up questions.

## Deprecation trajectory

1. Keep Lab as default run path.
2. Keep legacy paths available only behind rollback gate.
3. Remove V2 routing/code once Lab parity is stable.
4. Remove run recap/split fastpath modules once Lab covers those turns.

## Rollback controls

- `SMARTCOACH_RUN_REVIEW_LAB_FORCE_OFF=1` disables Lab gate.
- `SMARTCOACH_RUN_REVIEW_LAB_SPLITS=0` disables Lab routing for `split_detail`
  dialogue intent when the run-review classifier declines the turn.
- `SMARTCOACH_RUN_REVIEW_LEGACY_PATHS=0` disables deprecated fallback paths.

## Lab splits routing

When `SMARTCOACH_RUN_REVIEW_LAB_SPLITS` is on (default), turns with dialogue
intent `split_detail` enter Lab even if the classifier says "not run review".
Lab uses scope `splits_only`, fetches splits via `context_builder`, and uses a
split-focused prompt appendix. Telemetry: `run_review_lab_gate.lab_route` is
`split_intent`, `classifier_splits`, or `classifier`.

from __future__ import annotations


def prompt(intake_state: dict) -> str:
    _ = intake_state
    return (
        "## Plan generation — AUTHORIZED\n"
        "- The athlete has completed intake confirmation, runner assessment, and explicit "
        "plan-build consent. You may call `generate_training_plan` with `confirm=true` "
        "when appropriate.\n"
    )

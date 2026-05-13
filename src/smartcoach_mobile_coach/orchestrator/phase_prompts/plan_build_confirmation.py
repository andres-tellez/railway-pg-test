from __future__ import annotations


def prompt(intake_state: dict) -> str:
    _ = intake_state
    return (
        "## Plan build confirmation\n"
        "- Ask the athlete to **explicitly authorize building the plan**: tap "
        "**Create my plan** or say exactly **create my plan**, **build my plan**, or "
        "**generate the plan**.\n"
        "- A generic **yes** is **not** sufficient. Do **not** call "
        "`generate_training_plan` until `plan_generation_confirmed` is true in "
        "`plan_intake_state.ux`.\n"
    )

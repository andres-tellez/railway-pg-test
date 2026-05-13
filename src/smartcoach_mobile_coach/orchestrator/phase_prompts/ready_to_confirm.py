from __future__ import annotations


def prompt(intake_state: dict) -> str:
    _ = intake_state
    return (
        "## Plan intake phase — READY_TO_CONFIRM\n"
        "- **All required fields are present** (see tool intake payload). Give a **short** recap "
        "(race, goal, schedule) and **one** yes/no asking whether to generate the plan.\n"
        "- Do **not** re-ask for fields already present in the draft / tool state.\n"
    )

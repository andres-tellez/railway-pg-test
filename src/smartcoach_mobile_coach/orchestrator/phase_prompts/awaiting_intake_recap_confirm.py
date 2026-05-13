from __future__ import annotations


def prompt(intake_state: dict) -> str:
    _ = intake_state
    return (
        "## Plan intake phase — AWAITING_INTAKE_RECAP_CONFIRM\n"
        "- **All required fields are present.** Give a **short** recap "
        "(race, goal, schedule) and ask whether **that summary is accurate**.\n"
        "- Do **not** ask to generate or create the plan yet; do **not** call "
        "`generate_training_plan`. Generic yes here confirms intake only.\n"
        "- Do **not** re-ask for fields already present in the draft / tool state.\n"
    )

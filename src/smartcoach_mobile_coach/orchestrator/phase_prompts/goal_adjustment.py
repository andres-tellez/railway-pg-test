from __future__ import annotations


def prompt(intake_state: dict) -> str:
    _ = intake_state
    return (
        "## Plan intake — adjusting goal or timeline\n"
        "- The athlete chose to adjust **goal** or **race date** from the pre-plan review. "
        "Help them update those fields via chat or structured controls.\n"
        "- Do **not** offer **Create my plan** until material intake is consistent again "
        "and the split-confirm flow catches up.\n"
    )

from __future__ import annotations


def prompt(intake_state: dict) -> str:
    draft0 = (
        intake_state.get("draft") if isinstance(intake_state.get("draft"), dict) else {}
    )
    tt0 = draft0.get("target_time") or "your marathon time"
    return (
        "## Adding a training day\n"
        "- The athlete chose **Add another training day**. Start with **one sentence**: "
        "an extra run day usually gives more room for weekly mileage and easier spacing of "
        f"quality work toward a goal like **{tt0}**.\n"
        "- They pick **one** weekday from the chips below—do **not** repeat the earlier "
        "four-option list.\n"
        "- Do **not** show **Create my plan** until `training_days` is saved again.\n"
    )

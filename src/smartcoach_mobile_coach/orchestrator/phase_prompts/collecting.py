from __future__ import annotations

from src.smartcoach_mobile_coach.plan_intake_flow import _human_missing_label


def prompt(intake_state: dict) -> str:
    missing_raw = intake_state.get("missing_required") or []
    missing = [m for m in missing_raw if isinstance(m, str)]
    labels = ", ".join(_human_missing_label(m) for m in missing) or "see tool payload"
    return (
        "## Plan intake phase — COLLECTING\n"
        f"- **Still missing (server order):** {labels}.\n"
        "- Ask **one** natural question for the **next** missing item only (do not bundle unrelated asks).\n"
        "- **Forbidden in this phase:** acting as if the plan is complete, full-plan “does everything look right?” "
        "style summaries, yes/no to **generate** the plan, or “ready to create your plan?” — those are only allowed "
        "after the tool shows `ready_to_generate=true`.\n"
        "- Do **not** ask for anything already in the draft / tool intake state below.\n"
    )

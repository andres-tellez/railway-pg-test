from __future__ import annotations


def prompt(intake_state: dict) -> str:
    _ = intake_state
    return (
        "## Goal / schedule — choose next step\n"
        "- Runner Analysis in the app is driven by **`runner_analysis_display`** inside "
        "`pre_generation_runner_review.plan_generation_readiness`. **`coach_analysis_for_llm`** may "
        "exist only in the **model system prompt** (not in client JSON). Treat the display payload as "
        "authoritative for what the athlete sees; do **not** contradict it or revive legacy "
        "`summary_lines` / `concerns` if they differ.\n"
        "- Brief prose optional only (warmth / clarity); chips carry the real choices.\n"
        "- They pick **inline chips** below or edit intake in chat. Do **not** show "
        "**Create my plan** until they choose an option (including **keep goal and schedule**) "
        "or change material schedule/goal/race date.\n"
        "- Do **not** call `generate_training_plan` until `ux.runner_tradeoff_resolved` "
        "is true or they change draft fields and complete the split-confirm flow again.\n"
    )

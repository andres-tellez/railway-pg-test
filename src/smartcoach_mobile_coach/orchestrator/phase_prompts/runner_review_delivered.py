from __future__ import annotations


def prompt(intake_state: dict) -> str:
    _ = intake_state
    return (
        "## Runner assessment phase (structured UI)\n"
        "- The app displays a **deterministic Runner Analysis card** from "
        "`plan_generation_readiness.runner_analysis_display` (user-facing facts, verdict, "
        "and actions). The server may also derive **`coach_analysis_for_llm`** for the **model "
        "system prompt** only; it is **not** included in the client JSON — treat the display "
        "payload as what the athlete sees.\n"
        "- Do **not** repeat the full analysis, numbers, schedule, or action list in prose.\n"
        "- Optional only: **at most two short sentences** of warmth or empathy — no new facts, "
        "metrics, categories, or recommendations beyond those payloads.\n"
        "- Do **not** call `generate_training_plan` in this phase.\n"
    )

"""Snapshot-style tests for plan intake phase prompt strings (Phase 7.3)."""

from __future__ import annotations

import pytest

from src.smartcoach_mobile_coach.orchestrator.phase_prompts import (
    add_day,
    authorized,
    awaiting_intake_recap_confirm,
    collecting,
    goal_adjustment,
    plan_build_confirmation,
    ready_to_confirm,
    runner_review_delivered,
    tradeoff,
)


@pytest.fixture
def representative_intake_state() -> dict:
    return {
        "ready_to_generate": False,
        "missing_required": ["race_date", "primary_goal"],
        "draft": {"race_distance": "Marathon", "target_time": "3:30:00"},
        "ux": {"plan_creation_phase": "collecting_race_date_v1"},
    }


def test_add_day_prompt_snapshot():
    assert add_day.prompt({"draft": {"target_time": "3:45:00"}}) == (
        "## Adding a training day\n"
        "- The athlete chose **Add another training day**. Start with **one sentence**: "
        "an extra run day usually gives more room for weekly mileage and easier spacing of "
        "quality work toward a goal like **3:45:00**.\n"
        "- They pick **one** weekday from the chips below—do **not** repeat the earlier "
        "four-option list.\n"
        "- Do **not** show **Create my plan** until `training_days` is saved again.\n"
    )


def test_awaiting_intake_recap_confirm_snapshot():
    assert awaiting_intake_recap_confirm.prompt({}) == (
        "## Plan intake phase — AWAITING_INTAKE_RECAP_CONFIRM\n"
        "- **All required fields are present.** Give a **short** recap "
        "(race, goal, schedule) and ask whether **that summary is accurate**.\n"
        "- Do **not** ask to generate or create the plan yet; do **not** call "
        "`generate_training_plan`. Generic yes here confirms intake only.\n"
        "- Do **not** re-ask for fields already present in the draft / tool state.\n"
    )


def test_runner_review_delivered_snapshot():
    assert runner_review_delivered.prompt({}) == (
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


def test_goal_adjustment_snapshot():
    assert goal_adjustment.prompt({}) == (
        "## Plan intake — adjusting goal or timeline\n"
        "- The athlete chose to adjust **goal** or **race date** from the pre-plan review. "
        "Help them update those fields via chat or structured controls.\n"
        "- Do **not** offer **Create my plan** until material intake is consistent again "
        "and the split-confirm flow catches up.\n"
    )


def test_tradeoff_snapshot():
    assert tradeoff.prompt({}) == (
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


def test_plan_build_confirmation_snapshot():
    assert plan_build_confirmation.prompt({}) == (
        "## Plan build confirmation\n"
        "- Ask the athlete to **explicitly authorize building the plan**: tap "
        "**Create my plan** or say exactly **create my plan**, **build my plan**, or "
        "**generate the plan**.\n"
        "- A generic **yes** is **not** sufficient. Do **not** call "
        "`generate_training_plan` until `plan_generation_confirmed` is true in "
        "`plan_intake_state.ux`.\n"
    )


def test_authorized_snapshot():
    assert authorized.prompt({}) == (
        "## Plan generation — AUTHORIZED\n"
        "- The athlete has completed intake confirmation, runner assessment, and explicit "
        "plan-build consent. You may call `generate_training_plan` with `confirm=true` "
        "when appropriate.\n"
    )


def test_ready_to_confirm_snapshot():
    assert ready_to_confirm.prompt({}) == (
        "## Plan intake phase — READY_TO_CONFIRM\n"
        "- **All required fields are present** (see tool intake payload). Give a **short** recap "
        "(race, goal, schedule) and **one** yes/no asking whether to generate the plan.\n"
        "- Do **not** re-ask for fields already present in the draft / tool state.\n"
    )


def test_collecting_snapshot(representative_intake_state):
    out = collecting.prompt(representative_intake_state)
    assert out == (
        "## Plan intake phase — COLLECTING\n"
        "- **Still missing (server order):** race date, goal type.\n"
        "- Ask **one** natural question for the **next** missing item only (do not bundle unrelated asks).\n"
        "- **Forbidden in this phase:** acting as if the plan is complete, full-plan “does everything look right?” "
        "style summaries, yes/no to **generate** the plan, or “ready to create your plan?” — those are only allowed "
        "after the tool shows `ready_to_generate=true`.\n"
        "- Do **not** ask for anything already in the draft / tool intake state below.\n"
    )

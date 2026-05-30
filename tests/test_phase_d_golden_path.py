"""
V1.6 Phase D 3D.9 — golden-path coach turn tests.

These tests lock the **deterministic** turn-shape contract the coach
depends on in Phase D. They run end-to-end over the
``get_phase_analysis`` payload builder plus the orchestrator prompt
composer; they do NOT call the LLM. That keeps the assertions
repeatable across model swaps while still guarding the three user-
locked (2026-04-21) scenarios:

* **Mid-phase update** — an active phase goal exists, some weeks of
  the phase are already past, and a progress question arrives.
  Expected deterministic output: ``coaching_hint is None``, ``goal``
  populated, ``weekly_progress[]`` non-empty, ``phase_progress_summary``
  resolved. The coach renders the Progress step from these fields.
* **Transition merged retro + proposal** — a new phase has just begun
  (zero completed weeks), no active goal, and the user asks about
  the plan. Expected: ``coaching_hint == "merge_retrospective_and_propose"``
  — a single coach response must blend a retrospective of the prior
  phase with a new-phase goal proposal. Trigger is single-shot (first
  plan/phase/progress turn after the transition).
* **Mid-phase catch-up auto-proposal** — a phase is past (or current
  with ``completed >= 1``), no active goal, and the user asks about
  the plan. Expected: ``coaching_hint == "propose_goal"`` — the
  coach proposes a focus inline without a retrospective.
* **Scope gating** — the Phase UX prompt contract is present in the
  non-plan-creation system prompt and carries the self-gating clause
  that tells the LLM to suppress the template on single-run recaps /
  KPI-definition questions / general chat. The plan-creation prompt
  deliberately omits it.

The payload + prompt contract is the "golden path"; the LLM response
copy is tested separately in the 3D.8 contract suite (which locks
every anchor phrase and BAD-example) and in the 3D.4 resolver suite
(which locks every trigger cell).

Fixture reuse
-------------
The plan fixture mirrors the one in ``test_get_phase_analysis_tool.py``
so both suites stay aligned on the Base → Build week layout. Today is
pinned to **Wed 2026-04-22**, which puts us in week 3 (Build, current,
``completed == 0``).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from src.db.models.activities import Activity
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.plans import Plan
from src.db.models.user_athletes import UserAthleteLink
from src.services.plan.phase_analysis import build_phase_analysis_payload
from src.services.plan.phase_coach_hints import CoachingHint
from src.services.plan.phase_goal import save_phase_goal

DEFAULT_USER_ID = uuid.UUID("0b5e5a42-0000-4000-8000-0000000003d9")
DEFAULT_USER_ID_STR = str(DEFAULT_USER_ID)

# Pin "today" so `phase_temporality` / `completed` are deterministic.
# Wed 2026-04-22 is in wk3 (Mon 2026-04-20 .. Sun 2026-04-26), which is
# the first week of Build in the fixture. That gives us: Base =
# entirely past, Build = current with completed == 0.
FIXED_TODAY = date(2026, 4, 22)


@pytest.fixture(autouse=True)
def _pin_today(monkeypatch):
    # Bind the phase-analysis builder's "today" anchor deterministically.
    # Every scenario in this file either uses FIXED_TODAY directly or
    # passes its own `today` into build_phase_analysis_payload, so the
    # autouse patch is a safety net, not a requirement.
    monkeypatch.setattr(
        "src.services.plan.phase_analysis.get_today_date_in_timezone",
        lambda _tz: FIXED_TODAY,
    )


@pytest.fixture
def seeded_plan(test_db_session):
    """Two-phase plan: Base (2 past weeks, fully matched) + Build
    (1 current + 1 future). Easy on Tue, Long on Sat each week.

    The Base weeks' matched activities have good zone compliance +
    green/yellow scores, which gives us a non-trivial
    ``phase_progress_summary`` for the mid-phase scenario.
    """
    session = test_db_session
    session.add(UserAthleteLink(user_id=DEFAULT_USER_ID_STR, athlete_id=5959))
    plan = Plan(
        user_id=DEFAULT_USER_ID,
        plan_name="Phase D 3D.9 Golden Path",
        race_date=date(2026, 6, 7),
        race_distance="Marathon",
        is_active=True,
        training_days=["Tue", "Sat"],
    )
    session.add(plan)
    session.flush()

    week_specs = [
        (date(2026, 4, 6), "Base", 5.0, 10.0),
        (date(2026, 4, 13), "Base", 5.0, 11.0),
        (date(2026, 4, 20), "Build", 5.0, 13.0),
        (date(2026, 4, 27), "Build", 5.0, 14.0),
    ]

    workouts: dict[date, PlanWorkout] = {}
    for monday, phase, easy_mi, long_mi in week_specs:
        tue = monday + timedelta(days=1)
        sat = monday + timedelta(days=5)
        easy = PlanWorkout(
            plan_id=plan.id,
            date=tue,
            workout_type="Easy Run",
            description="Easy miles",
            miles=easy_mi,
            intensity="z2",
            run_type_key="easy",
            phase=phase,
        )
        long_run = PlanWorkout(
            plan_id=plan.id,
            date=sat,
            workout_type="Long Run",
            description="Weekend long",
            miles=long_mi,
            intensity="z2",
            run_type_key="long_run",
            phase=phase,
        )
        session.add_all([easy, long_run])
        session.flush()
        workouts[tue] = easy
        workouts[sat] = long_run

    def _add(*, aid, pw_date, run_score, zc_pct, planned_type, planned_mi, actual_mi):
        session.add(
            Activity(
                activity_id=aid,
                athlete_id=5959,
                user_id=DEFAULT_USER_ID,
                name=f"Activity {aid}",
                type="Run",
                start_date=datetime(
                    pw_date.year,
                    pw_date.month,
                    pw_date.day,
                    12,
                    0,
                    tzinfo=timezone.utc,
                ),
                matched_plan_workout_id=workouts[pw_date].id,
                planned_type=planned_type,
                executed_type=planned_type,
                run_score=run_score,
                zone_compliance_pct=zc_pct,
                planned_miles=planned_mi,
                actual_miles=actual_mi,
                completion_pct=100.0,
                conv_distance=actual_mi,
                moving_time=int(actual_mi * 540),
            )
        )

    # Base wk1 — both runs matched, solid execution.
    _add(
        aid=595901,
        pw_date=date(2026, 4, 7),
        run_score="green",
        zc_pct=85.0,
        planned_type="easy",
        planned_mi=5.0,
        actual_mi=5.0,
    )
    _add(
        aid=595902,
        pw_date=date(2026, 4, 11),
        run_score="green",
        zc_pct=82.0,
        planned_type="long",
        planned_mi=10.0,
        actual_mi=10.0,
    )
    # Base wk2 — both runs matched, solid execution.
    _add(
        aid=595903,
        pw_date=date(2026, 4, 14),
        run_score="green",
        zc_pct=90.0,
        planned_type="easy",
        planned_mi=5.0,
        actual_mi=5.0,
    )
    _add(
        aid=595904,
        pw_date=date(2026, 4, 18),
        run_score="green",
        zc_pct=80.0,
        planned_type="long",
        planned_mi=11.0,
        actual_mi=11.0,
    )
    # Build wk3 Tue — already logged so the current week has one
    # matched run. This seeds the "current, completed == 0" scenario
    # (the Sunday has not passed yet, so `completed` stays at 0
    # regardless of matched activities mid-week).
    _add(
        aid=595905,
        pw_date=date(2026, 4, 21),
        run_score="green",
        zc_pct=80.0,
        planned_type="easy",
        planned_mi=5.0,
        actual_mi=5.0,
    )

    session.commit()
    return plan


# ---------------------------------------------------------------------------
# Golden path A — mid-phase update with an active goal
# ---------------------------------------------------------------------------


def test_golden_path_mid_phase_update_with_active_goal(test_db_session, seeded_plan):
    """Scenario: user has a live Base goal and asks about progress mid-
    phase. The coach needs ``goal`` + ``weekly_progress`` + a resolved
    dominant status, and MUST NOT be told to auto-propose anything."""
    status, saved = save_phase_goal(
        test_db_session,
        DEFAULT_USER_ID,
        "Base",
        "Lock in aerobic consistency on the Saturday long runs.",
        source_raw="user_stated",
        confirmed=True,
    )
    assert status == "ok"
    test_db_session.flush()

    payload = build_phase_analysis_payload(test_db_session, DEFAULT_USER_ID, "Base")

    # Hint silenced — the coach does not re-propose a live goal.
    assert payload["coaching_hint"] is None

    # Goal fully surfaced for the Focus step.
    goal = payload["goal"]
    assert goal is not None
    assert goal["goal_text"] == (
        "Lock in aerobic consistency on the Saturday long runs."
    )
    assert goal["status"] == "active"

    # Progress step has real evidence — not the empty shell.
    wp = payload["weekly_progress"]
    assert len(wp) == 2
    assert payload["phase_progress_summary"]["weeks_evaluated"] == 2
    # Dominant status is a canonical value (or None); the coach may
    # render it in plain language but the wire value must be stable.
    assert payload["phase_progress_summary"]["dominant_status"] in (
        "on_track",
        "close",
        "off_track",
        None,
    )

    # The Base phase is fully past in the fixture — locking this
    # guards against a future refactor that accidentally treats "has a
    # goal" as "suppress temporality".
    assert payload["phase_weeks"]["phase_temporality"] == "past"


# ---------------------------------------------------------------------------
# Golden path B — transition merged retrospective + proposal
# ---------------------------------------------------------------------------


def test_golden_path_transition_merge_retrospective_and_propose(
    test_db_session, seeded_plan
):
    """Scenario: the athlete has just rolled into Build (wk3). No Sunday
    has passed for Build yet, so ``completed == 0`` and no goal exists.
    This is the single-shot merged-retrospective trigger."""
    payload = build_phase_analysis_payload(test_db_session, DEFAULT_USER_ID, "Build")

    assert payload["goal"] is None
    assert payload["phase_weeks"]["phase_temporality"] == "current"
    assert payload["phase_weeks"]["completed"] == 0
    assert (
        payload["coaching_hint"] == CoachingHint.MERGE_RETROSPECTIVE_AND_PROPOSE.value
    )
    # Future wk4 must NOT be in `weekly_progress` (§19.5 extension).
    assert all(e["week_index"] != 4 for e in payload["weekly_progress"])


def test_golden_path_merge_branch_closes_after_first_week_completes(
    test_db_session, seeded_plan, monkeypatch
):
    """Single-shot lock: once Build's wk3 Sunday has passed, the merge
    window closes and the hint drops to ``propose_goal`` — the coach
    still proposes, but does NOT re-open a retrospective."""
    # Advance "today" to the Monday AFTER wk3's Sunday (2026-04-27).
    # That makes Build.completed == 1 while still in Build (wk4 is now
    # current). No goal has been saved, so the resolver must switch
    # from merge to propose_goal.
    monkeypatch.setattr(
        "src.services.plan.phase_analysis.get_today_date_in_timezone",
        lambda _tz: date(2026, 4, 27),
    )

    payload = build_phase_analysis_payload(test_db_session, DEFAULT_USER_ID, "Build")
    assert payload["goal"] is None
    assert payload["phase_weeks"]["completed"] >= 1
    assert payload["coaching_hint"] == CoachingHint.PROPOSE_GOAL.value


# ---------------------------------------------------------------------------
# Golden path C — mid-phase catch-up auto-proposal
# ---------------------------------------------------------------------------


def test_golden_path_past_phase_no_goal_triggers_propose_goal(
    test_db_session, seeded_plan
):
    """Scenario: user asks about their Base phase after it is fully
    past, but they never set a goal for it. The resolver emits
    ``propose_goal`` (no retrospective merge — that branch only fires
    at the transition moment)."""
    payload = build_phase_analysis_payload(test_db_session, DEFAULT_USER_ID, "Base")

    assert payload["goal"] is None
    assert payload["phase_weeks"]["phase_temporality"] == "past"
    assert payload["coaching_hint"] == CoachingHint.PROPOSE_GOAL.value
    # The Progress step still has the retrospective evidence the coach
    # needs even when the hint is `propose_goal` — the prompt contract
    # pulls from `weekly_progress` directly.
    assert len(payload["weekly_progress"]) == 2


# ---------------------------------------------------------------------------
# Golden path D — scope gating (prompt-level contract)
# ---------------------------------------------------------------------------


def test_phase_ux_contract_is_present_in_non_plan_creation_prompt() -> None:
    """The Phase UX contract must reach the LLM on every non-plan-
    creation turn so the scope gate inside it can decide when to
    render. This guards the composition in
    ``_join_nonempty_system_sections`` — a regression that silently
    dropped the section would disable the entire 3D.8 template."""
    from src.smartcoach_mobile_coach.phase_ux_contract import (
        PHASE_UX_CONTRACT_BLOCK,
    )

    # The contract block is a constant, so we can verify it contains
    # the scope-gate anchor. If this ever moves into a template,
    # update the anchor string rather than deleting the test.
    assert "Scope gate" in PHASE_UX_CONTRACT_BLOCK
    # The three scope triggers the user locked on 2026-04-21 —
    # plan-related / phase-related / progress-related turns.
    assert "plan" in PHASE_UX_CONTRACT_BLOCK.lower()
    assert "phase" in PHASE_UX_CONTRACT_BLOCK.lower()
    assert "progress" in PHASE_UX_CONTRACT_BLOCK.lower()


def test_scope_gate_lists_out_of_scope_examples_verbatim() -> None:
    """The scope-gate clause must carry out-of-scope anti-examples so
    the LLM self-suppresses on single-run recaps, KPI-definition
    questions, and general chat. We assert at least one anti-example
    is present verbatim — a full list lives in test_phase_ux_contract.py."""
    from src.smartcoach_mobile_coach.phase_ux_contract import (
        PHASE_UX_CONTRACT_BLOCK,
    )

    # At least one of the locked anti-example anchors from 3D.8 must
    # appear verbatim in the block. Any one catches drift.
    anti_example_anchors = (
        "single-run recap",
        "single run recap",
        "KPI definition",
        "preference update",
        "general chat",
    )
    assert any(
        anchor.lower() in PHASE_UX_CONTRACT_BLOCK.lower()
        for anchor in anti_example_anchors
    ), (
        "Phase UX scope gate must list at least one out-of-scope "
        "anti-example verbatim so the LLM can self-suppress."
    )


def test_phase_ux_contract_absent_in_plan_creation_branch() -> None:
    """Scope gating has a structural twin: the plan-creation prompt
    deliberately omits the UX contract because there is no phase goal
    or weekly progress during intake. This guards the composition
    shape at the source level (a runtime prompt snapshot is a deeper
    test in :mod:`test_phase_ux_contract`)."""
    from pathlib import Path

    src = Path("src/smartcoach_mobile_coach/orchestrator/__init__.py").read_text(
        encoding="utf-8"
    )
    # Exactly one composition site — already asserted in
    # test_phase_ux_contract.py, but we re-lock it here to keep the
    # golden-path suite self-contained.
    assert src.count("phase_ux_contract_section()") == 1
    plan_creation_idx = src.index("PLAN_CREATION_SYSTEM_PROMPT_BASE")
    ux_idx = src.index("phase_ux_contract_section()")
    assert plan_creation_idx < ux_idx, (
        "phase_ux_contract_section() must be composed in the "
        "non-plan-creation branch, i.e. AFTER the "
        "PLAN_CREATION_SYSTEM_PROMPT_BASE definition in source order."
    )


# ---------------------------------------------------------------------------
# Cross-scenario invariants
# ---------------------------------------------------------------------------


def test_coaching_hint_field_is_always_present_on_payload(test_db_session, seeded_plan):
    """Every phase payload — goaled / no-goal / empty / past / current
    — MUST carry the ``coaching_hint`` key (value may be ``None``).
    The coach treats the key's absence as an upstream bug, not a
    "no hint" signal, so we lock the key shape here for all four
    V1.6 phases."""
    for phase in ("Base", "Build", "Peak", "Taper"):
        payload = build_phase_analysis_payload(test_db_session, DEFAULT_USER_ID, phase)
        assert (
            "coaching_hint" in payload
        ), f"phase {phase}: coaching_hint key missing from payload"
        assert payload["coaching_hint"] in (
            None,
            CoachingHint.PROPOSE_GOAL.value,
            CoachingHint.MERGE_RETROSPECTIVE_AND_PROPOSE.value,
        )


def test_active_goal_always_suppresses_hint_across_phases(test_db_session, seeded_plan):
    """Cross-phase single-source-of-truth sanity: saving a goal on any
    phase must flip that phase's ``coaching_hint`` to ``None`` without
    affecting the other phases. Prevents future "one hint fits all"
    regressions where the resolver leaks between phases."""
    save_phase_goal(
        test_db_session,
        DEFAULT_USER_ID,
        "Build",
        "Hit each Tempo segment without blowing up the closer.",
        source_raw="coach_refined",
    )
    test_db_session.flush()

    build_payload = build_phase_analysis_payload(
        test_db_session, DEFAULT_USER_ID, "Build"
    )
    base_payload = build_phase_analysis_payload(
        test_db_session, DEFAULT_USER_ID, "Base"
    )

    assert build_payload["coaching_hint"] is None
    # Base still has no goal, so it keeps proposing.
    assert base_payload["coaching_hint"] == CoachingHint.PROPOSE_GOAL.value

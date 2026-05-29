"""Plan profile HR beat during plan creation (ux flags, not REQUIRED_FIELDS)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.smartcoach_mobile_coach.hr_calibration_intake import (
    HR_CALIBRATION_STEP_BIRTH_YEAR,
    HR_CALIBRATION_STEP_MAX_HR,
    build_plan_profile_hr_beat_ui_prompt,
    ensure_user_profile_row,
    plan_profile_hr_beat_ui_active,
    sync_plan_profile_hr_beat_ux,
)
from src.smartcoach_mobile_coach.plan_creation_ui import compute_plan_creation_ui
from src.smartcoach_mobile_coach.plan_intake_flow import REQUIRED_FIELDS
from src.smartcoach_mobile_coach.profile_structured_patch import (
    maybe_apply_patch_user_profile_birth_year,
)


def _ready_intake(**ux_overrides):
    ux = {"intake_confirmed": True}
    ux.update(ux_overrides)
    return {
        "status": "ready",
        "ready_to_generate": True,
        "missing_required": [],
        "draft": {
            "race_distance": "Marathon",
            "race_date": "2026-10-11",
            "primary_goal": "Target Time",
            "target_time": "3:30:00",
            "training_days": ["Mon", "Wed", "Fri", "Sun"],
        },
        "ux": ux,
    }


@patch("src.smartcoach_mobile_coach.hr_calibration_intake.get_user_profile")
def test_ready_to_generate_unchanged_when_hr_pending(mock_profile):
    mock_profile.return_value = {}
    state = _ready_intake()
    out = sync_plan_profile_hr_beat_ux(MagicMock(), "user-1", state)
    assert out["ready_to_generate"] is True
    assert out["missing_required"] == []
    assert out["ux"]["hr_calibration_step"] == HR_CALIBRATION_STEP_BIRTH_YEAR
    assert out["ux"].get("hr_calibration_intake_done") is not True


@patch("src.smartcoach_mobile_coach.hr_calibration_intake.get_user_profile")
def test_birth_year_then_max_hr_step(mock_profile):
    mock_profile.return_value = {"birth_year": 1990}
    state = _ready_intake()
    out = sync_plan_profile_hr_beat_ux(MagicMock(), "user-1", state)
    assert out["ux"]["hr_calibration_step"] == HR_CALIBRATION_STEP_MAX_HR
    assert plan_profile_hr_beat_ui_active(out) is True


@patch("src.smartcoach_mobile_coach.hr_calibration_intake.get_user_profile")
def test_skip_max_hr_with_birth_year_uses_age_estimate(mock_profile):
    mock_profile.return_value = {"birth_year": 1990}
    state = _ready_intake(hr_calibration_max_hr_skipped=True)
    out = sync_plan_profile_hr_beat_ux(MagicMock(), "user-1", state)
    assert out["ux"]["hr_calibration_intake_done"] is True
    assert "hr_calibration_step" not in out["ux"]
    assert plan_profile_hr_beat_ui_active(out) is False


@patch("src.smartcoach_mobile_coach.hr_calibration_intake.get_user_profile")
def test_both_skipped_advances_beat(mock_profile):
    mock_profile.return_value = {}
    state = _ready_intake(
        hr_calibration_birth_year_skipped=True,
        hr_calibration_max_hr_skipped=True,
    )
    out = sync_plan_profile_hr_beat_ux(MagicMock(), "user-1", state)
    assert out["ux"]["hr_calibration_intake_done"] is True


@patch("src.smartcoach_mobile_coach.hr_calibration_intake.get_user_profile")
def test_manual_max_hr_completes_beat(mock_profile):
    mock_profile.return_value = {"birth_year": 1990, "max_hr_manual": 185}
    state = _ready_intake()
    out = sync_plan_profile_hr_beat_ux(MagicMock(), "user-1", state)
    assert out["ux"]["hr_calibration_intake_done"] is True


def test_required_fields_exclude_hr():
    assert "birth_year" not in REQUIRED_FIELDS
    assert "max_hr" not in REQUIRED_FIELDS
    assert "max_hr_manual" not in REQUIRED_FIELDS


@patch("src.smartcoach_mobile_coach.hr_calibration_intake.get_user_profile")
def test_ui_prompt_order_birth_year_before_max_hr(mock_profile):
    mock_profile.return_value = {}
    state = sync_plan_profile_hr_beat_ux(MagicMock(), "user-1", _ready_intake())
    ui = build_plan_profile_hr_beat_ui_prompt(state)
    assert ui is not None
    assert ui["control_type"] == "year_select"

    mock_profile.return_value = {"birth_year": 1985}
    state = sync_plan_profile_hr_beat_ux(MagicMock(), "user-1", state)
    ui = build_plan_profile_hr_beat_ui_prompt(state)
    assert ui is not None
    assert ui["control_type"] == "optional_bpm"
    assert "don't guess" in ui["prompt"].lower()


@patch("src.smartcoach_mobile_coach.hr_calibration_intake.get_user_profile")
def test_compute_plan_creation_ui_syncs_when_session_provided(mock_profile):
    mock_profile.return_value = {}
    state = _ready_intake(schedule_confirm_before_posture=True)
    session = MagicMock()
    ui = compute_plan_creation_ui(state, session=session, user_id="user-1")
    assert ui is not None
    assert ui["control_type"] == "year_select"
    mock_profile.assert_called()


@patch("src.smartcoach_mobile_coach.hr_calibration_intake.get_user_profile")
def test_birth_year_prompt_includes_skip_option(mock_profile):
    mock_profile.return_value = {}
    state = sync_plan_profile_hr_beat_ux(MagicMock(), "user-1", _ready_intake())
    ui = build_plan_profile_hr_beat_ui_prompt(state)
    assert ui is not None
    skip_ids = [o["id"] for o in ui.get("options") or []]
    assert "birth_year_skip" in skip_ids


@patch("src.smartcoach_mobile_coach.hr_calibration_intake.save_user_profile")
@patch("src.smartcoach_mobile_coach.hr_calibration_intake.get_user_profile")
def test_ensure_user_profile_row_bootstraps_minimal_profile(mock_get, mock_save):
    mock_get.side_effect = [None, {"user_id": "u1", "age_group": "30-39"}]
    session = MagicMock()
    out = ensure_user_profile_row(session, "u1")
    assert out["user_id"] == "u1"
    mock_save.assert_called_once()
    saved = mock_save.call_args[0][1]
    assert saved["height_feet"] == 5
    assert saved["height_inches"] == 10


@patch(
    "src.smartcoach_mobile_coach.profile_structured_patch.ensure_user_profile_row",
    return_value={"user_id": "u1", "age_group": "30-39"},
)
@patch("src.smartcoach_mobile_coach.profile_structured_patch.save_user_profile")
def test_patch_birth_year_without_prior_onboarding_row(mock_save, _mock_ensure):
    session = MagicMock()
    conversation = MagicMock()
    conversation.id = "conv-1"
    result = maybe_apply_patch_user_profile_birth_year(
        session,
        internal_user_id="u1",
        birth_year=1988,
        conversation=conversation,
        message_body="My birth year is 1988.",
        prior_messages_count=1,
    )
    assert hasattr(result, "assistant_payload")
    mock_save.assert_called_once()
    merged = mock_save.call_args[0][1]
    assert merged["birth_year"] == 1988

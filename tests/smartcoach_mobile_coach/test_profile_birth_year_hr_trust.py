"""Birth year patch must not create a zone-trusted max HR."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.services.heart_rate.hrmax_resolution_service import HRMaxResolutionService
from src.smartcoach_mobile_coach.profile_structured_patch import (
    PatchBirthYearApplied,
    maybe_apply_patch_user_profile_birth_year,
)


@patch("src.smartcoach_mobile_coach.profile_structured_patch.ensure_user_profile_row")
@patch("src.smartcoach_mobile_coach.profile_structured_patch.save_user_profile")
def test_birth_year_patch_does_not_set_trusted_max_hr(mock_save, mock_ensure):
    mock_ensure.return_value = {"user_id": "user-1"}
    mock_save.side_effect = lambda _session, merged: None

    conversation = MagicMock()
    conversation.id = 1
    conversation.title = None

    result = maybe_apply_patch_user_profile_birth_year(
        MagicMock(),
        internal_user_id="user-1",
        birth_year=1976,
        conversation=conversation,
        message_body="1976",
        prior_messages_count=0,
    )

    assert isinstance(result, PatchBirthYearApplied)
    saved = mock_save.call_args[0][1]
    assert saved["birth_year"] == 1976
    assert saved.get("max_hr_manual") is None
    assert saved.get("max_hr_auto") is None
    assert HRMaxResolutionService.get_trusted_max_hr_for_zones(saved) is None

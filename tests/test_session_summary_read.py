"""Coverage for retained session-summary history helper."""

from __future__ import annotations

from src.smartcoach_mobile_coach.memory.session_summary_read import (
    has_prior_assistant_message,
)


def test_prior_assistant_detector_false_on_empty_history() -> None:
    assert has_prior_assistant_message([]) is False


def test_prior_assistant_detector_false_when_only_user_messages() -> None:
    history = [{"role": "user", "content": "hi"}]
    assert has_prior_assistant_message(history) is False


def test_prior_assistant_detector_true_when_any_assistant_message_exists() -> None:
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "Hey, let's dig in."},
    ]
    assert has_prior_assistant_message(history) is True


def test_prior_assistant_detector_ignores_blank_assistant_content() -> None:
    history = [
        {"role": "assistant", "content": ""},
        {"role": "assistant", "content": "   "},
    ]
    assert has_prior_assistant_message(history) is False


def test_prior_assistant_detector_handles_malformed_input_defensively() -> None:
    assert has_prior_assistant_message(None) is False
    assert has_prior_assistant_message("not a list") is False
    assert has_prior_assistant_message([None, 42, "str"]) is False

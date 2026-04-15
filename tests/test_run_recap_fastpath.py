"""Tests for opening run-recap fast path eligibility."""

from __future__ import annotations

from src.smartcoach_mobile_coach.run_recap_fastpath import wants_run_recap_fastpath


def test_wants_fastpath_how_was_my_run_opening():
    assert wants_run_recap_fastpath("How was my run?", [])


def test_wants_fastpath_how_did_today_go():
    assert wants_run_recap_fastpath("How did today go?", [])


def test_rejects_last_run():
    assert not wants_run_recap_fastpath("How was my last run?", [])


def test_rejects_with_prior_assistant():
    hist = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hey — how can I help?"},
    ]
    assert not wants_run_recap_fastpath("How was my run?", hist)


def test_disabled_env(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_RUN_RECAP_FASTPATH", "0")
    try:
        assert not wants_run_recap_fastpath("How was my run?", [])
    finally:
        monkeypatch.delenv("SMARTCOACH_RUN_RECAP_FASTPATH", raising=False)

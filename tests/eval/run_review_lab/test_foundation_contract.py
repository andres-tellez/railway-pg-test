"""Smoke checks for the Run Review Lab foundation contract.

These tests intentionally validate only stable architecture promises:
- Lab can be force-disabled via env kill switch.
- Legacy run paths stay enabled by default during staged migration.
"""

from __future__ import annotations

from src.smartcoach_mobile_coach.run_review_lab.config import load_config
from src.smartcoach_mobile_coach.orchestrator import _legacy_run_paths_enabled


def test_lab_force_off_flag_defaults_false(monkeypatch) -> None:
    monkeypatch.delenv("SMARTCOACH_RUN_REVIEW_LAB_FORCE_OFF", raising=False)
    cfg = load_config()
    assert cfg.force_off is False


def test_lab_force_off_flag_reads_true(monkeypatch) -> None:
    monkeypatch.setenv("SMARTCOACH_RUN_REVIEW_LAB_FORCE_OFF", "1")
    cfg = load_config()
    assert cfg.force_off is True


def test_lab_splits_flag_defaults_true(monkeypatch) -> None:
    monkeypatch.delenv("SMARTCOACH_RUN_REVIEW_LAB_SPLITS", raising=False)
    cfg = load_config()
    assert cfg.splits_enabled is True


def test_lab_splits_flag_opt_out(monkeypatch) -> None:
    monkeypatch.setenv("SMARTCOACH_RUN_REVIEW_LAB_SPLITS", "0")
    cfg = load_config()
    assert cfg.splits_enabled is False


def test_legacy_run_paths_default_on(monkeypatch) -> None:
    monkeypatch.delenv("SMARTCOACH_RUN_REVIEW_LEGACY_PATHS", raising=False)
    assert _legacy_run_paths_enabled() is True


def test_legacy_run_paths_opt_out(monkeypatch) -> None:
    monkeypatch.setenv("SMARTCOACH_RUN_REVIEW_LEGACY_PATHS", "0")
    assert _legacy_run_paths_enabled() is False

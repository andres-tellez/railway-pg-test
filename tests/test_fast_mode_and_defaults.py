"""
V1.6 Phase 3D — tests for `SMARTCOACH_FAST_MODE` umbrella flag and
the tightened defaults (max_tokens, timeout).
"""

from __future__ import annotations

from pathlib import Path

import pytest


ORCH_SRC = Path("src/smartcoach_mobile_coach/orchestrator.py").read_text(
    encoding="utf-8"
)


# ---------------------------------------------------------------------------
# SMARTCOACH_FAST_MODE umbrella
# ---------------------------------------------------------------------------


def test_fast_mode_flag_is_wired_into_all_three_minimal_toggles() -> None:
    # Each of the three minimal prompt switches must OR-combine with
    # `fast_mode` so a single env flag flips them together — but an
    # explicit per-switch env MUST still win.
    for snippet in (
        'fast_mode = _env_experiment_minimal_flag("SMARTCOACH_FAST_MODE")',
        '_env_experiment_minimal_flag("SMARTCOACH_EXPERIMENT_MINIMAL_BASE") or fast_mode',
        '_env_experiment_minimal_flag("SMARTCOACH_EXPERIMENT_MINIMAL_PREFS") or fast_mode',
        '_env_experiment_minimal_flag("SMARTCOACH_EXPERIMENT_MINIMAL_DIRECTIVE")',
    ):
        assert snippet in ORCH_SRC, f"expected FAST_MODE wiring fragment: {snippet!r}"


def test_active_prompt_profile_is_logged_every_turn() -> None:
    # Log line is the direct answer to "which prompt is active?" —
    # we lock the tag so grep + dashboards stay stable.
    assert "[coach_prompt_profile]" in ORCH_SRC
    # Keys any latency investigation needs to read at a glance.
    for tok in (
        "fast_mode=%s",
        "minimal_base=%s",
        "minimal_prefs=%s",
        "minimal_directive=%s",
        "model=%s",
        "max_tokens=%s",
    ):
        assert tok in ORCH_SRC, f"prompt-profile log missing {tok!r}"


# ---------------------------------------------------------------------------
# Tightened defaults
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "env_fragment",
    [
        'os.getenv("OPENAI_MAX_TOKENS", "1000")',
        'os.getenv("OPENAI_MOBILE_AGENT_TIMEOUT", "60.0")',
    ],
)
def test_tightened_defaults_locked_in_orchestrator(env_fragment: str) -> None:
    assert env_fragment in ORCH_SRC, (
        "tightened Phase 3D default missing or reverted: " + env_fragment
    )

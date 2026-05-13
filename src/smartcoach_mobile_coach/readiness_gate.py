"""Shared readiness-gate evaluation with short-lived in-process caching.

Tests may monkeypatch ``build_pre_generation_runner_assessment`` and
``evaluate_plan_generation_readiness`` on **this** module; the cache
implementation calls through these symbols.
"""

from __future__ import annotations

from src.coaching_intelligence.plan_generation_readiness import (
    evaluate_plan_generation_readiness,
)
from src.coaching_intelligence.pre_generation_runner_assessment import (
    build_pre_generation_runner_assessment,
)


def get_or_compute_readiness_gate(*args, **kwargs):
    from src.smartcoach_mobile_coach.intake.readiness_cache import (
        get_or_compute_readiness_gate as _impl,
    )

    return _impl(*args, **kwargs)


from src.smartcoach_mobile_coach.intake.readiness_cache import (  # noqa: E402
    ReadinessGateResult,
    _clear_readiness_gate_cache_for_tests,
)

__all__ = (
    "ReadinessGateResult",
    "build_pre_generation_runner_assessment",
    "evaluate_plan_generation_readiness",
    "get_or_compute_readiness_gate",
    "_clear_readiness_gate_cache_for_tests",
)

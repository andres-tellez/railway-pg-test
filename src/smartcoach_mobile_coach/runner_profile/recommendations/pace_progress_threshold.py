"""
Deprecated shim — Tempo/Z3 pace progress lives in ``pace_progress_tempo.py``.

Import from ``pace_progress_tempo`` for new code. This module re-exports legacy names
until Phase 3 alias removal.
"""

from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_core import (
    PaceProgressBand,
    PaceProgressChartZone,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_tempo import (
    DEFAULT_PACE_PROGRESS_TEMPO_CONFIG,
    PaceProgressTempoConfig,
    TempoPaceProgressReference,
    build_tempo_pace_progress_reference,
    build_tempo_pace_progress_zones_chart,
    classify_tempo_pace_progress,
    format_tempo_corridor_target_display,
    tempo_corridor_sec,
    tempo_pace_progress_zones_chart_api_payload,
)

ThresholdPaceProgressReference = TempoPaceProgressReference
PaceProgressThresholdConfig = PaceProgressTempoConfig
DEFAULT_PACE_PROGRESS_THRESHOLD_CONFIG = DEFAULT_PACE_PROGRESS_TEMPO_CONFIG

build_threshold_pace_progress_reference = build_tempo_pace_progress_reference
build_threshold_pace_progress_zones_chart = build_tempo_pace_progress_zones_chart
classify_threshold_pace_progress = classify_tempo_pace_progress
threshold_pace_progress_zones_chart_api_payload = (
    tempo_pace_progress_zones_chart_api_payload
)

__all__ = [
    "PaceProgressBand",
    "PaceProgressChartZone",
    "ThresholdPaceProgressReference",
    "PaceProgressThresholdConfig",
    "DEFAULT_PACE_PROGRESS_THRESHOLD_CONFIG",
    "tempo_corridor_sec",
    "format_tempo_corridor_target_display",
    "build_threshold_pace_progress_reference",
    "threshold_pace_progress_zones_chart_api_payload",
    "build_threshold_pace_progress_zones_chart",
    "classify_threshold_pace_progress",
]

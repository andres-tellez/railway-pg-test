from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GyorHrPositionConfig:
    """HR position vs target band (bpm). Primary signal for easy GYOR."""

    yellow_above_high_bpm: float = 5.0
    orange_above_high_bpm: float = 10.0
    yellow_below_low_bpm: float = 5.0


@dataclass(frozen=True)
class GyorPacePositionConfig:
    """Pace position vs goal-aligned easy band (sec/mi). Secondary signal for easy GYOR."""

    yellow_outside_sec: float = 10.0
    orange_outside_sec: float = 25.0
    red_outside_sec: float = 45.0
    max_band_when_too_slow: str = "yellow"


@dataclass(frozen=True)
class GyorFusionPolicy:
    """How HR and pace bands combine. Easy uses HR-first with fast-pace absolution."""

    name: str = "hr_priority_v1"
    max_band_without_hr: str = "orange"


@dataclass(frozen=True)
class EasyGyorConfig:
    hr: GyorHrPositionConfig = GyorHrPositionConfig()
    pace: GyorPacePositionConfig = GyorPacePositionConfig()
    fusion: GyorFusionPolicy = GyorFusionPolicy()
    chart_fast_axis_cap_min_per_mi: float = 2.0
    chart_slow_axis_cap_min_per_mi: float = 2.0


DEFAULT_EASY_GYOR_CONFIG = EasyGyorConfig()

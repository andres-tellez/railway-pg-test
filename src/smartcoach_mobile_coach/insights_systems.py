"""
Single registry for Insights training systems (Easy / Tempo / Threshold / Speed).

Product naming: Z2=Easy, Z3=Tempo, Z4=Threshold. Do not use ``threshold_*`` for Tempo/Z3.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
from typing import Any

TEMPO_RUN_MIN_SPLITS_WITH_HR = 3
TEMPO_RUN_MIN_FRACTION_SPLITS_ABOVE_Z2_HIGH = 0.5

# Deprecated aliases — remove after migration completes.
THRESHOLD_MIN_SPLITS_WITH_HR = TEMPO_RUN_MIN_SPLITS_WITH_HR
THRESHOLD_MIN_FRACTION_SPLITS_ABOVE_Z2_HIGH = (
    TEMPO_RUN_MIN_FRACTION_SPLITS_ABOVE_Z2_HIGH
)

TEMPO_LEGACY_SYSTEM_KEY = "threshold"


class InsightsSystem(str, Enum):
    EASY = "easy"
    TEMPO = "tempo"
    THRESHOLD = "threshold"  # reserved for future Z4 Insights tab
    SPEED = "speed"


@dataclass(frozen=True)
class InsightsSystemSpec:
    system_key: InsightsSystem
    zone: str
    goal_pace_attr: str
    pace_progress_attr: str
    history_pace_field: str
    history_band_field: str
    run_count_field: str
    kpi_pace_field: str
    trend_band_field: str
    trend_pace_delta_field: str
    legacy_system_key: str | None = None
    legacy_kpi_pace_field: str | None = None
    legacy_trend_band_field: str | None = None


INSIGHTS_SYSTEM_SPECS: dict[InsightsSystem, InsightsSystemSpec] = {
    InsightsSystem.EASY: InsightsSystemSpec(
        system_key=InsightsSystem.EASY,
        zone="z2",
        goal_pace_attr="goal_aligned_easy_pace",
        pace_progress_attr="pace_progress",
        history_pace_field="z2_pace_min_per_mi",
        history_band_field="easy_pace_progress_band",
        run_count_field="easy_run_count",
        kpi_pace_field="z2_pace_min_per_mi",
        trend_band_field="z2_pace",
        trend_pace_delta_field="z2_pace_delta",
    ),
    InsightsSystem.TEMPO: InsightsSystemSpec(
        system_key=InsightsSystem.TEMPO,
        zone="z3",
        goal_pace_attr="goal_aligned_z3_pace",
        pace_progress_attr="tempo_pace_progress",
        history_pace_field="tempo_pace_min_per_mi",
        history_band_field="tempo_pace_progress_band",
        run_count_field="tempo_run_count",
        kpi_pace_field="tempo_pace_min_per_mi",
        trend_band_field="tempo_pace",
        trend_pace_delta_field="tempo_pace_delta",
        legacy_system_key=TEMPO_LEGACY_SYSTEM_KEY,
        legacy_kpi_pace_field="threshold_pace_min_per_mi",
        legacy_trend_band_field="threshold_pace",
    ),
}

TEMPO_SYSTEM_SPEC = INSIGHTS_SYSTEM_SPECS[InsightsSystem.TEMPO]


def resolve_system_snapshot(
    systems: dict[str, Any] | None,
    spec: InsightsSystemSpec,
) -> dict[str, Any]:
    """Read a system slice from stored/API payloads with legacy key fallback."""
    if not systems:
        return {}
    key = spec.system_key.value
    if key in systems and isinstance(systems[key], dict):
        return systems[key]
    legacy = spec.legacy_system_key
    if legacy and legacy in systems and isinstance(systems[legacy], dict):
        return systems[legacy]
    return {}


def read_kpi_field(kpis: dict[str, Any], spec: InsightsSystemSpec, field: str) -> Any:
    """Read a KPI field with legacy name fallback (tempo migration)."""
    if field in kpis:
        return kpis[field]
    if field == spec.kpi_pace_field and spec.legacy_kpi_pace_field:
        return kpis.get(spec.legacy_kpi_pace_field)
    return None


def read_trend_band(bands: dict[str, Any], spec: InsightsSystemSpec) -> Any:
    if spec.trend_band_field in bands:
        return bands[spec.trend_band_field]
    if spec.legacy_trend_band_field:
        return bands.get(spec.legacy_trend_band_field)
    return None


def emit_legacy_tempo_system_aliases(
    systems: dict[str, Any],
) -> dict[str, Any]:
    """Dual-emit Tempo under legacy ``threshold`` system key (API migration only)."""
    out = dict(systems)
    tempo_key = InsightsSystem.TEMPO.value
    legacy = TEMPO_LEGACY_SYSTEM_KEY
    if tempo_key in out and legacy not in out:
        out[legacy] = copy.deepcopy(out[tempo_key])
    return out


_TEMPO_HISTORY_LEGACY_FIELDS: tuple[tuple[str, str], ...] = (
    ("tempo_pace_min_per_mi", "threshold_pace_min_per_mi"),
    ("tempo_pace_progress_band", "threshold_pace_progress_band"),
)


def emit_legacy_tempo_history_field_aliases(point: dict[str, Any]) -> dict[str, Any]:
    """Derive deprecated ``threshold_*`` history fields from canonical ``tempo_*``."""
    out = dict(point)
    for canonical, legacy in _TEMPO_HISTORY_LEGACY_FIELDS:
        if canonical in out and legacy not in out:
            out[legacy] = out[canonical]
    return out


def normalize_tempo_history_point(point: dict[str, Any]) -> dict[str, Any]:
    """Ensure canonical ``tempo_*`` fields when reading legacy payloads."""
    out = dict(point)
    for canonical, legacy in _TEMPO_HISTORY_LEGACY_FIELDS:
        if legacy in out and canonical not in out:
            out[canonical] = out[legacy]
    return out

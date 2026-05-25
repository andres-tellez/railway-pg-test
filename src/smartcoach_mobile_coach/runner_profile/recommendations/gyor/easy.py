from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.models import HrZoneBand, PaceZoneBand
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.config import (
    DEFAULT_EASY_GYOR_CONFIG,
    EasyGyorConfig,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.fusion import (
    fuse_gyor_hr_priority,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.hr_position import (
    classify_hr_position,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.models import (
    EasyGyorClassification,
    EasyGyorReference,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.pace_position import (
    classify_pace_position,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_easy import (
    DEFAULT_PACE_PROGRESS_EASY_CONFIG,
    EasyPaceProgressReference,
    PaceProgressEasyConfig,
    build_easy_pace_progress_reference,
)


def build_easy_gyor_reference(
    *,
    hr_target_z2: HrZoneBand | None,
    goal_aligned_easy_pace: PaceZoneBand | None,
    pace_progress: EasyPaceProgressReference | None = None,
    config: EasyGyorConfig | None = None,
    pace_progress_config: PaceProgressEasyConfig | None = None,
) -> EasyGyorReference | None:
    """Build static easy GYOR reference from marathon goal easy pace + Z2 HR target."""
    if hr_target_z2 is None or goal_aligned_easy_pace is None:
        return None
    cfg = config or DEFAULT_EASY_GYOR_CONFIG
    pp_cfg = pace_progress_config or DEFAULT_PACE_PROGRESS_EASY_CONFIG
    pp = pace_progress or build_easy_pace_progress_reference(
        goal_aligned_easy_pace, config=pp_cfg
    )
    return EasyGyorReference(
        policy=cfg.fusion.name,
        hr_target_z2=hr_target_z2,
        goal_aligned_easy_pace=goal_aligned_easy_pace,
        pace_progress_target_easy_pace=pp.target_easy_pace,
        pace_zones_chart=pp.pace_zones_chart,
    )


def classify_easy_gyor(
    *,
    pace_sec_per_mi: float | None,
    avg_hr_bpm: float | None,
    reference: EasyGyorReference | None,
    config: EasyGyorConfig | None = None,
) -> EasyGyorClassification | None:
    """HR-first easy GYOR (full goal easy band + Z2). Not used for pace-progress chart."""
    if reference is None:
        return None
    cfg = config or DEFAULT_EASY_GYOR_CONFIG

    band_hr = classify_hr_position(
        avg_hr_bpm,
        hr_target=reference.hr_target_z2,
        config=cfg.hr,
    )
    pace_position = classify_pace_position(
        pace_sec_per_mi,
        goal_aligned_easy_pace=reference.goal_aligned_easy_pace,
        config=cfg.pace,
    )
    band_pace = pace_position.band if pace_position is not None else None
    direction = pace_position.direction if pace_position is not None else None

    band = fuse_gyor_hr_priority(
        band_hr=band_hr,
        pace_position=pace_position,
        policy=cfg.fusion,
    )
    if band is None:
        return None

    return EasyGyorClassification(
        band=band,
        band_hr=band_hr,
        band_pace=band_pace,
        pace_direction=direction,
    )

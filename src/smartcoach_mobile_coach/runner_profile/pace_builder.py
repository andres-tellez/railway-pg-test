from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.smartcoach_mobile_coach.display_format import format_pace_sec_per_mi
from src.smartcoach_mobile_coach.runner_profile.models import (
    PaceZoneBand,
    PaceZoneComputation,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaceZoneConfig:
    min_distance_miles: float = 2.0
    lookback_weeks: int = 6
    min_runs_required: int = 6
    min_pace_sec_per_mile: float = 360.0
    max_pace_sec_per_mile: float = 1200.0
    z2_min_offset: float = -15.0
    z2_max_offset: float = 45.0
    z3_min_offset: float = -30.0
    z3_max_offset: float = -20.0
    marathon_offset: float = -60.0
    z4_min_offset: float = -30.0
    z4_max_offset: float = -20.0
    min_week1_long_cap: float = 8.0
    week1_long_cap_buffer: float = 2.0
    min_run_for_long_cap: float = 10.0
    calibration_marathon_pace: float = 600.0
    calibration_z2_low: float = 630.0
    calibration_z2_high: float = 690.0
    calibration_z3_low: float = 610.0
    calibration_z3_high: float = 625.0
    calibration_z4_low: float = 570.0
    calibration_z4_high: float = 580.0


DEFAULT_PACE_ZONE_CONFIG = PaceZoneConfig()


def _format_band_display(low_sec: int, high_sec: int) -> str:
    lo = format_pace_sec_per_mi(float(low_sec))
    hi = format_pace_sec_per_mi(float(high_sec))
    if low_sec == high_sec or lo == hi:
        return lo
    lo_mmss = lo.removesuffix("/mi") if lo.endswith("/mi") else lo
    hi_mmss = hi.removesuffix("/mi") if hi.endswith("/mi") else hi
    return f"{lo_mmss}–{hi_mmss}/mi"


def _build_band(low_sec: float, high_sec: float) -> PaceZoneBand:
    low_i = int(round(low_sec))
    high_i = int(round(high_sec))
    return PaceZoneBand(
        low_sec=low_i,
        high_sec=high_i,
        display=_format_band_display(low_i, high_i),
    )


def calculate_week1_long_cap(
    session: Session,
    user_id: str,
    lookback_weeks: int,
    config: PaceZoneConfig,
) -> float:
    query = text(
        """
        SELECT conv_distance
        FROM activities
        WHERE user_id = :user_id
          AND type = 'Run'
          AND DATE(start_date AT TIME ZONE 'UTC') >= (DATE(NOW() AT TIME ZONE 'UTC') - make_interval(weeks => :lookback_weeks))
          AND conv_distance >= :min_distance
        ORDER BY conv_distance DESC
        LIMIT 1
        """
    )
    try:
        value = session.execute(
            query,
            {
                "user_id": user_id,
                "lookback_weeks": lookback_weeks,
                "min_distance": config.min_run_for_long_cap,
            },
        ).scalar()
    except Exception:
        logger.exception("Failed calculating week1 long cap for user %s", user_id)
        return config.min_week1_long_cap

    if value is None:
        return config.min_week1_long_cap
    return max(config.min_week1_long_cap, float(value) + config.week1_long_cap_buffer)


def _build_from_median(
    median_easy_pace: float,
    week1_long_cap: float,
    source: str,
    config: PaceZoneConfig,
) -> PaceZoneComputation:
    z2_low = median_easy_pace + config.z2_min_offset
    z2_high = median_easy_pace + config.z2_max_offset
    z3_low = median_easy_pace + config.z3_min_offset
    z3_high = median_easy_pace + config.z3_max_offset
    marathon_sec = median_easy_pace + config.marathon_offset
    z4_low = marathon_sec + config.z4_min_offset
    z4_high = marathon_sec + config.z4_max_offset

    return PaceZoneComputation(
        pace_z2=_build_band(z2_low, z2_high),
        pace_z3=_build_band(z3_low, z3_high),
        pace_z4=_build_band(z4_low, z4_high),
        pace_source=source,
        pace_computed_at=datetime.now(timezone.utc),
        marathon_sec=int(round(marathon_sec)),
        week1_long_cap=float(week1_long_cap),
    )


def calibration_pace_zones(
    config: PaceZoneConfig = DEFAULT_PACE_ZONE_CONFIG,
) -> PaceZoneComputation:
    return PaceZoneComputation(
        pace_z2=_build_band(config.calibration_z2_low, config.calibration_z2_high),
        pace_z3=_build_band(config.calibration_z3_low, config.calibration_z3_high),
        pace_z4=_build_band(config.calibration_z4_low, config.calibration_z4_high),
        pace_source="calibration",
        pace_computed_at=datetime.now(timezone.utc),
        marathon_sec=int(round(config.calibration_marathon_pace)),
        week1_long_cap=float(config.min_week1_long_cap),
    )


def compute_pace_zones_from_activities(
    session: Session,
    user_id: str,
    *,
    lookback_weeks: Optional[int] = None,
    config: PaceZoneConfig = DEFAULT_PACE_ZONE_CONFIG,
) -> Optional[PaceZoneComputation]:
    """
    Canonical pace zone computation for runner profile.
    """
    lookback = int(lookback_weeks or config.lookback_weeks)
    query = text(
        """
        WITH valid_runs AS (
            SELECT moving_time::float / conv_distance AS pace_sec_per_mile
            FROM activities
            WHERE user_id = :user_id
              AND type = 'Run'
              AND DATE(start_date AT TIME ZONE 'UTC') >= (DATE(NOW() AT TIME ZONE 'UTC') - make_interval(weeks => :lookback_weeks))
              AND conv_distance >= :min_distance
              AND moving_time IS NOT NULL
              AND moving_time > 0
              AND conv_distance > 0
              AND (moving_time::float / conv_distance) BETWEEN :min_pace AND :max_pace
        )
        SELECT
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pace_sec_per_mile) AS median_pace,
            COUNT(*) AS run_count
        FROM valid_runs
        """
    )
    row = session.execute(
        query,
        {
            "user_id": user_id,
            "lookback_weeks": lookback,
            "min_distance": config.min_distance_miles,
            "min_pace": config.min_pace_sec_per_mile,
            "max_pace": config.max_pace_sec_per_mile,
        },
    ).first()
    if not row:
        return None

    run_count = int(row.run_count or 0)
    if run_count < config.min_runs_required:
        return None

    median_easy_pace = float(row.median_pace)
    week1_long_cap = calculate_week1_long_cap(session, user_id, lookback, config)
    return _build_from_median(
        median_easy_pace=median_easy_pace,
        week1_long_cap=week1_long_cap,
        source="performance",
        config=config,
    )

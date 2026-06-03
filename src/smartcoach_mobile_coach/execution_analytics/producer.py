"""Compute and persist Tier 2 execution facts on activities."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.db.models.activities import Activity
from src.db.models.splits import Split
from src.smartcoach_mobile_coach.execution_analytics.classification import (
    classify_insights_system,
)
from src.smartcoach_mobile_coach.execution_analytics.kpi_primitives import (
    compute_split_kpis,
)
from src.smartcoach_mobile_coach.execution_analytics.tempo_segment import (
    TempoHrZoneBounds,
    TempoSplitRow,
    compute_run_tempo_segment_pace,
)
from src.smartcoach_mobile_coach.execution_analytics.threshold_segment import (
    ThresholdHrZoneBounds,
    ThresholdSplitRow,
    compute_run_threshold_segment_pace,
)
from src.smartcoach_mobile_coach.execution_analytics.thresholds import (
    COMPUTE_STATUS_COMPLETE,
    COMPUTE_STATUS_FAILED,
    COMPUTE_STATUS_SKIPPED_NO_HR_SPLITS,
    COMPUTE_STATUS_SKIPPED_NO_PROFILE,
    COMPUTE_STATUS_SKIPPED_NOT_RUN,
)
from src.smartcoach_mobile_coach.runner_profile.models import RunnerZoneProfileData
from src.smartcoach_mobile_coach.runner_profile.service import get_runner_profile

logger = logging.getLogger(__name__)

EXECUTION_ANALYTICS_VERSION = "2"
DEFAULT_BATCH_SIZE = 100


@dataclass(frozen=True)
class ExecutionComputeResult:
    insights_system: str | None
    easy_pct: float | None
    z2_band_pct: float | None
    hr_drift_pct: float | None
    pace_spread: float | None
    tempo_segment_pace_min_per_mi: float | None
    tempo_segment_avg_hr_bpm: float | None
    tempo_segment_pace_source: str | None
    tempo_segment_split_count: int | None
    tempo_segment_confidence: str | None
    tempo_qualifying_distance_mi: float | None
    threshold_segment_pace_min_per_mi: float | None
    threshold_segment_avg_hr_bpm: float | None
    threshold_segment_pace_source: str | None
    threshold_segment_split_count: int | None
    threshold_segment_confidence: str | None
    threshold_qualifying_distance_mi: float | None
    execution_compute_status: str


def _coerce_finite_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:  # NaN
        return None
    return out


def _split_distance_mi(row: Split) -> float | None:
    dist = _coerce_finite_float(row.conv_distance)
    if dist is not None and dist > 0:
        return dist
    raw_m = _coerce_finite_float(row.distance)
    if raw_m is not None and raw_m > 0:
        return raw_m / 1609.344
    return None


def _split_pace_min_per_mi(row: Split, *, distance_mi: float | None) -> float | None:
    pace = _coerce_finite_float(row.conv_avg_speed)
    if pace is not None and pace > 0:
        return pace
    if distance_mi is not None and distance_mi > 0 and row.moving_time:
        try:
            minutes = float(row.moving_time) / 60.0
            if minutes > 0:
                return round(minutes / distance_mi, 4)
        except (TypeError, ValueError):
            pass
    return None


def splits_to_tempo_rows(splits: Sequence[Split]) -> list[TempoSplitRow]:
    rows: list[TempoSplitRow] = []
    for split in splits:
        split_idx = split.split if split.split is not None else split.lap_index
        if split_idx is None:
            continue
        try:
            split_index = int(split_idx)
        except (TypeError, ValueError):
            continue
        if split_index < 1:
            continue
        distance_mi = _split_distance_mi(split)
        rows.append(
            TempoSplitRow(
                split_index=split_index,
                avg_hr=_coerce_finite_float(split.average_heartrate),
                pace_min_per_mi=_split_pace_min_per_mi(split, distance_mi=distance_mi),
                distance_mi=distance_mi,
            )
        )
    return rows


def tempo_hr_zone_bounds_from_profile(
    profile: RunnerZoneProfileData,
) -> TempoHrZoneBounds:
    return TempoHrZoneBounds(
        z2_high=float(profile.hr_z2.high) if profile.hr_z2 is not None else None,
        z3_low=float(profile.hr_z3.low) if profile.hr_z3 is not None else None,
        z3_high=float(profile.hr_z3.high) if profile.hr_z3 is not None else None,
        z4_low=float(profile.hr_z4.low) if profile.hr_z4 is not None else None,
    )


def threshold_hr_zone_bounds_from_profile(
    profile: RunnerZoneProfileData,
) -> ThresholdHrZoneBounds:
    return ThresholdHrZoneBounds(
        z3_high=float(profile.hr_z3.high) if profile.hr_z3 is not None else None,
        z4_low=float(profile.hr_z4.low) if profile.hr_z4 is not None else None,
        z4_high=float(profile.hr_z4.high) if profile.hr_z4 is not None else None,
        z5_low=float(profile.hr_z5.low) if profile.hr_z5 is not None else None,
    )


def splits_to_threshold_rows(splits: Sequence[Split]) -> list[ThresholdSplitRow]:
    return [
        ThresholdSplitRow(
            split_index=row.split_index,
            avg_hr=row.avg_hr,
            pace_min_per_mi=row.pace_min_per_mi,
            distance_mi=row.distance_mi,
        )
        for row in splits_to_tempo_rows(splits)
    ]


def _null_tempo_fields() -> dict[str, None]:
    return {
        "tempo_segment_pace_min_per_mi": None,
        "tempo_segment_avg_hr_bpm": None,
        "tempo_segment_pace_source": None,
        "tempo_segment_split_count": None,
        "tempo_segment_confidence": None,
        "tempo_qualifying_distance_mi": None,
    }


def _null_threshold_fields() -> dict[str, None]:
    return {
        "threshold_segment_pace_min_per_mi": None,
        "threshold_segment_avg_hr_bpm": None,
        "threshold_segment_pace_source": None,
        "threshold_segment_split_count": None,
        "threshold_segment_confidence": None,
        "threshold_qualifying_distance_mi": None,
    }


def _null_segment_fields() -> dict[str, None]:
    return {**_null_tempo_fields(), **_null_threshold_fields()}


def compute_activity_execution(
    activity: Activity,
    splits: Sequence[Split],
    profile: RunnerZoneProfileData | None,
) -> ExecutionComputeResult:
    if activity.type != "Run":
        return ExecutionComputeResult(
            insights_system=None,
            easy_pct=None,
            z2_band_pct=None,
            hr_drift_pct=None,
            pace_spread=None,
            **_null_segment_fields(),
            execution_compute_status=COMPUTE_STATUS_SKIPPED_NOT_RUN,
        )

    if profile is None or not profile.calibrated or profile.hr_z2 is None:
        return ExecutionComputeResult(
            insights_system=None,
            easy_pct=None,
            z2_band_pct=None,
            hr_drift_pct=None,
            pace_spread=None,
            **_null_segment_fields(),
            execution_compute_status=COMPUTE_STATUS_SKIPPED_NO_PROFILE,
        )

    tempo_rows = splits_to_tempo_rows(splits)
    z2_low = float(profile.hr_z2.low)
    z2_high = float(profile.hr_z2.high)
    z3_low = float(profile.hr_z3.low) if profile.hr_z3 else None
    z3_high = float(profile.hr_z3.high) if profile.hr_z3 else None
    z4_low = float(profile.hr_z4.low) if profile.hr_z4 else None
    z4_high = float(profile.hr_z4.high) if profile.hr_z4 else None
    z5_low = float(profile.hr_z5.low) if profile.hr_z5 else None

    kpis = compute_split_kpis(
        tempo_rows,
        z2_low=z2_low,
        z2_high=z2_high,
        z3_low=z3_low,
        z3_high=z3_high,
        z4_low=z4_low,
        z4_high=z4_high,
        z5_low=z5_low,
    )
    if kpis.n_hr_splits == 0:
        return ExecutionComputeResult(
            insights_system=None,
            easy_pct=None,
            z2_band_pct=None,
            hr_drift_pct=None,
            pace_spread=kpis.pace_spread,
            **_null_segment_fields(),
            execution_compute_status=COMPUTE_STATUS_SKIPPED_NO_HR_SPLITS,
        )

    insights_system = classify_insights_system(
        moving_time_seconds=activity.moving_time,
        avg_hr=_coerce_finite_float(activity.average_heartrate),
        z2_high=z2_high,
        z3_high=z3_high,
        kpis=kpis,
    )

    tempo_fields = _null_tempo_fields()
    threshold_fields = _null_threshold_fields()
    if insights_system == "tempo":
        zones = tempo_hr_zone_bounds_from_profile(profile)
        activity_avg = _coerce_finite_float(activity.conv_avg_speed)
        segment, qualifying = compute_run_tempo_segment_pace(
            tempo_rows,
            zones,
            activity_avg_pace_min_per_mi=activity_avg,
        )
        qualifying_miles = sum(s.distance_mi for s in qualifying)
        tempo_fields = {
            "tempo_segment_pace_min_per_mi": segment.tempo_segment_pace_min_per_mi,
            "tempo_segment_avg_hr_bpm": segment.tempo_segment_avg_hr_bpm,
            "tempo_segment_pace_source": segment.tempo_segment_pace_source,
            "tempo_segment_split_count": (
                segment.tempo_segment_split_count
                if segment.tempo_segment_split_count > 0
                else None
            ),
            "tempo_segment_confidence": segment.tempo_segment_confidence,
            "tempo_qualifying_distance_mi": (
                round(qualifying_miles, 4) if qualifying_miles > 0 else None
            ),
        }
        # activity_avg is diagnostic: clear numeric fields when no HR-qualified segment
        if segment.tempo_segment_pace_source == "activity_avg":
            tempo_fields["tempo_segment_pace_min_per_mi"] = None
            tempo_fields["tempo_segment_avg_hr_bpm"] = None
            tempo_fields["tempo_segment_confidence"] = None
            tempo_fields["tempo_qualifying_distance_mi"] = None

    elif insights_system == "threshold":
        zones = threshold_hr_zone_bounds_from_profile(profile)
        threshold_rows = splits_to_threshold_rows(splits)
        activity_avg = _coerce_finite_float(activity.conv_avg_speed)
        segment, qualifying = compute_run_threshold_segment_pace(
            threshold_rows,
            zones,
            activity_avg_pace_min_per_mi=activity_avg,
        )
        qualifying_miles = sum(s.distance_mi for s in qualifying)
        threshold_fields = {
            "threshold_segment_pace_min_per_mi": segment.threshold_segment_pace_min_per_mi,
            "threshold_segment_avg_hr_bpm": segment.threshold_segment_avg_hr_bpm,
            "threshold_segment_pace_source": segment.threshold_segment_pace_source,
            "threshold_segment_split_count": (
                segment.threshold_segment_split_count
                if segment.threshold_segment_split_count > 0
                else None
            ),
            "threshold_segment_confidence": segment.threshold_segment_confidence,
            "threshold_qualifying_distance_mi": (
                round(qualifying_miles, 4) if qualifying_miles > 0 else None
            ),
        }
        if segment.threshold_segment_pace_source == "activity_avg":
            threshold_fields["threshold_segment_pace_min_per_mi"] = None
            threshold_fields["threshold_segment_avg_hr_bpm"] = None
            threshold_fields["threshold_segment_confidence"] = None
            threshold_fields["threshold_qualifying_distance_mi"] = None

    return ExecutionComputeResult(
        insights_system=insights_system,
        easy_pct=kpis.easy_pct,
        z2_band_pct=kpis.z2_band_pct,
        hr_drift_pct=kpis.hr_drift_pct,
        pace_spread=kpis.pace_spread,
        **tempo_fields,
        **threshold_fields,
        execution_compute_status=COMPUTE_STATUS_COMPLETE,
    )


def apply_execution_result_to_activity(
    activity: Activity,
    result: ExecutionComputeResult,
    *,
    profile: RunnerZoneProfileData | None,
    computed_at: datetime | None = None,
) -> None:
    now = computed_at or datetime.now(timezone.utc)
    activity.insights_system = result.insights_system
    activity.easy_pct = result.easy_pct
    activity.z2_band_pct = result.z2_band_pct
    activity.hr_drift_pct = result.hr_drift_pct
    activity.pace_spread = result.pace_spread
    activity.tempo_segment_pace_min_per_mi = result.tempo_segment_pace_min_per_mi
    activity.tempo_segment_avg_hr_bpm = result.tempo_segment_avg_hr_bpm
    activity.tempo_segment_pace_source = result.tempo_segment_pace_source
    activity.tempo_segment_split_count = result.tempo_segment_split_count
    activity.tempo_segment_confidence = result.tempo_segment_confidence
    activity.tempo_qualifying_distance_mi = result.tempo_qualifying_distance_mi
    activity.threshold_segment_pace_min_per_mi = (
        result.threshold_segment_pace_min_per_mi
    )
    activity.threshold_segment_avg_hr_bpm = result.threshold_segment_avg_hr_bpm
    activity.threshold_segment_pace_source = result.threshold_segment_pace_source
    activity.threshold_segment_split_count = result.threshold_segment_split_count
    activity.threshold_segment_confidence = result.threshold_segment_confidence
    activity.threshold_qualifying_distance_mi = result.threshold_qualifying_distance_mi
    activity.execution_kpis_computed_at = now
    activity.execution_zone_profile_at = (
        profile.computed_at if profile is not None else None
    )
    activity.execution_analytics_version = EXECUTION_ANALYTICS_VERSION
    activity.execution_compute_status = result.execution_compute_status


def compute_and_apply_activity_execution(
    activity: Activity,
    splits: Sequence[Split],
    profile: RunnerZoneProfileData | None,
) -> ExecutionComputeResult:
    result = compute_activity_execution(activity, splits, profile)
    apply_execution_result_to_activity(activity, result, profile=profile)
    return result


def _load_splits_by_activity(
    session: Session, activity_ids: Iterable[int]
) -> dict[int, list[Split]]:
    ids = list(activity_ids)
    if not ids:
        return {}
    rows = (
        session.query(Split)
        .filter(Split.activity_id.in_(ids))
        .order_by(Split.activity_id, Split.split.nullslast(), Split.lap_index)
        .all()
    )
    out: dict[int, list[Split]] = {}
    for row in rows:
        out.setdefault(int(row.activity_id), []).append(row)
    return out


def refresh_activity_execution_kpis(
    session: Session,
    user_id: str,
    *,
    activity_ids: Sequence[int] | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    commit: bool = True,
) -> int:
    """
    Recompute execution facts for a user's runs.

    When activity_ids is omitted, recomputes stale runs (null computed_at,
    profile newer than execution_zone_profile_at, or version mismatch).
    """
    profile = get_runner_profile(session, user_id)

    if activity_ids is not None:
        query = session.query(Activity).filter(
            Activity.user_id == user_id,
            Activity.activity_id.in_(list(activity_ids)),
            Activity.type == "Run",
        )
    else:
        query = session.query(Activity).filter(
            and_(Activity.user_id == user_id, Activity.type == "Run")
        )
        if profile is not None and profile.computed_at is not None:
            query = query.filter(
                or_(
                    Activity.execution_kpis_computed_at.is_(None),
                    Activity.execution_zone_profile_at.is_(None),
                    Activity.execution_zone_profile_at < profile.computed_at,
                    Activity.execution_analytics_version.is_(None),
                    Activity.execution_analytics_version != EXECUTION_ANALYTICS_VERSION,
                )
            )
        else:
            query = query.filter(Activity.execution_kpis_computed_at.is_(None))

    runs = query.order_by(Activity.activity_id).all()
    updated = 0

    for offset in range(0, len(runs), batch_size):
        batch = runs[offset : offset + batch_size]
        split_map = _load_splits_by_activity(
            session, [int(r.activity_id) for r in batch]
        )
        for activity in batch:
            try:
                splits = split_map.get(int(activity.activity_id), [])
                compute_and_apply_activity_execution(activity, splits, profile)
                updated += 1
            except Exception:
                logger.exception(
                    "execution_analytics failed activity_id=%s user_id=%s",
                    activity.activity_id,
                    user_id,
                )
                activity.execution_compute_status = COMPUTE_STATUS_FAILED
                activity.execution_kpis_computed_at = datetime.now(timezone.utc)
                activity.execution_analytics_version = EXECUTION_ANALYTICS_VERSION

        if commit:
            session.commit()

    return updated

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    HrZoneComputation,
    PaceZoneBand,
    PaceZoneComputation,
    RunnerZoneProfileData,
)


def _maybe_hr_band(low: Optional[int], high: Optional[int]) -> Optional[HrZoneBand]:
    if low is None or high is None:
        return None
    return HrZoneBand(low=int(low), high=int(high))


def _maybe_pace_band(
    low: Optional[int],
    high: Optional[int],
) -> Optional[PaceZoneBand]:
    if low is None or high is None:
        return None
    from src.smartcoach_mobile_coach.runner_profile.pace_builder import (
        _format_band_display,
    )

    low_i = int(low)
    high_i = int(high)
    return PaceZoneBand(
        low_sec=low_i, high_sec=high_i, display=_format_band_display(low_i, high_i)
    )


def read_runner_zone_profile(
    session: Session, user_id: str
) -> Optional[RunnerZoneProfileData]:
    row = (
        session.execute(
            text(
                """
            SELECT *
            FROM runner_zone_profiles
            WHERE user_id = CAST(:user_id AS uuid)
            """
            ),
            {"user_id": user_id},
        )
        .mappings()
        .first()
    )
    if not row:
        return None

    return RunnerZoneProfileData(
        user_id=user_id,
        calibrated=row.get("hr_z2_low") is not None
        and row.get("hr_z2_high") is not None,
        computed_at=row.get("computed_at"),
        hrmax_used=row.get("hrmax_used"),
        resting_hr_used=row.get("resting_hr_used"),
        zone_method=row.get("zone_method"),
        hr_z1=_maybe_hr_band(row.get("hr_z1_low"), row.get("hr_z1_high")),
        hr_z2=_maybe_hr_band(row.get("hr_z2_low"), row.get("hr_z2_high")),
        hr_z3=_maybe_hr_band(row.get("hr_z3_low"), row.get("hr_z3_high")),
        hr_z4=_maybe_hr_band(row.get("hr_z4_low"), row.get("hr_z4_high")),
        hr_z5=_maybe_hr_band(row.get("hr_z5_low"), row.get("hr_z5_high")),
        pace_z2=_maybe_pace_band(row.get("pace_z2_low"), row.get("pace_z2_high")),
        pace_z3=_maybe_pace_band(row.get("pace_z3_low"), row.get("pace_z3_high")),
        pace_z4=_maybe_pace_band(row.get("pace_z4_low"), row.get("pace_z4_high")),
        pace_source=row.get("pace_source"),
        pace_computed_at=row.get("pace_computed_at"),
    )


def upsert_runner_zone_profile(
    session: Session,
    user_id: str,
    *,
    hr: HrZoneComputation,
    pace: PaceZoneComputation,
) -> None:
    session.execute(
        text(
            """
            INSERT INTO runner_zone_profiles (
                user_id,
                hr_z1_low, hr_z1_high,
                hr_z2_low, hr_z2_high,
                hr_z3_low, hr_z3_high,
                hr_z4_low, hr_z4_high,
                hr_z5_low, hr_z5_high,
                hrmax_used, resting_hr_used, zone_method,
                pace_z2_low, pace_z2_high,
                pace_z3_low, pace_z3_high,
                pace_z4_low, pace_z4_high,
                pace_source, pace_computed_at, computed_at
            ) VALUES (
                CAST(:user_id AS uuid),
                :hr_z1_low, :hr_z1_high,
                :hr_z2_low, :hr_z2_high,
                :hr_z3_low, :hr_z3_high,
                :hr_z4_low, :hr_z4_high,
                :hr_z5_low, :hr_z5_high,
                :hrmax_used, :resting_hr_used, :zone_method,
                :pace_z2_low, :pace_z2_high,
                :pace_z3_low, :pace_z3_high,
                :pace_z4_low, :pace_z4_high,
                :pace_source, :pace_computed_at, :computed_at
            )
            ON CONFLICT (user_id) DO UPDATE SET
                hr_z1_low = EXCLUDED.hr_z1_low,
                hr_z1_high = EXCLUDED.hr_z1_high,
                hr_z2_low = EXCLUDED.hr_z2_low,
                hr_z2_high = EXCLUDED.hr_z2_high,
                hr_z3_low = EXCLUDED.hr_z3_low,
                hr_z3_high = EXCLUDED.hr_z3_high,
                hr_z4_low = EXCLUDED.hr_z4_low,
                hr_z4_high = EXCLUDED.hr_z4_high,
                hr_z5_low = EXCLUDED.hr_z5_low,
                hr_z5_high = EXCLUDED.hr_z5_high,
                hrmax_used = EXCLUDED.hrmax_used,
                resting_hr_used = EXCLUDED.resting_hr_used,
                zone_method = EXCLUDED.zone_method,
                pace_z2_low = EXCLUDED.pace_z2_low,
                pace_z2_high = EXCLUDED.pace_z2_high,
                pace_z3_low = EXCLUDED.pace_z3_low,
                pace_z3_high = EXCLUDED.pace_z3_high,
                pace_z4_low = EXCLUDED.pace_z4_low,
                pace_z4_high = EXCLUDED.pace_z4_high,
                pace_source = EXCLUDED.pace_source,
                pace_computed_at = EXCLUDED.pace_computed_at,
                computed_at = EXCLUDED.computed_at
            """
        ),
        {
            "user_id": user_id,
            "hr_z1_low": hr.zones["z1"].low if "z1" in hr.zones else None,
            "hr_z1_high": hr.zones["z1"].high if "z1" in hr.zones else None,
            "hr_z2_low": hr.zones["z2"].low if "z2" in hr.zones else None,
            "hr_z2_high": hr.zones["z2"].high if "z2" in hr.zones else None,
            "hr_z3_low": hr.zones["z3"].low if "z3" in hr.zones else None,
            "hr_z3_high": hr.zones["z3"].high if "z3" in hr.zones else None,
            "hr_z4_low": hr.zones["z4"].low if "z4" in hr.zones else None,
            "hr_z4_high": hr.zones["z4"].high if "z4" in hr.zones else None,
            "hr_z5_low": hr.zones["z5"].low if "z5" in hr.zones else None,
            "hr_z5_high": hr.zones["z5"].high if "z5" in hr.zones else None,
            "hrmax_used": hr.hrmax_used,
            "resting_hr_used": hr.resting_hr_used,
            "zone_method": hr.method,
            "pace_z2_low": pace.pace_z2.low_sec,
            "pace_z2_high": pace.pace_z2.high_sec,
            "pace_z3_low": pace.pace_z3.low_sec,
            "pace_z3_high": pace.pace_z3.high_sec,
            "pace_z4_low": pace.pace_z4.low_sec,
            "pace_z4_high": pace.pace_z4.high_sec,
            "pace_source": pace.pace_source,
            "pace_computed_at": pace.pace_computed_at,
            "computed_at": datetime.utcnow(),
        },
    )


def delete_runner_zone_profile(session: Session, user_id: str) -> None:
    session.execute(
        text("DELETE FROM runner_zone_profiles WHERE user_id = CAST(:user_id AS uuid)"),
        {"user_id": user_id},
    )

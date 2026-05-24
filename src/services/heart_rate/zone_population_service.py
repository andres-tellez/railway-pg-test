"""
Zone Population Service (compatibility shim).

Legacy callers still invoke ``refresh_user_zones``. The canonical storage is now
``runner_zone_profiles``; this shim keeps the old function name while delegating
to ``refresh_runner_profile``.
"""

import logging
import uuid as uuid_lib
from typing import Optional

from sqlalchemy.orm import Session

from src.db.models.weekly_training_insights import WeeklyTrainingInsight
from src.smartcoach_mobile_coach.runner_profile import refresh_runner_profile

logger = logging.getLogger(__name__)


def _clear_weekly_insights(session: Session, user_id: str) -> None:
    """Remove weekly Insights rows for users without calibrated HR zones."""
    uid_key = uuid_lib.UUID(str(user_id))

    session.query(WeeklyTrainingInsight).filter(
        WeeklyTrainingInsight.user_id == uid_key
    ).delete(synchronize_session=False)
    session.commit()
    logger.info(
        "Cleared weekly_training_insights for user %s "
        "(no calibrated runner zone profile)",
        user_id,
    )


def refresh_user_zones(session: Session, user_id: str) -> Optional[dict]:
    """
    Deprecated shim kept for backward compatibility with old call sites.
    """
    profile = refresh_runner_profile(session, user_id)
    if not profile.calibrated:
        logger.info(
            "No calibrated runner zones for user %s — clearing weekly insights",
            user_id,
        )
        _clear_weekly_insights(session, user_id)
        return None

    row = {
        "user_id": user_id,
        "z1_low": profile.hr_z1.low if profile.hr_z1 else None,
        "z1_high": profile.hr_z1.high if profile.hr_z1 else None,
        "z2_low": profile.hr_z2.low if profile.hr_z2 else None,
        "z2_high": profile.hr_z2.high if profile.hr_z2 else None,
        "z3_low": profile.hr_z3.low if profile.hr_z3 else None,
        "z3_high": profile.hr_z3.high if profile.hr_z3 else None,
        "z4_low": profile.hr_z4.low if profile.hr_z4 else None,
        "z4_high": profile.hr_z4.high if profile.hr_z4 else None,
        "z5_low": profile.hr_z5.low if profile.hr_z5 else None,
        "z5_high": profile.hr_z5.high if profile.hr_z5 else None,
        "method": profile.zone_method,
        "hrmax_used": (
            float(profile.hrmax_used) if profile.hrmax_used is not None else None
        ),
        "resting_hr_used": (
            float(profile.resting_hr_used)
            if profile.resting_hr_used is not None
            else None
        ),
        "computed_at": profile.computed_at,
    }

    logger.info(
        "Refreshed runner profile zones for user %s: method=%s, z2=%s-%s",
        user_id,
        profile.zone_method,
        row["z2_low"],
        row["z2_high"],
    )
    return row

"""Tests for zone_population_service (zones + Insight snapshot invalidation)."""

from __future__ import annotations

import uuid
from datetime import date

from src.db.dao.user_profile_dao import save_user_profile
from src.db.models.weekly_training_insights import WeeklyTrainingInsight
from src.services.heart_rate.zone_population_service import refresh_user_zones


def test_refresh_user_zones_clears_stale_weekly_insights_when_no_effective_max_hr(
    test_db_session,
):
    """Weekly insights rows must drop when HRmax is not available."""
    uid = uuid.uuid4()
    uid_s = str(uid)
    save_user_profile(
        test_db_session,
        {
            "user_id": uid_s,
            "height_feet": 5,
            "height_inches": 10,
            "max_hr_manual": None,
            "max_hr_auto": None,
            "max_hr_active": None,
        },
    )

    test_db_session.add(
        WeeklyTrainingInsight(
            user_id=uid,
            week_start=date(2026, 1, 5),
            week_end=date(2026, 1, 11),
            overall_band="green",
            hr_drift_pct=1.0,
        )
    )
    test_db_session.commit()

    assert refresh_user_zones(test_db_session, uid_s) is None

    assert (
        test_db_session.query(WeeklyTrainingInsight).filter_by(user_id=uid).first()
        is None
    )

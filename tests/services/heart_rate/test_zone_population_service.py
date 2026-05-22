"""Tests for zone_population_service (zones + Insight snapshot invalidation)."""

from __future__ import annotations

import uuid
from datetime import date

from src.db.dao.user_profile_dao import save_user_profile
from src.db.models.user_hr_zones import UserHrZones
from src.db.models.weekly_training_insights import WeeklyTrainingInsight
from src.services.heart_rate.zone_population_service import refresh_user_zones


def test_refresh_user_zones_clears_stale_data_when_no_effective_max_hr(test_db_session):
    """Stale user_hr_zones + weekly_training_insights rows must drop when HRmax absent."""
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
        UserHrZones(
            user_id=uid_s,
            z1_low=100,
            z1_high=119,
            z2_low=120,
            z2_high=139,
            z3_low=140,
            z3_high=159,
            z4_low=160,
            z4_high=179,
            z5_low=180,
            z5_high=190,
            method="pct_max",
            hrmax_used=190,
        )
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

    assert test_db_session.query(UserHrZones).filter_by(user_id=uid_s).first() is None
    assert (
        test_db_session.query(WeeklyTrainingInsight).filter_by(user_id=uid).first()
        is None
    )

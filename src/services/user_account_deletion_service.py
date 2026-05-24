"""
Permanent account erasure for a single internal user_id.

Used by GDPR self-service delete and admin tooling. Caller must commit/rollback the session.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from sqlalchemy.orm import Session

from src.db.models.activities import Activity
from src.db.models.plans import Plan
from src.db.models.splits import Split
from src.db.models.tokens import Token
from src.db.models.user_athletes import UserAthleteLink
from src.db.models.user_profile import UserProfile
from src.db.models.user_identity import UserIdentity
from src.db.models.user_auth_providers import UserAuthProvider
from src.db.models.weekly_training_insights import WeeklyTrainingInsight
from src.db.models.user_coach_preferences import UserCoachPreferences
from src.db.models.runner_zone_profiles import RunnerZoneProfile

logger = logging.getLogger(__name__)


def delete_all_user_account_data(
    session: Session, internal_user_id: str
) -> Dict[str, Any]:
    """
    Delete all application data for internal_user_id (UUID string).

    Returns a summary dict suitable for JSON responses. Does not commit.
    """
    uid_str = str(internal_user_id).strip()
    uid_uuid = uuid.UUID(uid_str)

    deletions: Dict[str, int] = {
        "splits": 0,
        "activities": 0,
        "plans": 0,
        "athlete_links": 0,
        "tokens": 0,
        "profile": 0,
        "identity": 0,
        "auth_providers": 0,
        "weekly_training_insights": 0,
        "user_coach_preferences": 0,
        "runner_zone_profiles": 0,
    }

    deletions["weekly_training_insights"] = (
        session.query(WeeklyTrainingInsight).filter_by(user_id=uid_uuid).delete()
    )
    deletions["user_coach_preferences"] = (
        session.query(UserCoachPreferences).filter_by(user_id=uid_uuid).delete()
    )
    deletions["runner_zone_profiles"] = (
        session.query(RunnerZoneProfile).filter_by(user_id=uid_uuid).delete()
    )

    # Splits reference activities; production FK may not CASCADE — delete splits first.
    activity_ids_for_user = session.query(Activity.activity_id).filter_by(
        user_id=internal_user_id
    )
    deletions["splits"] = (
        session.query(Split)
        .filter(Split.activity_id.in_(activity_ids_for_user))
        .delete(synchronize_session=False)
    )

    deletions["activities"] = (
        session.query(Activity).filter_by(user_id=internal_user_id).delete()
    )
    deletions["plans"] = session.query(Plan).filter_by(user_id=uid_uuid).delete()

    athlete_links = session.query(UserAthleteLink).filter_by(user_id=uid_str).all()
    for link in athlete_links:
        deletions["tokens"] += (
            session.query(Token).filter_by(athlete_id=link.athlete_id).delete()
        )

    deletions["athlete_links"] = (
        session.query(UserAthleteLink).filter_by(user_id=uid_str).delete()
    )

    deletions["auth_providers"] = (
        session.query(UserAuthProvider).filter_by(user_id=uid_str).delete()
    )

    deletions["profile"] = (
        session.query(UserProfile).filter_by(user_id=uid_str).delete()
    )

    deletions["identity"] = (
        session.query(UserIdentity).filter_by(user_id=uid_uuid).delete()
    )

    logger.info("Account data deleted for user_id=%s summary=%s", uid_str, deletions)
    return deletions

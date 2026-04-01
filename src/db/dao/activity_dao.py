# @file activity_dao.py
# @component ActivityDAO
# @description: Handles database operations for Strava activities
# @features: Insert, update, query by athlete or activity
# @integration-points: SQLAlchemy ORM, Postgres (insert + on_conflict), conversion utils
# @usage: Used in ingestion orchestration and enrichment
# @prerequisites: Activity table must exist with correct schema

from typing import Any, List, Dict, Optional
from datetime import date
import uuid
import logging

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from uuid import UUID

from src.db.models.activities import Activity
from src.utils.activity_local_date_sql import ACTIVITY_LOCAL_DATE_SQL_FRAGMENT
from src.utils.logger import get_logger
from src.utils.conversions import convert_metrics  # assumed to exist

logger = get_logger(__name__)


class ActivityDAO:
    @staticmethod
    def upsert_activities(
        session: Session,
        athlete_id: int,
        activities: List[Dict],
        user_id: UUID,
    ) -> int:
        """
        Upsert 'Run' activities into the database.
        Requires activity_id, user_id (UUID), and minimum required fields.
        Skips invalid or non-Run types.
        """

        if not activities:
            logger.warning("[WARNING] No activities provided to upsert.")
            return 0

        # Handle user_id validation - can be None, UUID object, or UUID string
        uid = None
        if user_id is not None:
            try:
                uid = uuid.UUID(str(user_id))
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(
                    f"Invalid user_id format (not UUID): {user_id}, continuing without user_id: {e}"
                )
                uid = None  # Continue without user_id rather than failing completely

        logger.info(
            f"[INFO] Preparing to upsert {len(activities)} activities for athlete={athlete_id}, user_id={uid}"
        )

        rows = []
        for act in activities:
            logger.debug(
                f"[DEBUG] Processing candidate: {act.get('activity_id') or act.get('id')}"
            )

            # Ensure it's a 'Run'
            if act.get("type") != "Run":
                logger.debug(f"[SKIP] Skipping non-Run activity type={act.get('type')}")
                continue

            name = (act.get("name") or "").lower()
            is_treadmill = "treadmill" in name

            # Required fields check
            required_fields = [
                "activity_id",
                "start_date",
                "distance",
                "moving_time",
                "elapsed_time",
            ]
            if not is_treadmill:
                required_fields.append("external_id")

            missing = [f for f in required_fields if not act.get(f)]
            if missing:
                logger.error(
                    f"[ERROR] Skipping activity {act.get('activity_id')} due to missing: {missing}"
                )
                continue

            # Metric conversions
            conv_input = {
                "distance": act.get("distance"),
                "elevation": act.get("total_elevation_gain"),
                "average_speed": act.get("average_speed"),
                "max_speed": act.get("max_speed"),
                "moving_time": act.get("moving_time"),
                "elapsed_time": act.get("elapsed_time"),
            }

            conv = convert_metrics(
                conv_input,
                [
                    "distance",
                    "elevation",
                    "average_speed",
                    "max_speed",
                    "moving_time",
                    "elapsed_time",
                ],
            )

            row = {
                "activity_id": act["activity_id"],
                "athlete_id": athlete_id,
                "user_id": uid,
                "name": act.get("name"),
                "type": act.get("type"),
                "start_date": act.get("start_date"),
                "distance": act.get("distance"),
                "elapsed_time": act.get("elapsed_time"),
                "moving_time": act.get("moving_time"),
                "total_elevation_gain": act.get("total_elevation_gain"),
                "external_id": act.get("external_id"),
                "timezone": act.get("timezone"),
                "hr_zone_1": act.get("hr_zone_1"),
                "hr_zone_2": act.get("hr_zone_2"),
                "hr_zone_3": act.get("hr_zone_3"),
                "hr_zone_4": act.get("hr_zone_4"),
                "hr_zone_5": act.get("hr_zone_5"),
                "conv_distance": conv.get("conv_distance"),
                "conv_elevation_feet": conv.get("conv_elevation_feet"),
                "conv_avg_speed": conv.get("conv_avg_speed"),
                "conv_max_speed": conv.get("conv_max_speed"),
                "conv_moving_time": conv.get("conv_moving_time"),
                "conv_elapsed_time": conv.get("conv_elapsed_time"),
            }

            rows.append(row)

        skipped_count = len(activities) - len(rows)
        if skipped_count:
            logger.warning(
                f"[WARNING] Skipped {skipped_count} activities due to missing required fields or unsupported types."
            )

        if not rows:
            logger.warning("[WARNING] No valid rows prepared for upsert.")
            return 0

        logger.info(f"[INFO] Upserting {len(rows)} activities into database...")
        logger.debug(f"[DEBUG] Example row: {rows[0]}")

        try:
            stmt = insert(Activity).values(rows)

            update_cols = {
                col.name: getattr(stmt.excluded, col.name)
                for col in Activity.__table__.columns
                if col.name not in ("activity_id", "user_id")
            }

            stmt = stmt.on_conflict_do_update(
                index_elements=["activity_id"], set_=update_cols
            )

            result = session.execute(stmt)
            session.commit()
            logger.info(f"[SUCCESS] Successfully upserted {result.rowcount} activities")
            return result.rowcount
        except Exception as e:
            session.rollback()
            logger.error(f"[ERROR] Upsert failed: {e}")
            return 0

    @staticmethod
    def get_by_id(session: Session, activity_id: int) -> Optional[Activity]:
        return session.query(Activity).filter_by(activity_id=activity_id).first()

    @staticmethod
    def get_activities_by_athlete(session: Session, athlete_id: int) -> List[Activity]:
        return (
            session.query(Activity)
            .filter(Activity.athlete_id == athlete_id)
            .order_by(Activity.start_date.desc())
            .all()
        )

    @staticmethod
    def find_run_activity_ids_on_local_date(
        session: Session,
        athlete_id: int,
        local_date: date,
        max_lookback_days: Optional[int] = None,
    ) -> List[int]:
        """
        Return activity_ids for Run activities on the athlete's local calendar date.

        Uses the same local-date expression as GET /api/activities/. Optional
        max_lookback_days filters by start_date (omit or 0 for full history).
        """
        params: Dict[str, Any] = {"aid": athlete_id, "d": local_date}
        lookback_clause = ""
        if max_lookback_days is not None and max_lookback_days > 0:
            lookback_clause = (
                "AND start_date >= (NOW() AT TIME ZONE 'UTC') "
                "- (:lookback_days * INTERVAL '1 day')"
            )
            params["lookback_days"] = max_lookback_days

        q = text(
            f"""
            SELECT activity_id
            FROM public.activities
            WHERE athlete_id = :aid
            AND type = 'Run'
            AND ({ACTIVITY_LOCAL_DATE_SQL_FRAGMENT}) = :d
            {lookback_clause}
            ORDER BY start_date DESC
            """
        )
        rows = session.execute(q, params).fetchall()
        return [int(r[0]) for r in rows]

    @staticmethod
    def search_runs(
        session: Session,
        athlete_id: int,
        *,
        min_distance_m: Optional[float] = None,
        max_distance_m: Optional[float] = None,
        name_query: Optional[str] = None,
        start_date_from: Optional[date] = None,
        start_date_to: Optional[date] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search Run activities for an athlete using optional filters.

        Results are ordered newest-first and capped to a small limit for tool usage.
        """
        lim = max(1, min(int(limit), 20))
        params: Dict[str, Any] = {"aid": athlete_id, "lim": lim}
        where_parts = ["athlete_id = :aid", "type = 'Run'"]

        if min_distance_m is not None:
            where_parts.append("distance >= :min_distance_m")
            params["min_distance_m"] = float(min_distance_m)
        if max_distance_m is not None:
            where_parts.append("distance <= :max_distance_m")
            params["max_distance_m"] = float(max_distance_m)
        if name_query:
            where_parts.append("COALESCE(name, '') ILIKE :name_query")
            params["name_query"] = f"%{name_query.strip()}%"
        if start_date_from is not None:
            where_parts.append("start_date::date >= :start_date_from")
            params["start_date_from"] = start_date_from
        if start_date_to is not None:
            where_parts.append("start_date::date <= :start_date_to")
            params["start_date_to"] = start_date_to

        q = text(
            f"""
            SELECT activity_id, name, start_date, distance
            FROM public.activities
            WHERE {" AND ".join(where_parts)}
            ORDER BY start_date DESC
            LIMIT :lim
            """
        )
        rows = session.execute(q, params).fetchall()
        return [
            {
                "activity_id": int(r.activity_id),
                "name": r.name,
                "start_date": r.start_date,
                "distance": float(r.distance) if r.distance is not None else None,
            }
            for r in rows
        ]


def has_existing_activities(session: Session, athlete_id: int) -> bool:
    count = session.query(Activity).filter(Activity.athlete_id == athlete_id).count()
    return count > 0

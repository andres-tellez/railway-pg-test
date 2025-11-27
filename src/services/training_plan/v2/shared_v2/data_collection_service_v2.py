"""
Layer 1: Data Collection Service

Purpose:
    Gather all raw data needed for training plan generation from the database.
    This layer is responsible ONLY for data retrieval, not calculation or transformation.

Responsibilities:
    - Fetch user profile information
    - Fetch Strava running activities (configurable timeframe)
    - Aggregate all data into a structured format for Layer 2

Dependencies:
    - SQLAlchemy session
    - Existing DAOs (user_profile_dao, ActivityDAO)

Testing:
    See tests/services/training_plan/test_data_collection_service.py

Author: SmartCoach Development Team
Last Updated: October 29, 2025
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, text

from src.db.dao.user_profile_dao import get_user_profile
from src.db.models.activities import Activity

# Configuration constants
MAX_WEEKS = 52  # Maximum activity history (1 year)
MAX_ACTIVITIES = 500  # Safety limit to prevent performance issues

logger = logging.getLogger(__name__)


class DataCollectionService:
    """
    Service for collecting raw data needed for training plan generation.

    This service acts as the data access layer, fetching information from
    the database without performing any calculations or transformations.
    """

    @staticmethod
    def fetch_user_profile(session: Session, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch user profile information from the database using existing DAO.

        Args:
            session: SQLAlchemy database session
            user_id: UUID string of the user

        Returns:
            Dictionary containing user profile data, or None if profile doesn't exist

        Example:
            {
                "age_group": "30-39",
                "height_feet": 5,
                "height_inches": 10,
                "weight": 165.0,
            }
        """
        # Use existing DAO to fetch profile
        profile_dict = get_user_profile(session, user_id)

        if not profile_dict:
            return None

        # Return normalized profile data (DAO already normalizes it)
        return {
            "age_group": profile_dict.get("age_group"),
            "height_feet": profile_dict.get("height_feet"),
            "height_inches": profile_dict.get("height_inches"),
            "weight": profile_dict.get("weight"),
        }

    @staticmethod
    def fetch_strava_activities(
        session: Session, user_id: str, weeks: int = 12, activity_type: str = "Run"
    ) -> List[Dict[str, Any]]:
        """
        Fetch Strava running activities for the specified time period.

        Args:
            session: SQLAlchemy database session
            user_id: UUID string of the user
            weeks: Number of weeks of history to fetch (default: 12, max: 52)
            activity_type: Type of activity to fetch (default: "Run")

        Returns:
            List of activity dictionaries, sorted by date (newest first)

        Raises:
            ValueError: If user_id is invalid or weeks is out of bounds
            RuntimeError: If database query fails

        Example:
            [
                {
                    "activity_id": 12345,
                    "date": "2025-10-20",
                    "distance": 5.2,  # miles
                    "moving_time": 2850,  # seconds
                    "average_heartrate": 145,  # bpm
                    "average_speed": 3.5,  # meters/second
                    "total_elevation_gain": 50,  # meters
                },
                ...
            ]
        """
        # Validate inputs
        if not isinstance(weeks, int):
            raise TypeError(f"weeks must be an integer, got {type(weeks).__name__}")

        if weeks < 1:
            raise ValueError(f"weeks must be at least 1, got {weeks}")

        if weeks > MAX_WEEKS:
            logger.warning(
                f"Requested {weeks} weeks exceeds maximum {MAX_WEEKS}, clamping to {MAX_WEEKS}"
            )
            weeks = MAX_WEEKS

        # Validate and convert user_id to UUID
        try:
            user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
        except (ValueError, AttributeError, TypeError) as e:
            raise ValueError(f"Invalid user_id format: {user_id}") from e

        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(weeks=weeks)
        current_time = datetime.now()

        # Try view first (v_completed_activities), then fall back to table
        result: List[Dict[str, Any]] = []
        view_error: Optional[Exception] = None

        # Try view first (v_completed_activities)
        try:
            rows = (
                session.execute(
                    text(
                        """
                        SELECT
                            activity_id,
                            activity_date,
                            distance AS distance_miles,
                            moving_time,
                            avg_hr AS average_heartrate,
                            max_hr AS max_heartrate,
                            avg_speed AS average_speed,
                            max_speed,
                            elevation AS total_elevation_gain
                        FROM v_completed_activities
                        WHERE user_id = :uid
                          AND activity_date >= :cutoff_date
                          AND activity_date <= :now_date
                        ORDER BY activity_date DESC
                        LIMIT :lim
                        """
                    ),
                    {
                        "uid": str(user_uuid),
                        "cutoff_date": cutoff_date.date(),
                        "now_date": current_time.date(),
                        "lim": MAX_ACTIVITIES,
                    },
                )
                .mappings()
                .all()
            )

            for r in rows:
                activity_date = r.get("activity_date")
                date_str = (
                    activity_date.strftime("%Y-%m-%d")
                    if hasattr(activity_date, "strftime")
                    else str(activity_date)
                )
                result.append(
                    {
                        "activity_id": r.get("activity_id"),
                        "date": date_str,
                        "distance": float(r.get("distance_miles") or 0.0),  # miles
                        "moving_time": int(r.get("moving_time") or 0),  # seconds
                        "average_heartrate": r.get("average_heartrate"),  # bpm
                        "max_heartrate": r.get("max_heartrate"),  # bpm
                        "average_speed": r.get("average_speed"),  # m/s
                        "max_speed": r.get("max_speed"),  # m/s
                        "total_elevation_gain": r.get("total_elevation_gain"),  # meters
                    }
                )
            logger.debug(
                f"Fetched {len(result)} activities from v_completed_activities view for user {user_id} (last {weeks} weeks)"
            )
        except Exception as e:
            try:
                session.rollback()
            except Exception:
                pass
            view_error = e
            logger.debug(
                f"View fetch failed or not available, will fall back to activities table: {e}"
            )

        # Fall back to activities table if view failed or returned no results
        if not result:
            try:
                activities = (
                    session.query(Activity)
                    .filter(
                        and_(
                            Activity.user_id == user_uuid,
                            Activity.type == activity_type,
                            Activity.start_date >= cutoff_date,
                            Activity.start_date
                            <= current_time,  # Filter out future dates
                        )
                    )
                    .order_by(Activity.start_date.desc())
                    .limit(MAX_ACTIVITIES)  # Safety limit for performance
                    .all()
                )

                logger.debug(
                    f"Fetched {len(activities)} activities from activities table for user {user_id} (last {weeks} weeks)"
                )

                # Convert to dictionaries
                for activity in activities:
                    result.append(
                        {
                            "activity_id": activity.activity_id,
                            "date": (
                                activity.start_date.strftime("%Y-%m-%d")
                                if activity.start_date
                                else None
                            ),
                            "distance": activity.conv_distance,  # Already converted to miles
                            "moving_time": activity.moving_time,  # seconds
                            "elapsed_time": activity.elapsed_time,  # seconds
                            "average_heartrate": activity.average_heartrate,  # bpm
                            "max_heartrate": activity.max_heartrate,  # bpm
                            "average_speed": activity.average_speed,  # m/s
                            "max_speed": activity.max_speed,  # m/s
                            "total_elevation_gain": activity.total_elevation_gain,  # meters
                            "suffer_score": activity.suffer_score,
                        }
                    )

            except Exception as e:
                logger.error(
                    f"Database error fetching activities for user {user_id}: {e}"
                )
                if view_error:
                    logger.error(f"Original view error: {view_error}")
                raise RuntimeError("Failed to fetch activities from database") from e

        return result

    @staticmethod
    def collect_all_data(
        session: Session,
        user_id: str,
        plan_request: Dict[str, Any],
        activity_weeks: int = 12,
    ) -> Dict[str, Any]:
        """
        Collect all data needed for training plan generation.

        This is the main entry point for Layer 1. It aggregates all necessary data
        from the database into a single structured package for Layer 2 processing.

        Args:
            session: SQLAlchemy database session
            user_id: UUID string of the user
            plan_request: Dictionary containing plan creation request data
                         (race_date, primary_goal, etc.)
            activity_weeks: Number of weeks of activity history to fetch (default: 12)

        Returns:
            Complete data package containing:
                - user_profile: User demographic and preference information
                - strava_activities: Historical running activity data
                - plan_request: The original plan request parameters

        Raises:
            ValueError: If user profile doesn't exist or inputs are invalid
            RuntimeError: If database operations fail

        Example:
            >>> data = DataCollectionService.collect_all_data(
            ...     session=db_session,
            ...     user_id="abc-123",
            ...     plan_request={
            ...         "race_date": "2025-06-15",
            ...         "primary_goal": "Just Finish",
            ...         "training_days": ["Mon", "Wed", "Fri", "Sat"],
            ...         "notes": "First marathon attempt"
            ...     }
            ... )
        """
        logger.info(
            f"Starting data collection for user {user_id}, requesting {activity_weeks} weeks of history"
        )

        # Fetch user profile
        user_profile = DataCollectionService.fetch_user_profile(session, user_id)
        if not user_profile:
            logger.error(f"User profile not found for user_id: {user_id}")
            raise ValueError(f"User profile not found for user_id: {user_id}")

        logger.debug(
            f"User profile retrieved: age_group={user_profile.get('age_group')}"
        )

        # Fetch Strava activities
        strava_activities = DataCollectionService.fetch_strava_activities(
            session=session, user_id=user_id, weeks=activity_weeks
        )

        logger.info(
            f"Data collection complete: {len(strava_activities)} activities found"
        )

        # Aggregate all data
        return {
            "user_profile": user_profile,
            "strava_activities": strava_activities,
            "plan_request": plan_request,
            "metadata": {
                "collected_at": datetime.now().isoformat(),
                "activity_weeks_requested": activity_weeks,
                "activities_found": len(strava_activities),
            },
        }

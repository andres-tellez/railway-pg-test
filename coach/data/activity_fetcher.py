"""
ActivityFetcher for Coach system.

Fetches database activities filtered to exact calendar week boundaries.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, and_

from coach.utils.error_handler import CoachErrorHandler, ErrorSeverity


@dataclass
class ActivityRecord:
    """
    Standardized activity record format.

    All fields are optional to handle missing data gracefully.
    """

    date: date
    activity_id: Optional[int] = None
    activity_name: Optional[str] = None
    distance_miles: Optional[float] = None
    avg_pace_seconds_per_mile: Optional[float] = None  # seconds per mile
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    moving_time_seconds: Optional[int] = None
    hr_zones: Optional[dict] = None  # {"z1": 20.0, "z2": 60.0, ...} percentages
    workout_type: Optional[str] = (
        None  # "easy", "tempo", "long_run", "interval", "other"
    )

    @property
    def avg_pace_str(self) -> Optional[str]:
        """Format pace as MM:SS/mile string."""
        if self.avg_pace_seconds_per_mile is None:
            return None
        minutes = int(self.avg_pace_seconds_per_mile // 60)
        seconds = int(self.avg_pace_seconds_per_mile % 60)
        return f"{minutes}:{seconds:02d}/mile"


class ActivityFetcher:
    """
    Fetches activities from database for exact week boundaries.

    Does NOT transform data - only fetches and standardizes format.
    """

    def __init__(self, user_id: str, session: Session):
        """
        Initialize ActivityFetcher.

        Args:
            user_id: User UUID string
            session: SQLAlchemy database session
        """
        self.user_id = user_id
        self.session = session

    def fetch_week(self, week_start: date, week_end: date) -> List[ActivityRecord]:
        """
        Fetch activities for exact calendar week (Monday-Sunday).

        Args:
            week_start: Monday of the week
            week_end: Sunday of the week (should be week_start + 6 days)

        Returns:
            List of ActivityRecord objects, ordered by date ascending

        Note:
            Filters to activities where week_start <= date <= week_end
            Only returns activities of type "Run"
        """
        try:
            # Convert dates to datetime range (inclusive of entire end day)
            week_start_dt = datetime.combine(week_start, datetime.min.time())
            week_end_dt = datetime.combine(week_end, datetime.max.time())

            # Query activities table directly
            # Use v_completed_activities view if available, otherwise fall back to table
            query = text(
                """
                SELECT
                    a.activity_id,
                    a.name as activity_name,
                    DATE(a.start_date) as activity_date,
                    COALESCE(a.conv_distance, a.distance / 1609.34) as distance_miles,
                    a.moving_time as moving_time_seconds,
                    a.average_heartrate as avg_hr,
                    a.max_heartrate as max_hr,
                    a.average_speed,
                    a.hr_zone_1,
                    a.hr_zone_2,
                    a.hr_zone_3,
                    a.hr_zone_4,
                    a.hr_zone_5
                FROM activities a
                WHERE a.user_id = :user_id
                  AND a.type = 'Run'
                  AND a.start_date >= :week_start
                  AND a.start_date <= :week_end
                ORDER BY a.start_date ASC
            """
            )

            result = self.session.execute(
                query,
                {
                    "user_id": self.user_id,
                    "week_start": week_start_dt,
                    "week_end": week_end_dt,
                },
            ).fetchall()

            # Convert to ActivityRecord format
            activities = []
            for row in result:
                # Calculate pace from average_speed (m/s) -> seconds per mile
                avg_pace_sec_per_mile = None
                if row.average_speed and row.average_speed > 0:
                    # Convert m/s to seconds per mile
                    meters_per_mile = 1609.34
                    avg_pace_sec_per_mile = meters_per_mile / row.average_speed

                # Build HR zones dict if available
                hr_zones = None
                if any(
                    [
                        row.hr_zone_1,
                        row.hr_zone_2,
                        row.hr_zone_3,
                        row.hr_zone_4,
                        row.hr_zone_5,
                    ]
                ):
                    hr_zones = {}
                    if row.hr_zone_1 is not None:
                        hr_zones["z1"] = float(row.hr_zone_1)
                    if row.hr_zone_2 is not None:
                        hr_zones["z2"] = float(row.hr_zone_2)
                    if row.hr_zone_3 is not None:
                        hr_zones["z3"] = float(row.hr_zone_3)
                    if row.hr_zone_4 is not None:
                        hr_zones["z4"] = float(row.hr_zone_4)
                    if row.hr_zone_5 is not None:
                        hr_zones["z5"] = float(row.hr_zone_5)

                # Parse date
                activity_date = row.activity_date
                if isinstance(activity_date, str):
                    activity_date = datetime.fromisoformat(activity_date).date()
                elif isinstance(activity_date, datetime):
                    activity_date = activity_date.date()

                record = ActivityRecord(
                    date=activity_date,
                    activity_id=row.activity_id,
                    activity_name=row.activity_name,
                    distance_miles=(
                        float(row.distance_miles) if row.distance_miles else None
                    ),
                    avg_pace_seconds_per_mile=avg_pace_sec_per_mile,
                    avg_hr=int(row.avg_hr) if row.avg_hr else None,
                    max_hr=int(row.max_hr) if row.max_hr else None,
                    moving_time_seconds=(
                        int(row.moving_time_seconds)
                        if row.moving_time_seconds
                        else None
                    ),
                    hr_zones=hr_zones,
                )

                activities.append(record)

            return activities

        except Exception as e:
            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.MEDIUM,
                component="ActivityFetcher.fetch_week",
                user_id=self.user_id,
                metadata={
                    "week_start": str(week_start),
                    "week_end": str(week_end),
                },
            )
            return []

from datetime import datetime, timedelta
from sqlalchemy import func, extract, select
from src.db.models.activities import Activity
from sqlalchemy.orm import Session
from typing import List, Dict, Optional


class ActivityStatsDAO:

    @staticmethod
    def get_recent_activities(
        session: Session, athlete_id: int, days: int
    ) -> List[Activity]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(Activity)
            .where(
                Activity.athlete_id == athlete_id,
                Activity.type == "Run",
                Activity.start_date >= cutoff,
            )
            .order_by(Activity.start_date.desc())
        )
        return session.scalars(stmt).all()

    @staticmethod
    def get_activities_by_date_range(
        session: Session, athlete_id: int, start_date: datetime, end_date: datetime
    ) -> List[Activity]:
        stmt = (
            select(Activity)
            .where(
                Activity.athlete_id == athlete_id,
                Activity.type == "Run",
                Activity.start_date.between(start_date, end_date),
            )
            .order_by(Activity.start_date)
        )
        return session.scalars(stmt).all()

    @staticmethod
    def get_total_distance(
        session: Session, athlete_id: int, start_date: datetime, end_date: datetime
    ) -> float:
        stmt = select(func.sum(Activity.distance)).where(
            Activity.athlete_id == athlete_id,
            Activity.type == "Run",
            Activity.start_date.between(start_date, end_date),
        )
        return session.scalar(stmt) or 0.0

    @staticmethod
    def get_average_pace(
        session: Session, athlete_id: int, days: int
    ) -> Optional[float]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = select(
            func.avg(Activity.moving_time / (Activity.distance / 1000))
        ).where(
            Activity.athlete_id == athlete_id,
            Activity.type == "Run",
            Activity.start_date >= cutoff,
            Activity.distance > 0,
        )
        return session.scalar(stmt)

    @staticmethod
    def get_longest_run(
        session: Session, athlete_id: int, days: int
    ) -> Optional[Activity]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(Activity)
            .where(
                Activity.athlete_id == athlete_id,
                Activity.type == "Run",
                Activity.start_date >= cutoff,
            )
            .order_by(Activity.distance.desc())
            .limit(1)
        )
        return session.scalar(stmt)

    @staticmethod
    def get_fastest_run(
        session: Session, athlete_id: int, days: int
    ) -> Optional[Activity]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(Activity)
            .where(
                Activity.athlete_id == athlete_id,
                Activity.type == "Run",
                Activity.start_date >= cutoff,
                Activity.distance > 0,
            )
            .order_by((Activity.moving_time / (Activity.distance / 1000)).asc())
            .limit(1)
        )
        return session.scalar(stmt)

    @staticmethod
    def get_weekly_summary(
        session: Session, athlete_id: int, past_weeks: int = 4
    ) -> List[Dict]:
        cutoff = datetime.utcnow() - timedelta(weeks=past_weeks)
        stmt = (
            select(
                extract("year", Activity.start_date).label("year"),
                extract("week", Activity.start_date).label("week"),
                func.sum(Activity.distance).label("total_distance"),
                func.sum(Activity.moving_time).label("total_time"),
            )
            .where(
                Activity.athlete_id == athlete_id,
                Activity.type == "Run",
                Activity.start_date >= cutoff,
            )
            .group_by("year", "week")
            .order_by("year", "week")
        )
        return [dict(row._mapping) for row in session.execute(stmt)]

    @staticmethod
    def get_hr_zone_summary(
        session: Session, athlete_id: int, days: int
    ) -> Dict[str, float]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = select(
            func.avg(Activity.hr_zone_1),
            func.avg(Activity.hr_zone_2),
            func.avg(Activity.hr_zone_3),
            func.avg(Activity.hr_zone_4),
            func.avg(Activity.hr_zone_5),
        ).where(
            Activity.athlete_id == athlete_id,
            Activity.type == "Run",
            Activity.start_date >= cutoff,
        )
        row = session.execute(stmt).first()
        return {
            "zone_1": row[0] or 0.0,
            "zone_2": row[1] or 0.0,
            "zone_3": row[2] or 0.0,
            "zone_4": row[3] or 0.0,
            "zone_5": row[4] or 0.0,
        }

    @staticmethod
    def get_treadmill_vs_outdoor_stats(
        session: Session, athlete_id: int, days: int
    ) -> Dict[str, int]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = select(Activity.name).where(
            Activity.athlete_id == athlete_id,
            Activity.type == "Run",
            Activity.start_date >= cutoff,
        )
        runs = session.scalars(stmt).all()
        treadmill = sum(1 for r in runs if r and "treadmill" in r.lower())
        return {"treadmill": treadmill, "outdoor": len(runs) - treadmill}

    @staticmethod
    def get_runs_by_weekday(
        session: Session, athlete_id: int, days: int
    ) -> Dict[str, int]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(extract("dow", Activity.start_date), func.count())
            .where(
                Activity.athlete_id == athlete_id,
                Activity.type == "Run",
                Activity.start_date >= cutoff,
            )
            .group_by(extract("dow", Activity.start_date))
        )
        result = session.execute(stmt).all()
        return {str(int(day)): count for day, count in result}

    @staticmethod
    def get_time_of_day_stats(
        session: Session, athlete_id: int, days: int
    ) -> Dict[str, int]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = select(Activity.start_date).where(
            Activity.athlete_id == athlete_id,
            Activity.type == "Run",
            Activity.start_date >= cutoff,
        )
        results = session.scalars(stmt).all()
        morning = sum(1 for r in results if r and r.hour < 12)
        return {"morning": morning, "evening": len(results) - morning}

    @staticmethod
    def get_trend_metrics(
        session: Session, athlete_id: int, metric: str, window_size: int = 7
    ) -> List[Dict]:
        metric_col = getattr(Activity, metric, None)
        if not metric_col:
            raise ValueError(f"Invalid metric field: {metric}")

        cutoff = datetime.utcnow() - timedelta(days=window_size * 6)
        stmt = (
            select(
                func.date_trunc("week", Activity.start_date).label("week"),
                func.avg(metric_col).label("avg_metric"),
            )
            .where(
                Activity.athlete_id == athlete_id,
                Activity.type == "Run",
                Activity.start_date >= cutoff,
            )
            .group_by("week")
            .order_by("week")
        )
        return [dict(row._mapping) for row in session.execute(stmt)]

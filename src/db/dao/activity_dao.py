from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from src.db.models.activities import Activity
from src.utils.conversions import convert_metrics
from src.utils.logger import get_logger
from typing import List, Dict

logger = get_logger(__name__)

class ActivityDAO:
    @staticmethod
    def upsert_activities(session: Session, athlete_id: int, activities: List[Dict]) -> int:
        """
        Upsert activities into the database, filtering only 'Run' types.

        Args:
            session (Session): SQLAlchemy session object.
            athlete_id (int): ID of the athlete.
            activities (list): List of activity dicts from Strava.

        Returns:
            int: Number of rows affected.
        """
        if not activities:
            return 0

        rows = []
        for act in activities:
            if act.get("type") != "Run":
                logger.warning(f"⚠️ Skipping non-Run activity {act.get('id')} — type={act.get('type')}")
                continue

            name = act.get("name", "").lower()
            is_treadmill = "treadmill" in name

            required_fields = ["id", "start_date", "distance", "moving_time", "elapsed_time"]
            if not is_treadmill:
                required_fields.append("external_id")

            missing = [f for f in required_fields if not act.get(f)]
            if missing:
                logger.error(f"❌ Skipping activity {act.get('id')} due to missing required fields: {missing}")
                continue

            conv_input = {
                "distance": act.get("distance"),
                "elevation": act.get("total_elevation_gain"),
                "average_speed": act.get("average_speed"),
                "max_speed": act.get("max_speed"),
                "moving_time": act.get("moving_time"),
                "elapsed_time": act.get("elapsed_time")
            }
            conv_fields = ["distance", "elevation", "average_speed", "max_speed", "moving_time", "elapsed_time"]
            conv = convert_metrics(conv_input, conv_fields)

            row = {
                "activity_id": act["id"],
                "athlete_id": athlete_id,
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

        if not rows:
            return 0

        stmt = insert(Activity).values(rows)
        update_cols = {
            col.name: getattr(stmt.excluded, col.name)
            for col in Activity.__table__.columns
            if col.name != "activity_id"
        }
        stmt = stmt.on_conflict_do_update(index_elements=["activity_id"], set_=update_cols)

        result = session.execute(stmt)
        session.commit()
        return result.rowcount
    
    
    @staticmethod
    def get_by_id(session: Session, activity_id: int) -> Activity | None:
        """
        Retrieve a single activity by its activity_id.
        """
        return session.query(Activity).filter_by(activity_id=activity_id).first()

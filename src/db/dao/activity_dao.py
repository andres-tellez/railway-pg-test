from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from src.db.models.activities import Activity

def upsert_activities(session: Session, athlete_id: int, activities: list[dict]) -> int:
    if not activities:
        return 0

    stmt = insert(Activity).values([{
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
        "hr_zone_1": act.get("hr_zone_1"),  # ✅ Added enrichment field
    } for act in activities])

    update_cols = {
        "name": stmt.excluded.name,
        "type": stmt.excluded.type,
        "start_date": stmt.excluded.start_date,
        "distance": stmt.excluded.distance,
        "elapsed_time": stmt.excluded.elapsed_time,
        "moving_time": stmt.excluded.moving_time,
        "total_elevation_gain": stmt.excluded.total_elevation_gain,
        "external_id": stmt.excluded.external_id,
        "timezone": stmt.excluded.timezone,
        "hr_zone_1": stmt.excluded.hr_zone_1,  # ✅ Include on update
    }

    stmt = stmt.on_conflict_do_update(
        index_elements=["activity_id"],
        set_=update_cols
    )

    result = session.execute(stmt)
    session.commit()
    return result.rowcount

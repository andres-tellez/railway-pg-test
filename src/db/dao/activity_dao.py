from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from src.db.models.activities import Activity

def upsert_activities(session: Session, athlete_id: int, activities: list[dict]) -> int:
    if not activities:
        return 0

    rows = []
    for act in activities:
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
            "hr_zone_1": act.get("hr_zone_1"),  # Optional enrichment
        }
        rows.append(row)

    stmt = insert(Activity).values(rows)

    update_cols = {
        col.name: getattr(stmt.excluded, col.name)
        for col in Activity.__table__.columns
        if col.name not in ("activity_id",)
    }

    stmt = stmt.on_conflict_do_update(
        index_elements=["activity_id"],
        set_=update_cols
    )

    result = session.execute(stmt)
    session.commit()
    return result.rowcount

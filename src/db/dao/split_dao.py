from sqlalchemy.dialects.postgresql import insert
from src.db.models.splits import Split

def upsert_splits(session, splits: list) -> int:
    """
    Upserts multiple split records into the 'splits' table.
    Safely uses PostgreSQL's ON CONFLICT with SQLAlchemy Core.
    """
    if not splits:
        return 0

    stmt = insert(Split).values([
        {
            "activity_id": s["activity_id"],
            "lap_index": s["lap_index"],
            "distance": s["distance"],
            "elapsed_time": s["elapsed_time"],
            "moving_time": s["moving_time"],
            "average_speed": s["average_speed"],
            "max_speed": s["max_speed"],
            "start_index": s["start_index"],
            "end_index": s["end_index"],
            "split": s["split"],
            "average_heartrate": s.get("average_heartrate"),
            "pace_zone": s.get("pace_zone"),
            "conv_distance": s.get("conv_distance"),
            "conv_avg_speed": s.get("conv_avg_speed"),
            "conv_moving_time": s.get("conv_moving_time"),
            "conv_elapsed_time": s.get("conv_elapsed_time"),
        }
        for s in splits
    ])

    update_map = {col.name: getattr(stmt.excluded, col.name) for col in Split.__table__.columns if col.name not in ("activity_id", "lap_index")}

    stmt = stmt.on_conflict_do_update(
        index_elements=["activity_id", "lap_index"],
        set_=update_map
    )

    result = session.execute(stmt)
    session.commit()
    return result.rowcount

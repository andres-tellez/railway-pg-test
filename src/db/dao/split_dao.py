# src/db/dao/split_dao.py

from sqlalchemy.dialects.postgresql import insert
from src.db.models.splits import Split

def upsert_splits(session, splits: list) -> int:
    """
    Upserts splits into the 'splits' table using SQLAlchemy ORM session.
    Fully safe for PostgreSQL transactions (uses flush/commit correctly).
    """
    if not splits:
        return 0

    stmt = insert(Split).values([{
            "activity_id": split["activity_id"],
            "lap_index": split["lap_index"],
            "distance": split["distance"],
            "elapsed_time": split["elapsed_time"],
            "moving_time": split["moving_time"],
            "average_speed": split["average_speed"],
            "max_speed": split["max_speed"],
            "start_index": split["start_index"],
            "end_index": split["end_index"],
            "split": split["split"]
        } for split in splits])

    # Define conflict resolution
    update_cols = {
        "lap_index": stmt.excluded.lap_index,
        "distance": stmt.excluded.distance,
        "elapsed_time": stmt.excluded.elapsed_time,
        "moving_time": stmt.excluded.moving_time,
        "average_speed": stmt.excluded.average_speed,
        "max_speed": stmt.excluded.max_speed,
        "start_index": stmt.excluded.start_index,
        "end_index": stmt.excluded.end_index,
        "split": stmt.excluded.split
    }

    stmt = stmt.on_conflict_do_update(
        index_elements=["activity_id", "lap_index"],
        set_=update_cols
    )

    result = session.execute(stmt)
    session.commit()  # Ensure commit here after split insertions
    return result.rowcount

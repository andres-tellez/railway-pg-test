from sqlalchemy.dialects.postgresql import insert
from src.db.models.splits import Split
from src.utils.conversions import convert_metrics


def upsert_splits(session, splits: list) -> int:
    """
    Upserts multiple split records into the 'splits' table.
    Applies conversion logic centrally before inserting.
    Ensures 'split' field is consistently a valid integer type.
    """
    if not splits:
        return 0

    converted = []
    for s in splits:
        # Ensure 'split' is a true int, not a bool or invalid type
        split_raw = s.get("split")
        split_value = None
        if split_raw is not None:
            if isinstance(split_raw, bool):
                split_value = 1 if split_raw else 0
            elif isinstance(split_raw, (int, float, str)):
                try:
                    split_value = int(split_raw)
                except (ValueError, TypeError):
                    split_value = None  # fallback for invalid string etc.

        conv_fields = ["distance", "average_speed", "moving_time", "elapsed_time"]
        conv_data = {
            "distance": s.get("distance"),
            "average_speed": s.get("average_speed"),
            "moving_time": s.get("moving_time"),
            "elapsed_time": s.get("elapsed_time"),
        }
        enriched = convert_metrics(conv_data, conv_fields)

        converted.append(
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
                "split": split_value,
                "average_heartrate": s.get("average_heartrate"),
                "pace_zone": s.get("pace_zone"),
                "conv_distance": enriched.get("conv_distance"),
                "conv_avg_speed": enriched.get("conv_avg_speed"),
                "conv_moving_time": enriched.get("conv_moving_time"),
                "conv_elapsed_time": enriched.get("conv_elapsed_time"),
            }
        )

    # 🔍 Debug output to verify types
    print(
        f"[DAO DEBUG] split values: {[row['split'] for row in converted]} | types: {[type(row['split']) for row in converted]}"
    )

    stmt = insert(Split).values(converted)

    update_map = {
        col.name: getattr(stmt.excluded, col.name)
        for col in Split.__table__.columns
        if col.name not in ("activity_id", "lap_index")
    }

    stmt = stmt.on_conflict_do_update(
        index_elements=["activity_id", "lap_index"], set_=update_map
    )

    result = session.execute(stmt)
    session.commit()
    return result.rowcount

# src/services/split_extraction.py

def extract_splits(activity):
    """
    Parse splits from Strava activity object.

    Accepts:
      - activity (dict): full activity object

    Returns list of dicts ready for DAO upsert.
    """
    activity_id = activity.get("id")
    laps = activity.get("splits_metric")

    if not laps:
        return []

    splits = []
    for lap in laps:
        split_value = lap.get("split", True)
        split_bool = bool(split_value) if split_value is not None else True

        split_data = {
            "activity_id": activity_id,
            "lap_index": lap.get("lap_index") or lap.get("split"),  # allow both keys for safety
            "distance": lap.get("distance"),
            "elapsed_time": lap.get("elapsed_time"),
            "moving_time": lap.get("moving_time"),
            "average_speed": lap.get("average_speed"),
            "max_speed": lap.get("max_speed"),
            "start_index": lap.get("start_index"),
            "end_index": lap.get("end_index"),
            "split": split_bool
        }
        splits.append(split_data)

    return splits

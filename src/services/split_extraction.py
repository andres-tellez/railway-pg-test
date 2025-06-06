# src/services/split_extraction.py

def extract_splits(activity):
    """
    Parse splits from Strava activity object.

    Fully normalized to match Strava UI:
    - Uses splits_standard
    - Normalizes pace based on elapsed_time / conv_distance
    - Preserves average_heartrate
    """

    activity_id = activity.get("id")
    laps = activity.get("splits_standard")  # ✅ critical — full mile splits

    if not laps:
        return []

    splits = []
    for lap in laps:
        split_value = lap.get("split", True)
        split_bool = bool(split_value) if split_value is not None else True

        # Normalize distance into miles
        distance_meters = lap.get("distance")
        conv_distance = round(distance_meters / 1609.344, 2) if distance_meters else None

        # Compute pace exactly matching Strava (elapsed_time / conv_distance)
        elapsed_time = lap.get("elapsed_time")
        if elapsed_time and conv_distance:
            pace_seconds = elapsed_time / conv_distance
            pace_minutes, pace_secs = divmod(pace_seconds, 60)
            conv_avg_speed = f"{int(pace_minutes)}:{int(pace_secs):02}"
        else:
            conv_avg_speed = None

        split_data = {
            "activity_id": activity_id,
            "lap_index": lap.get("lap_index") or lap.get("split"),
            "distance": distance_meters,
            "elapsed_time": elapsed_time,
            "moving_time": lap.get("moving_time"),
            "average_speed": lap.get("average_speed"),
            "max_speed": lap.get("max_speed"),
            "start_index": lap.get("start_index"),
            "end_index": lap.get("end_index"),
            "split": split_bool,

            # ✅ Preserve heart rate and pace zone directly
            "average_heartrate": lap.get("average_heartrate"),
            "pace_zone": lap.get("pace_zone"),

            # ✅ Normalized conversions
            "conv_distance": conv_distance,
            "conv_avg_speed": conv_avg_speed,
            "conv_moving_time": _format_seconds_to_hms(lap.get("moving_time")),
            "conv_elapsed_time": _format_seconds_to_hms(elapsed_time)
        }
        splits.append(split_data)

    return splits

# --- helper function for time formatting
def _format_seconds_to_hms(seconds):
    if seconds is None:
        return None
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}:{minutes:02}:{sec:02}"
    else:
        return f"{minutes}:{sec:02}"

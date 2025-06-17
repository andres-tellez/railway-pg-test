def meters_to_miles(meters):
    return round(meters / 1609.344, 2) if meters is not None else None

def meters_to_feet(meters):
    return round(meters * 3.28084, 1) if meters is not None else None

def mps_to_min_per_mile(mps):
    return round(26.8224 / mps, 2) if mps and mps > 0 else None

def format_seconds_to_hms(seconds):
    if seconds is None:
        return None
    try:
        seconds = int(seconds)
    except (ValueError, TypeError):
        return None
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02}:{sec:02}" if hours > 0 else f"{minutes}:{sec:02}"

def safe_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def safe_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return None

def convert_metrics(data: dict, fields: list[str]) -> dict:
    conversions = {}
    if "distance" in fields:
        conversions["conv_distance"] = meters_to_miles(safe_float(data.get("distance")))
    if "elevation" in fields:
        conversions["conv_elevation_feet"] = meters_to_feet(safe_float(data.get("elevation")))
    if "average_speed" in fields:
        conversions["conv_avg_speed"] = mps_to_min_per_mile(safe_float(data.get("average_speed")))
    if "max_speed" in fields:
        conversions["conv_max_speed"] = mps_to_min_per_mile(safe_float(data.get("max_speed")))
    if "moving_time" in fields:
        conversions["conv_moving_time"] = format_seconds_to_hms(safe_int(data.get("moving_time")))
    if "elapsed_time" in fields:
        conversions["conv_elapsed_time"] = format_seconds_to_hms(safe_int(data.get("elapsed_time")))
    return conversions

from src.db.models.activities import Activity
from src.services.strava_client import StravaClient  # ✅ Fully centralized import

def pull_activity_from_strava(activity_id, athlete_id):
    """
    Fetch activity JSON from Strava using centralized client.
    """
    strava = StravaClient(athlete_id)
    activity_json = strava.get_activity(activity_id, include_all_efforts=True)
    return activity_json

def insert_activity_into_db(session, activity_json):
    """
    Insert activity into DB from JSON response.
    """
    activity = Activity(
        activity_id=activity_json["id"],
        athlete_id=activity_json["athlete"]["id"],
        name=activity_json["name"],
        type=activity_json["type"],
        start_date=activity_json["start_date"],
        distance=activity_json.get("distance"),
        elapsed_time=activity_json.get("elapsed_time"),
        moving_time=activity_json.get("moving_time"),
        total_elevation_gain=activity_json.get("total_elevation_gain"),
        external_id=activity_json.get("external_id"),
        timezone=activity_json.get("timezone"),
        average_speed=activity_json.get("average_speed"),
        max_speed=activity_json.get("max_speed"),
        suffer_score=activity_json.get("suffer_score"),
        average_heartrate=activity_json.get("average_heartrate"),
        max_heartrate=activity_json.get("max_heartrate"),
        calories=activity_json.get("calories"),
    )

    session.add(activity)
    session.commit()
    return activity.athlete_id

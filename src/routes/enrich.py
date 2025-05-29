# src/routes/enrich.py

from flask import Blueprint, jsonify, current_app
from strava_platform.strava import enrich_activity, backfill_activities
from src.db.base_model import get_session

enrich_bp = Blueprint("enrich", __name__)

@enrich_bp.route("/status", methods=["GET"])
def status():
    """Quick check that enrich blueprint is active."""
    return jsonify({"enrich": "up"}), 200

@enrich_bp.route("/activity/<int:activity_id>", methods=["POST"])
def enrich_single(activity_id):
    """Fetch detailed data for one Strava activity."""
    result = enrich_activity(activity_id, key=current_app.config["CRON_SECRET_KEY"])
    return jsonify(result), 200

@enrich_bp.route("/backfill", methods=["POST"])
def backfill():
    """Enrich all past activities since a given date."""
    params = {}  # pull args like 'since' from request.args if you want
    count = backfill_activities(**params)
    return jsonify({"backfilled": count}), 200

def enrich_activity_pg(activity_id, activity_json):
    """
    Update the activity record in the database with enriched Strava fields.
    """
    session = get_session()

    session.execute(
        """
        UPDATE activities
        SET name = :name,
            distance = :distance,
            moving_time = :moving_time,
            elapsed_time = :elapsed_time,
            total_elevation_gain = :elevation,
            type = :type,
            workout_type = :workout_type,
            average_speed = :avg_speed,
            max_speed = :max_speed,
            suffer_score = :suffer_score
        WHERE activity_id = :activity_id
        """,
        {
            "activity_id": activity_id,
            "name": activity_json.get("name"),
            "distance": activity_json.get("distance"),
            "moving_time": activity_json.get("moving_time"),
            "elapsed_time": activity_json.get("elapsed_time"),
            "elevation": activity_json.get("total_elevation_gain"),
            "type": activity_json.get("type"),
            "workout_type": activity_json.get("workout_type"),
            "avg_speed": activity_json.get("average_speed"),
            "max_speed": activity_json.get("max_speed"),
            "suffer_score": activity_json.get("suffer_score"),
        }
    )
    session.commit()

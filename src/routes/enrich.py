# src/routes/enrich.py

from flask import Blueprint, jsonify, current_app
from src.platform.strava import enrich_activity, backfill_activities


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

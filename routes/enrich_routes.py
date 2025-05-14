from flask import Blueprint, jsonify, request
import os
from services.activity_enrichment import enrich_batch

ENRICH   = Blueprint("enrich", __name__)
CRON_KEY = os.getenv("CRON_SECRET_KEY")

@ENRICH.route("/enrich-activities/<int:athlete_id>")
def enrich_activities(athlete_id):
    key    = request.args.get("key")
    limit  = int(request.args.get("limit", 10))
    offset = int(request.args.get("offset", 0))

    # Auth
    if CRON_KEY and key != CRON_KEY:
        return jsonify(error="Unauthorized"), 401

    # Delegate to service
    try:
        enriched, processed, next_offset = enrich_batch(
            athlete_id, key, limit, offset,
            os.getenv("STRAVA_CLIENT_ID"),
            os.getenv("STRAVA_CLIENT_SECRET")
        )
    except LookupError:
        return jsonify(error="No tokens for that athlete"), 404

    return jsonify(
        enriched= enriched,
        processed=processed,
        offset=next_offset
    ), 200

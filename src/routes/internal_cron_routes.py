"""
Internal endpoints for scheduled jobs (Railway cron, etc.).

Protected by a shared secret header — not user JWT auth.
"""

import os
import logging

from flask import Blueprint, request

from src.services.strava_sync_retry_service import process_due_strava_ingestion_retries

logger = logging.getLogger(__name__)

internal_cron_bp = Blueprint("internal_cron", __name__, url_prefix="/api/internal/cron")


def _check_processor_key() -> bool:
    expected = (os.getenv("STRAVA_INGESTION_RETRY_PROCESSOR_KEY") or "").strip()
    if not expected:
        return False
    got = (request.headers.get("X-Strava-Retry-Processor-Key") or "").strip()
    return got == expected


@internal_cron_bp.post("/strava/process-ingestion-retries")
def process_strava_ingestion_retries():
    """
    Claim due `strava_ingestion_retry` rows and start background ingestion.

    Configure Railway (or similar) to POST here every 1–2 minutes.

    Headers:
        X-Strava-Retry-Processor-Key: must match env STRAVA_INGESTION_RETRY_PROCESSOR_KEY

    Optional JSON body: { "limit": 10 }
    """
    if not _check_processor_key():
        return {
            "error": "Unauthorized",
            "hint": "Set STRAVA_INGESTION_RETRY_PROCESSOR_KEY",
        }, 401

    body = request.get_json(silent=True) or {}
    raw_limit = body.get("limit", 10)
    try:
        limit = max(1, min(int(raw_limit), 50))
    except (TypeError, ValueError):
        limit = 10

    started = process_due_strava_ingestion_retries(limit=limit)
    return {"started": started}, 200

"""Authenticated batch ingest for client-emitted product analytics (mobile MVP)."""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request, g

from src.services.product_analytics_service import record_product_event
from src.utils.auth0_jwt import requires_auth

logger = logging.getLogger(__name__)

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")

_MAX_EVENTS = 50


@analytics_bp.route("/events", methods=["POST"])
@requires_auth
def post_product_events():
    if not request.is_json:
        return jsonify({"error": "expected application/json"}), 400
    body = request.get_json(silent=True) or {}
    events = body.get("events")
    if not isinstance(events, list) or not events:
        return jsonify({"error": "events must be a non-empty array"}), 400
    if len(events) > _MAX_EVENTS:
        return jsonify({"error": f"at most {_MAX_EVENTS} events per request"}), 400

    uid = str(getattr(g, "user_id", "") or "")
    accepted = 0
    for raw in events:
        if not isinstance(raw, dict):
            continue
        name = raw.get("event_name") or raw.get("name")
        outcome = raw.get("outcome")
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(outcome, str) or not outcome.strip():
            continue
        props = raw.get("properties")
        if props is not None and not isinstance(props, dict):
            props = {"_invalid_properties": "not_object"}
        cid = raw.get("correlation_id") or raw.get("client_correlation_id")
        eid = raw.get("client_event_id") or raw.get("id")
        record_product_event(
            event_name=name.strip(),
            outcome=outcome.strip(),
            user_id=uid,
            source="client",
            correlation_id=str(cid).strip()[:120] if cid else None,
            client_event_id=str(eid).strip()[:120] if eid else None,
            properties=props if isinstance(props, dict) else None,
        )
        accepted += 1

    return jsonify({"ok": True, "accepted": accepted}), 200

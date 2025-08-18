# src/services/user_identity_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from flask import session as flask_session

from src.db.dao.user_identity_dao import get_by_user_id, upsert_identity


def _parse_updated_at(claims: Dict[str, Any]) -> datetime:
    """
    Try to parse 'updated_at' from token claims; fall back to now() if missing.
    Accepts ISO strings with or without 'Z'.
    """
    raw = claims.get("updated_at")
    if not raw:
        return datetime.now(timezone.utc)
    try:
        # Normalize trailing 'Z' to +00:00 for fromisoformat
        if isinstance(raw, str) and raw.endswith("Z"):
            raw = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(raw)
    except Exception:
        return datetime.now(timezone.utc)


def _row_to_dict(row) -> Dict[str, Any]:
    """
    SQLAlchemy Row -> dict (works whether it's Row or RowMapping).
    """
    if not row:
        return {}
    m = getattr(row, "_mapping", None)
    return dict(m) if m is not None else dict(row)


def get_or_create_user_identity(claims: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orchestrates 'who am I':
      - ensure a row exists in user_identity for this Auth0 sub
      - update profile fields if provided
      - return a minimal JSON-safe dict our route can send back
    """
    sub = claims.get("sub")
    if not sub:
        raise ValueError("Token missing 'sub' (user id)")

    # Token may expose fields directly or under a nested 'raw'
    raw = claims.get("raw") or claims
    payload = {
        "user_id": sub,
        "email": raw.get("email"),
        "email_verified": raw.get("email_verified"),
        "name": raw.get("name"),
        "picture": raw.get("picture"),
        "updated_at": _parse_updated_at(raw),
    }

    # One write, no extra reads: DAO returns the row after upsert
    row = upsert_identity(payload)

    # Extremely defensive: if the upsert didn't return a row, re-read once
    if not row:
        row = get_by_user_id(sub)

    data = _row_to_dict(row)

    # Roles/permissions can come later; keep the field present for the UI
    roles = raw.get("permissions") or []
    data.setdefault("roles", roles)

    # Ensure updated_at is JSON-friendly
    ua = data.get("updated_at")
    if isinstance(ua, datetime):
        data["updated_at"] = ua.isoformat()

    # ✅ Set session for downstream authentication (e.g. /auth/whoami)
    flask_session["athlete_id"] = data.get("user_id") or sub

    return {
        "user_id": data.get("user_id") or sub,
        "email": data.get("email"),
        "email_verified": (
            bool(data.get("email_verified"))
            if data.get("email_verified") is not None
            else None
        ),
        "name": data.get("name"),
        "picture": data.get("picture"),
        "updated_at": data.get("updated_at"),
        "roles": data.get("roles", []),
    }

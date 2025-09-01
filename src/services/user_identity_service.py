# src/services/user_identity_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from flask import request

from src.routes.user_identity_routes import fetch_userinfo_from_auth0
from src.db.dao.user_identity_dao import get_by_user_id, upsert_identity
from src.db.dao.user_profile_dao import exists_user_profile
from src.db.dao.user_athletes_dao import get_by_user_id


def _parse_updated_at(claims: Dict[str, Any]) -> datetime:
    raw = claims.get("updated_at")
    if not raw:
        return datetime.now(timezone.utc)
    try:
        if isinstance(raw, str) and raw.endswith("Z"):
            raw = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(raw)
    except Exception:
        return datetime.now(timezone.utc)


def _row_to_dict(row) -> Dict[str, Any]:
    if not row:
        return {}
    m = getattr(row, "_mapping", None)
    return dict(m) if m is not None else dict(row)


def get_or_create_user_identity(claims: Dict[str, Any]) -> Dict[str, Any]:
    sub = claims.get("sub")
    if not sub:
        raise ValueError("Token missing 'sub' (user id)")

    # Use raw claims if present
    raw = claims.get("raw") or claims

    # If critical fields are missing, fetch from Auth0
    if not all(k in raw for k in ("email", "email_verified", "name", "picture")):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.split(" ")[1] if " " in auth_header else auth_header
        raw = fetch_userinfo_from_auth0(token)

    payload = {
        "user_id": sub,
        "email": raw.get("email"),
        "email_verified": raw.get("email_verified"),
        "name": raw.get("name"),
        "picture": raw.get("picture"),
        "updated_at": _parse_updated_at(raw),
    }

    row = upsert_identity(payload)
    if not row:
        row = get_by_user_id(sub)

    data = _row_to_dict(row)
    roles = raw.get("permissions") or []
    data.setdefault("roles", roles)

    ua = data.get("updated_at")
    if isinstance(ua, datetime):
        data["updated_at"] = ua.isoformat()

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


def get_user_status(user_id: str) -> dict:
    has_onboarded = exists_user_profile(user_id)
    has_strava = get_by_user_id(user_id) is not None
    return {
        "hasOnboarded": has_onboarded,
        "hasStrava": has_strava,
    }

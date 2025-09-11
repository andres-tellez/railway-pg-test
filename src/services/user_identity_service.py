# src/services/user_identity_service.py
from __future__ import annotations
import requests
from datetime import datetime

from sqlalchemy import select

from src.utils.config import config
from src.db.db_session import db, get_session
from src.db.models import UserIdentity
from src.db.models.user_profile import user_profile_table
from src.db.dao.user_athletes_dao import get_by_user_id

from src.db.dao.user_identity_dao import (
    upsert_identity,
    resolve_user_id_from_auth_provider,  # ✅ use this version only
)


def fetch_userinfo_from_auth0(token: str) -> dict:
    resp = requests.get(
        f"https://{config.AUTH0_DOMAIN}/userinfo",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


def upsert_user_identity_from_userinfo(userinfo: dict) -> dict:
    sub = userinfo.get("sub")
    if not sub:
        return {"ok": False, "error": "missing_sub"}

    # 🔑 allow creation if missing
    user_id = resolve_user_id_from_auth_provider(sub, userinfo, create_if_missing=True)

    payload = {
        "user_id": user_id,
        "email": userinfo.get("email"),
        "email_verified": userinfo.get("email_verified"),
        "name": userinfo.get("name"),
        "picture": userinfo.get("picture"),
        "updated_at": datetime.utcnow(),
    }

    upsert_identity(payload)
    return {"ok": True, "user_id": str(user_id)}


def get_user_status(user_id: str) -> dict:
    session = get_session()
    try:
        has_onboarded = (
            session.execute(
                select(user_profile_table).where(
                    user_profile_table.c.user_id == user_id
                )
            ).first()
            is not None
        )
        link = get_by_user_id(user_id)
        has_strava = link is not None
        return {"hasOnboarded": has_onboarded, "hasStrava": has_strava}
    finally:
        session.close()

# src/services/user_identity_service.py
from __future__ import annotations
import requests
from flask import g
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.utils import config
from src.db.db_session import db
from src.db.models import UserIdentity
from src.db.dao.user_athletes_dao import get_by_user_id  # if you need it here


def fetch_userinfo_from_auth0(token: str) -> dict:
    resp = requests.get(
        f"https://{config.AUTH0_DOMAIN}/userinfo",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


def upsert_user_identity_from_userinfo(userinfo: dict) -> dict:
    try:
        print("⚠️ Received userinfo:", userinfo)

        user_id = userinfo["sub"]
        email = userinfo.get("email")
        email_verified = userinfo.get("email_verified")
        name = userinfo.get("name")
        picture = userinfo.get("picture")

        stmt = (
            pg_insert(UserIdentity)
            .values(
                user_id=user_id,
                email=email,
                email_verified=email_verified,
                name=name,
                picture=picture,
            )
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "email": email,
                    "email_verified": email_verified,
                    "name": name,
                    "picture": picture,
                },
            )
        )

        db.session.execute(stmt)
        db.session.commit()

        print(f"✅ Successfully upserted identity for user_id={user_id}")
        return {"ok": True, "user_id": user_id}

    except Exception as e:
        # 🔥 Full traceback
        import traceback

        traceback.print_exc()

        print("❌ Failed to upsert user identity")
        print("📦 Payload was:", userinfo)
        print("🐞 Error:", str(e))

        return {"ok": False, "error": str(e)}


def get_or_create_user_identity(claims: dict) -> dict:
    """
    Load from DB if exists; otherwise create a minimal record from claims.
    Expand with your existing logic as needed.
    """
    user_id = (claims or {}).get("sub")
    row: UserIdentity | None = db.session.get(UserIdentity, user_id)
    if not row:
        row = UserIdentity(
            user_id=user_id,
            email=claims.get("email"),
            name=claims.get("name"),
            picture=claims.get("picture"),
            email_verified=claims.get("email_verified"),
        )
        db.session.add(row)
        db.session.commit()
    return row.to_dict()


def get_user_status(user_id: str) -> dict:
    """Return flags used by the dashboard (hasOnboarded, hasStrava, etc.)."""
    # Minimal example; wire into your DAOs/services as needed.
    identity: UserIdentity | None = db.session.get(UserIdentity, user_id)
    return {
        "name": identity.name if identity else "",
        "email": identity.email if identity else "",
        "picture": identity.picture if identity else "",
        "hasOnboarded": bool(identity and identity.name),
        "hasStrava": bool(get_by_user_id(user_id)),  # if you map user->athlete
    }

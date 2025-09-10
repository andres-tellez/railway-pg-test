# src/services/user_identity_service.py
from __future__ import annotations
import sys
import requests
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.utils.config import config
from src.db.db_session import db
from src.db.models import UserIdentity, UserAuthProvider
from src.db.db_session import get_session
from src.db.models.user_profile import user_profile_table
from src.db.dao.user_athletes_dao import get_by_user_id  # used in get_user_status


def fetch_userinfo_from_auth0(token: str) -> dict:
    resp = requests.get(
        f"https://{config.AUTH0_DOMAIN}/userinfo",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


def resolve_user_id_from_auth_provider(sub: str) -> str:
    """
    Return our internal user_id for an external Auth0/Google `sub`.
    If no mapping exists, generate a new user_id but DON'T insert mapping yet.
    (FK requires user_identity to exist first.)
    """
    existing = db.session.execute(
        select(UserAuthProvider.user_id).where(UserAuthProvider.provider_user_id == sub)
    ).first()
    if existing:
        return existing.user_id
    return str(uuid4())


def upsert_user_identity_from_userinfo(userinfo: dict) -> dict:
    try:
        print("⚠️ Received userinfo:", userinfo)
        sys.stdout.flush()

        sub = userinfo.get("sub")
        if not sub:
            raise ValueError("Missing `sub` in userinfo")

        user_id = resolve_user_id_from_auth_provider(sub)
        email = userinfo.get("email")
        email_verified = userinfo.get("email_verified")
        name = userinfo.get("name")
        picture = userinfo.get("picture")

        # 1) Upsert user_identity first (NOT NULL updated_at)
        stmt = (
            pg_insert(UserIdentity)
            .values(
                user_id=user_id,
                email=email,
                email_verified=email_verified,
                name=name,
                picture=picture,
                updated_at=func.now(),
            )
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "email": email,
                    "email_verified": email_verified,
                    "name": name,
                    "picture": picture,
                    "updated_at": func.now(),
                },
            )
        )
        db.session.execute(stmt)

        # 2) Ensure provider mapping exists (column names match your DDL)
        provider_name = sub.split("|", 1)[0]
        mapping_stmt = (
            pg_insert(UserAuthProvider)
            .values(
                user_id=user_id,
                provider_name=provider_name,
                provider_user_id=sub,
                full_provider_id=sub,
            )
            .on_conflict_do_nothing()
        )
        db.session.execute(mapping_stmt)

        db.session.commit()
        print(f"✅ Successfully upserted identity for user_id={user_id}")
        return {"ok": True, "user_id": user_id}

    except Exception as e:
        import traceback

        traceback.print_exc()
        print("❌ Failed to upsert user identity")
        print("📦 Payload was:", userinfo)
        print("🐞 Error:", str(e))
        db.session.rollback()
        return {"ok": False, "error": str(e)}


def get_or_create_user_identity(claims: dict) -> dict:
    """
    Load from DB if exists; otherwise create a minimal record from claims.
    """
    sub = (claims or {}).get("sub")
    if not sub:
        raise ValueError("Missing `sub` in claims")

    user_id = resolve_user_id_from_auth_provider(sub)

    row: UserIdentity | None = db.session.get(UserIdentity, user_id)
    if not row:
        row = UserIdentity(
            user_id=user_id,
            email=claims.get("email"),
            name=claims.get("name"),
            picture=claims.get("picture"),
            email_verified=claims.get("email_verified"),
            updated_at=func.now(),  # keep in sync with schema
        )
        db.session.add(row)

        # mirror mapping creation so this path behaves like the main upsert
        provider_name = sub.split("|", 1)[0]
        db.session.execute(
            pg_insert(UserAuthProvider)
            .values(
                user_id=user_id,
                provider_name=provider_name,
                provider_user_id=sub,
                full_provider_id=sub,
            )
            .on_conflict_do_nothing()
        )
        db.session.commit()

    return row.to_dict()


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

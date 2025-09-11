import uuid
from datetime import datetime
from typing import Mapping, Any, Optional, Dict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.db.db_session import get_session
from src.db.models.user_identity import UserIdentity
from src.db.models.user_auth_providers import UserAuthProvider


def get_by_user_id(user_id: str) -> Optional[UserIdentity]:
    db = get_session()
    return db.query(UserIdentity).filter(UserIdentity.user_id == user_id).first()


def upsert_identity(payload: Mapping[str, Any]):
    now = datetime.utcnow()
    data = {
        "user_id": payload["user_id"],  # required UUID
        "email": payload.get("email"),
        "email_verified": payload.get("email_verified"),
        "name": payload.get("name"),
        "picture": payload.get("picture"),
        "updated_at": payload.get("updated_at") or now,
    }

    # Ensure we don’t violate the constraint
    if not data["email"] and not data["name"]:
        data["name"] = "Anonymous User"

    db = get_session()
    stmt = (
        insert(UserIdentity)
        .values(**data)
        .on_conflict_do_update(
            index_elements=["user_id"],
            set_={
                "email": data["email"],
                "email_verified": data["email_verified"],
                "name": data["name"],
                "picture": data["picture"],
                "updated_at": data["updated_at"],
            },
        )
        .returning(UserIdentity)
    )
    result = db.execute(stmt).first()
    db.commit()
    return result


def get_by_email(email: str) -> Optional[UserIdentity]:
    db = get_session()
    return db.query(UserIdentity).filter(UserIdentity.email == email).first()


def resolve_user_id_from_auth_provider(
    sub: str, userinfo: Optional[Dict[str, Any]] = None, create_if_missing: bool = False
) -> Optional[uuid.UUID]:
    """
    Resolve internal user_id from an Auth0 `sub`.
    If `create_if_missing=True`, will insert UserIdentity + UserAuthProvider.
    Otherwise, returns None if no mapping exists.
    """
    if not sub:
        return None

    db = get_session()
    provider_name, provider_user_id = sub.split("|")

    # ✅ Lookup
    existing = db.execute(
        select(UserAuthProvider.user_id).where(
            UserAuthProvider.provider_name == provider_name,
            UserAuthProvider.provider_user_id == provider_user_id,
        )
    ).scalar()
    if existing:
        return existing

    # 🚫 Read-only mode
    if not create_if_missing:
        return None

    # ✅ Write mode: create user_identity + auth_provider link
    user_id = uuid.uuid4()
    db.execute(
        insert(UserIdentity).values(
            user_id=user_id,
            email=userinfo.get("email") if userinfo else None,
            email_verified=userinfo.get("email_verified") if userinfo else None,
            name=(userinfo.get("name") if userinfo else "Anonymous User"),
            picture=userinfo.get("picture") if userinfo else None,
            updated_at=datetime.utcnow(),
        )
    )

    db.execute(
        insert(UserAuthProvider)
        .values(
            user_id=user_id,
            full_provider_id=sub,
            provider_name=provider_name,
            provider_user_id=provider_user_id,
        )
        .on_conflict_do_nothing()
    )

    db.commit()
    return user_id

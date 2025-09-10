# src/db/dao/user_identity_dao.py
import uuid
from datetime import datetime
from typing import Mapping, Any, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.db.db_session import get_session
from src.db.models.user_identity import UserIdentity
from src.db.models.user_auth_providers import UserAuthProvider


def get_by_user_id(user_id: str) -> Optional[UserIdentity]:
    """
    Return the row for this internal user_id (UUID), or None if not found.
    """
    db = get_session()
    return db.query(UserIdentity).filter(UserIdentity.user_id == user_id).first()


def upsert_identity(payload: Mapping[str, Any]):
    """
    Insert or update user_identity for the given payload.
    Returns the inserted/updated row.
    Allowed keys: user_id, email, email_verified, name, picture, updated_at (datetime or None)
    """
    now = datetime.utcnow()
    data = {
        "user_id": payload["user_id"],  # required UUID
        "email": payload.get("email"),
        "email_verified": payload.get("email_verified"),
        "name": payload.get("name"),
        "picture": payload.get("picture"),
        "updated_at": payload.get("updated_at") or now,
    }

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


def get_or_create_internal_user_id(sub: str) -> uuid.UUID:
    """
    Ensure there is an internal UUID for this Auth0 `sub`.
    Looks in user_auth_providers; if none, creates a new mapping.
    Returns the UUID.
    """
    db = get_session()

    # Look up mapping
    row = db.execute(
        select(UserAuthProvider.user_id).where(UserAuthProvider.full_provider_id == sub)
    ).first()
    if row:
        return row[0]

    # No mapping → generate new internal UUID
    new_uuid = uuid.uuid4()

    # Insert into mapping table
    stmt = insert(UserAuthProvider).values(
        user_id=new_uuid,
        full_provider_id=sub,
    )
    db.execute(stmt)
    db.commit()

    return new_uuid

# src/db/dao/user_identity_dao.py
from datetime import datetime
from typing import Mapping, Any
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.db.db_session import get_session
from src.db.models.user_identity import UserIdentity


def get_by_user_id(user_id: str):
    """
    Return the row for this user_id, or None if not found.
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
        "user_id": payload["user_id"],  # required
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

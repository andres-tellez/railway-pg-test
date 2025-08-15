# src/db/dao/user_identity_dao.py
from datetime import datetime
from typing import Optional, Mapping, Any
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.db.db_session import get_engine
from src.db.models.user_identity import user_identity


def get_by_user_id(user_id: str):
    """
    Return the row for this user_id, or None if not found.
    Returns a SQLAlchemy Row (RowMapping-like).
    """
    engine = get_engine()
    with engine.begin() as conn:
        res = conn.execute(
            select(user_identity).where(user_identity.c.user_id == user_id)
        ).first()
        return res


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
        # Prefer caller-supplied updated_at (from token) if parseable, else now
        "updated_at": payload.get("updated_at") or now,
    }

    engine = get_engine()
    with engine.begin() as conn:
        stmt = (
            insert(user_identity)
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
            .returning(user_identity)
        )
        row = conn.execute(stmt).first()
        return row

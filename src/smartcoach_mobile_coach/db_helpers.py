"""Small DB helpers; avoids importing activity_routes (blueprint side effects)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session


def get_primary_athlete_id(session: Session, internal_user_id: str) -> Optional[int]:
    stmt = text(
        """
        SELECT athlete_id
        FROM public.user_athletes
        WHERE user_id = :uid
        LIMIT 1
        """
    ).bindparams(bindparam("uid", type_=PGUUID))
    row = session.execute(stmt, {"uid": internal_user_id}).fetchone()
    if not row:
        return None
    return int(row[0])

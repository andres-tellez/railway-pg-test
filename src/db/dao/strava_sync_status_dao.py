from __future__ import annotations

from contextlib import contextmanager
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import select, update, func
from sqlalchemy.exc import SQLAlchemyError

from src.db.models.strava_sync_status import StravaSyncStatus
from src.db.db_session import get_session


DEFAULT_USER_MESSAGE = "Syncing activities…"


class StravaSyncStatusDAO:
    def __init__(self, session: Session):
        self.session = session

    def start_sync(self, user_id: str, athlete_id: int) -> StravaSyncStatus:
        status = (
            self.session.execute(
                select(StravaSyncStatus).where(
                    StravaSyncStatus.user_id == user_id,
                    StravaSyncStatus.athlete_id == athlete_id,
                )
            )
            .scalars()
            .first()
        )

        if status:
            status.status = "in_progress"
            status.progress = 0.0
            status.step = "Preparing to sync"
            status.detail = None
            status.error_code = None
            status.completed_at = None
        else:
            status = StravaSyncStatus(
                user_id=user_id,
                athlete_id=athlete_id,
                status="in_progress",
                progress=0.0,
                step="Preparing to sync",
            )
            self.session.add(status)

        self.session.commit()
        return status

    def update_progress(
        self,
        user_id: str,
        athlete_id: int,
        *,
        progress: float,
        step: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        self.session.execute(
            update(StravaSyncStatus)
            .where(
                StravaSyncStatus.user_id == user_id,
                StravaSyncStatus.athlete_id == athlete_id,
            )
            .values(
                status="in_progress",
                progress=max(0.0, min(progress, 100.0)),
                step=step or DEFAULT_USER_MESSAGE,
                detail=detail,
            )
        )
        self.session.commit()

    def mark_complete(self, user_id: str, athlete_id: int) -> None:
        self.session.execute(
            update(StravaSyncStatus)
            .where(
                StravaSyncStatus.user_id == user_id,
                StravaSyncStatus.athlete_id == athlete_id,
            )
            .values(
                status="complete",
                progress=100.0,
                step="Sync complete",
                detail=None,
                error_code=None,
                completed_at=func.now(),
            )
        )
        self.session.commit()

    def mark_error(
        self,
        user_id: str,
        athlete_id: int,
        *,
        detail: str,
        error_code: Optional[str] = None,
    ) -> None:
        self.session.execute(
            update(StravaSyncStatus)
            .where(
                StravaSyncStatus.user_id == user_id,
                StravaSyncStatus.athlete_id == athlete_id,
            )
            .values(
                status="error",
                step="Sync failed",
                detail=detail,
                error_code=error_code,
                progress=0.0,
            )
        )
        self.session.commit()

    def get_status(self, user_id: str, athlete_id: int) -> Optional[StravaSyncStatus]:
        return (
            self.session.execute(
                select(StravaSyncStatus).where(
                    StravaSyncStatus.user_id == user_id,
                    StravaSyncStatus.athlete_id == athlete_id,
                )
            )
            .scalars()
            .first()
        )

    def get_latest_for_user(self, user_id: str) -> Optional[StravaSyncStatus]:
        return (
            self.session.execute(
                select(StravaSyncStatus)
                .where(StravaSyncStatus.user_id == user_id)
                .order_by(StravaSyncStatus.updated_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )


@contextmanager
def get_sync_status_dao(session: Optional[Session] = None):
    external_session = session is not None
    session = session or get_session()
    try:
        yield StravaSyncStatusDAO(session)
    finally:
        if not external_session:
            session.close()

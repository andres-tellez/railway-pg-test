"""
Purpose:
- Canonical read-only active-plan existence check.

Responsibilities:
- Expose one helper (`has_active_plan`) that answers whether a user currently
  has an active row in `plans`.
- Preserve defensive behavior used by coach flows: return False on DB errors
  and roll back the SQLAlchemy session if needed.

Non-goals:
- No plan creation, mutation, or replacement logic.
- No orchestration or prompt assembly concerns.

Guardrails:
- Allowed imports/calls: SQLAlchemy Session + text query, module-local logger.
- Must not import from smartcoach orchestrator modules.
- Must remain a thin read helper (single existence query).
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("services.plan.active_plan")


def has_active_plan(session: Session, user_id: str) -> bool:
    """Cheap existence check for an active user plan."""
    if not user_id:
        return False
    try:
        row = session.execute(
            text(
                "SELECT 1 FROM plans "
                "WHERE user_id = CAST(:uid AS uuid) AND is_active = TRUE "
                "LIMIT 1"
            ),
            {"uid": user_id},
        ).first()
    except Exception:
        logger.debug(
            "[active_plan] query failed; treating as no-plan",
            exc_info=True,
        )
        try:
            session.rollback()
        except Exception:
            logger.debug(
                "[active_plan] rollback failed",
                exc_info=True,
            )
        return False
    return row is not None


__all__ = ["has_active_plan"]

"""Run Review V2 telemetry — best-effort, never raises."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.services.product_analytics_service import record_product_event, truncate_text

logger = logging.getLogger("smartcoach_mobile_coach")


def record_run_review_event(
    *,
    user_id: Optional[str],
    outcome: str,
    user_message: str,
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    """Emit one ``coach_run_review`` product analytics event.

    ``outcome`` is a short string like ``"served"``, ``"fallback"``, ``"skip"``.
    The user message is truncated so we never persist long bodies.
    """
    props: Dict[str, Any] = dict(properties or {})
    props.setdefault("user_message_preview", truncate_text(user_message, 240))
    try:
        record_product_event(
            event_name="coach_run_review",
            outcome=outcome,
            user_id=user_id,
            source="server",
            properties=props,
        )
    except Exception:
        logger.debug("coach_run_review analytics skipped", exc_info=True)

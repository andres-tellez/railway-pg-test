"""Coach response telemetry — best-effort, never raises."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.services.product_analytics_service import record_product_event, truncate_text

logger = logging.getLogger("smartcoach_mobile_coach")


def record_coach_response_event(
    *,
    user_id: Optional[str],
    outcome: str,
    user_message: str,
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    """Emit one ``coach_response_v1`` product analytics event."""
    props: Dict[str, Any] = dict(properties or {})
    props.setdefault("user_message_preview", truncate_text(user_message, 240))
    try:
        record_product_event(
            event_name="coach_response_v1",
            outcome=outcome,
            user_id=user_id,
            source="server",
            properties=props,
        )
    except Exception:
        logger.debug("coach_response_v1 analytics skipped", exc_info=True)

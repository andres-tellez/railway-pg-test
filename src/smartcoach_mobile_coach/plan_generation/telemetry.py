"""Analytics helpers for plan-generation tool outcomes."""

# pylint: disable=missing-function-docstring,broad-exception-caught,import-outside-toplevel,duplicate-code

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("smartcoach_mobile_coach")


def record_plan_generation_tool_event(
    internal_user_id: str,
    outcome: str,
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        from src.services.product_analytics_service import record_product_event

        record_product_event(
            event_name="plan_generation_tool",
            outcome=outcome,
            user_id=str(internal_user_id),
            source="server",
            properties=properties,
        )
    except Exception:
        logger.debug("plan_generation_tool analytics skipped", exc_info=True)

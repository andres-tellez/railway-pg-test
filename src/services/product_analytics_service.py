"""Best-effort product analytics persistence (never raises to callers)."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Mapping, Optional

from src.db.db_session import get_session
from src.db.models.product_analytics_event import ProductAnalyticsEvent

logger = logging.getLogger(__name__)

_MAX_PROP_JSON_BYTES = 12000


def _shrink_properties(props: Optional[Mapping[str, Any]]) -> Optional[dict]:
    if not props:
        return None
    try:
        raw = json.dumps(dict(props), default=str)
    except Exception:
        return {"_serialization": "failed"}
    if len(raw.encode("utf-8")) <= _MAX_PROP_JSON_BYTES:
        return dict(props)
    return {
        "_truncated": True,
        "preview": raw[:_MAX_PROP_JSON_BYTES],
    }


def record_product_event(
    *,
    event_name: str,
    outcome: str,
    user_id: Optional[str] = None,
    source: str = "server",
    correlation_id: Optional[str] = None,
    client_event_id: Optional[str] = None,
    properties: Optional[Mapping[str, Any]] = None,
) -> None:
    try:
        session = get_session()
        try:
            row = ProductAnalyticsEvent(
                user_id=str(user_id) if user_id else None,
                event_name=str(event_name)[:120],
                outcome=str(outcome)[:64],
                source=str(source)[:32],
                correlation_id=(
                    str(correlation_id)[:120] if correlation_id is not None else None
                ),
                client_event_id=(
                    str(client_event_id)[:120] if client_event_id is not None else None
                ),
                properties=_shrink_properties(properties),
                created_at=datetime.utcnow(),
            )
            session.add(row)
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.warning("product_analytics insert failed: %s", exc, exc_info=True)
        finally:
            session.close()
    except Exception as exc:
        logger.warning("product_analytics session failed: %s", exc, exc_info=True)


def truncate_text(value: Optional[str], max_chars: int = 500) -> str:
    if not value or not isinstance(value, str):
        return ""
    s = value.strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1] + "…"

"""
HTTP API for SmartCoach mobile Coach tab — agent tool loop only.

POST /api/conversations/<conversation_id>/agent-messages
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

from flask import Blueprint, jsonify, request

from src.db.db_session import get_session
from src.db.models.conversations import Conversation, ConversationMessage
from src.routes.conversation_routes import get_user_from_auth
from src.services.security.external_apis.openai_service import (
    CostLimitExceededError,
    RateLimitExceededError,
)
from src.smartcoach_mobile_coach.config import SMARTCOACH_MOBILE_AGENT_ENABLED
from src.smartcoach_mobile_coach.http_rate_limit import (
    can_make_agent_http_request,
    record_agent_http_request,
)
from src.smartcoach_mobile_coach.orchestrator import run_mobile_agent_turn
from src.utils.response_utils import error_response

logger = logging.getLogger("smartcoach_mobile_coach")

_EVAL_MODEL_ALLOWLIST = frozenset(
    {"gpt-4o", "gpt-4o-mini", "gpt-4o-2024-08-06"},
)


def _eval_model_override_enabled() -> bool:
    v = (os.getenv("SMARTCOACH_COACH_EVAL_MODEL_OVERRIDE") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _eval_request_secret_configured() -> str:
    """Shared secret for scripted eval (optional alternative to override flag)."""
    return (os.getenv("SMARTCOACH_COACH_EVAL_REQUEST_SECRET") or "").strip()


def _eval_request_secret_matches() -> bool:
    """True when client sent X-SmartCoach-Eval-Secret matching SMARTCOACH_COACH_EVAL_REQUEST_SECRET."""
    secret = _eval_request_secret_configured()
    if not secret:
        return False  # never treat empty server secret as valid
    hdr = (request.headers.get("X-SmartCoach-Eval-Secret") or "").strip()
    if len(hdr) != len(secret):
        return False
    return hmac.compare_digest(hdr, secret)


def _eval_headers_allowed() -> bool:
    """
    Allow X-SmartCoach-Eval-Model when either:
    - SMARTCOACH_COACH_EVAL_MODEL_OVERRIDE is on, or
    - SMARTCOACH_COACH_EVAL_REQUEST_SECRET is set on the server and the request
      includes matching X-SmartCoach-Eval-Secret (for local/staging eval scripts).
    """
    return _eval_model_override_enabled() or _eval_request_secret_matches()


def _coerce_eval_model_header() -> Optional[str]:
    """Honor X-SmartCoach-Eval-Model when eval headers are allowed (override or secret)."""
    if not _eval_headers_allowed():
        return None
    raw = request.headers.get("X-SmartCoach-Eval-Model")
    if not raw or not isinstance(raw, str):
        return None
    name = raw.strip()
    if name in _EVAL_MODEL_ALLOWLIST:
        return name
    logger.warning(
        "[smartcoach_mobile_coach] ignored X-SmartCoach-Eval-Model=%r (not in allowlist)",
        name[:80],
    )
    return None


def _llm_plain_text_from_stored_message(role: str, content: str) -> str:
    """
    Assistant rows may store JSON for structured mobile payloads; the agent only sees plain insight text.
    """
    if role != "assistant" or not content:
        return content
    stripped = content.strip()
    if not stripped.startswith("{"):
        return content
    try:
        obj: Any = json.loads(stripped)
    except json.JSONDecodeError:
        return content
    if isinstance(obj, dict) and obj.get("type") == "run_summary":
        inner = obj.get("content")
        if isinstance(inner, str):
            return inner
    return content


def _resolve_anchor_local_date(payload: dict) -> Tuple[str, Optional[str]]:
    """
    Prefer client_local_date / clientLocalDate (YYYY-MM-DD) from the mobile app.
    Fall back to UTC calendar date if missing or invalid (logged).
    Returns (anchor_date_str, timezone_str_or_none).
    """
    raw = payload.get("client_local_date")
    if raw is None:
        raw = payload.get("clientLocalDate")
    tz_raw = payload.get("client_timezone")
    if tz_raw is None:
        tz_raw = payload.get("clientTimezone")

    tz = None
    if isinstance(tz_raw, str) and tz_raw.strip():
        tz = tz_raw.strip()[:120]

    if isinstance(raw, str) and raw.strip():
        candidate = raw.strip()
        try:
            datetime.strptime(candidate, "%Y-%m-%d")
            return candidate, tz
        except ValueError:
            logger.warning(
                "[smartcoach_mobile_coach] invalid client_local_date=%r; using UTC fallback",
                candidate[:48],
            )

    anchor = datetime.now(timezone.utc).date().isoformat()
    logger.info(
        "[smartcoach_mobile_coach] missing client_local_date; using UTC date fallback %s",
        anchor,
    )
    return anchor, tz


smartcoach_mobile_coach_bp = Blueprint(
    "smartcoach_mobile_coach",
    __name__,
    url_prefix="/api",
)


@smartcoach_mobile_coach_bp.route(
    "/conversations/<conversation_id>/agent-messages",
    methods=["POST"],
)
def agent_messages(conversation_id):
    correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    if not SMARTCOACH_MOBILE_AGENT_ENABLED:
        logger.info(
            "[smartcoach_mobile_coach] agent disabled correlation_id=%s", correlation_id
        )
        return (
            jsonify(
                {
                    "error": "agent_disabled",
                    "message": "Mobile coach agent is not enabled on this server.",
                }
            ),
            503,
        )

    if not request.is_json:
        return jsonify({"error": "Request content-type must be application/json"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400

    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Invalid or missing 'message'"}), 400

    user_id, err_resp, err_code = get_user_from_auth()
    if err_resp:
        return err_resp, err_code

    uid_str = str(user_id)
    allowed, retry_after = can_make_agent_http_request(uid_str)
    if not allowed:
        return (
            jsonify(
                {
                    "error": "rate_limited",
                    "message": "Too many agent requests. Please wait and try again.",
                    "retry_after_seconds": int(max(1, round(retry_after))),
                }
            ),
            429,
        )
    record_agent_http_request(uid_str)

    session = get_session()
    start = time.time()
    try:
        conversation = (
            session.query(Conversation)
            .filter_by(id=conversation_id, user_id=user_id)
            .first()
        )
        if not conversation:
            return jsonify({"error": "Conversation not found"}), 404

        prior = (
            session.query(ConversationMessage)
            .filter_by(conversation_id=conversation_id)
            .order_by(ConversationMessage.created_at.asc())
            .all()
        )
        history = [
            {
                "role": m.role,
                "content": _llm_plain_text_from_stored_message(m.role, m.content),
            }
            for m in prior
        ]
        anchor_date, client_tz = _resolve_anchor_local_date(data)

        user_msg = ConversationMessage(
            conversation_id=conversation_id,
            role="user",
            content=message.strip(),
        )
        session.add(user_msg)

        if len(prior) == 0:
            conversation.title = message.strip()[:50] + (
                "..." if len(message) > 50 else ""
            )

        try:
            gpt_response, meta = run_mobile_agent_turn(
                session,
                uid_str,
                history,
                message.strip(),
                anchor_local_date=anchor_date,
                client_timezone=client_tz,
                eval_model_override=_coerce_eval_model_header(),
            )
        except RateLimitExceededError as e:
            session.rollback()
            return error_response(
                message=f"Rate limit exceeded. Please try again in {int(e.retry_after)} seconds.",
                status_code=429,
                error_code="OPENAI_RATE_LIMIT_EXCEEDED",
                details={
                    "retry_after_seconds": int(e.retry_after),
                },
            )
        except CostLimitExceededError as e:
            session.rollback()
            return error_response(
                message=e.message or "Daily cost limit exceeded.",
                status_code=429,
                error_code="OPENAI_COST_LIMIT_EXCEEDED",
                details={"limit_type": "daily_cost"},
            )

        assistant_content = (
            json.dumps(gpt_response, separators=(",", ":"))
            if isinstance(gpt_response, dict)
            else gpt_response
        )
        assistant_msg = ConversationMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_content,
        )
        session.add(assistant_msg)
        conversation.updated_at = datetime.utcnow()
        session.commit()

        elapsed = time.time() - start
        response_shape = (
            gpt_response.get("type") if isinstance(gpt_response, dict) else "text"
        )
        logger.info(
            "[smartcoach_mobile_coach] ok correlation_id=%s user=%s conversation=%s "
            "loops=%s max_loops=%s truncated=%s cost=%.6f tokens=%s duration_ms=%d response_shape=%s",
            correlation_id,
            uid_str,
            conversation_id,
            meta.get("loops"),
            meta.get("max_loops"),
            meta.get("truncated", False),
            meta.get("cost", 0),
            meta.get("usage", {}).get("total_tokens", 0),
            int(elapsed * 1000),
            response_shape,
        )

        model_used = str(meta.get("model") or "")
        resp_headers = {}
        if model_used:
            resp_headers["X-SmartCoach-Model-Used"] = model_used

        return (
            jsonify(
                {
                    "message": "Message sent successfully",
                    "response": gpt_response,
                    "message_id": str(user_msg.id),
                    "response_time": elapsed,
                    "token_usage": {
                        "prompt_tokens": meta.get("usage", {}).get("prompt_tokens", 0),
                        "completion_tokens": meta.get("usage", {}).get(
                            "completion_tokens", 0
                        ),
                        "total_tokens": meta.get("usage", {}).get("total_tokens", 0),
                        "model": model_used,
                    },
                }
            ),
            200,
            resp_headers,
        )

    except Exception as e:
        logger.exception(
            "[smartcoach_mobile_coach] error correlation_id=%s: %s",
            correlation_id,
            e,
        )
        session.rollback()
        return jsonify({"error": f"Failed to process agent message: {str(e)}"}), 500
    finally:
        session.close()

"""
HTTP API for SmartCoach mobile Coach tab — agent tool loop only.

POST /api/conversations/<conversation_id>/agent-messages
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime

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
        history = [{"role": m.role, "content": m.content} for m in prior]

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

        assistant_msg = ConversationMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=gpt_response,
        )
        session.add(assistant_msg)
        conversation.updated_at = datetime.utcnow()
        session.commit()

        elapsed = time.time() - start
        logger.info(
            "[smartcoach_mobile_coach] ok correlation_id=%s user=%s conversation=%s "
            "loops=%s cost=%.6f tokens=%s duration_ms=%d",
            correlation_id,
            uid_str,
            conversation_id,
            meta.get("loops"),
            meta.get("cost", 0),
            meta.get("usage", {}).get("total_tokens", 0),
            int(elapsed * 1000),
        )

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
                        "model": meta.get("model", ""),
                    },
                }
            ),
            200,
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

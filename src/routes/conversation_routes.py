"""
Conversation Routes Module
==========================

Provides API endpoints for AI-powered conversation management.

Endpoints:
----------
GET    /api/conversations
    Get all conversations for the current user

POST   /api/conversations
    Create a new conversation

GET    /api/conversations/<conversation_id>
    Get a specific conversation with its messages

POST   /api/conversations/<conversation_id>/messages
    Send a message and get AI coach response

DELETE /api/conversations/<conversation_id>
    Delete a conversation

Dependencies:
-------------
- SmartDataService: Provides context-aware training data
- get_conversation_response: GPT integration for AI responses
- Conversation/ConversationMessage: Database models

Features:
---------
- Context-aware responses based on user's training data
- Conversation history management
- Training plan coach system prompt
- Automatic conversation title generation

Author: SmartCoach Development Team
Last Updated: November 2025
"""

import time
import logging
from flask import Blueprint, request, jsonify
from src.db.db_session import get_session
from src.db.models.conversations import Conversation, ConversationMessage
from src.utils.gpt_ops import get_conversation_response
from src.utils.auth_helpers import get_user_id_from_request
from src.services.security.external_apis.openai_rate_limiter import get_user_stats
from src.services.security.external_apis.openai_cost_tracker import (
    get_user_cost_stats,
)
from src.services.security.external_apis.openai_service import (
    RateLimitExceededError,
    CostLimitExceededError,
)
from src.utils.response_utils import error_response

logger = logging.getLogger(__name__)


from datetime import datetime

conversation_bp = Blueprint("conversation", __name__, url_prefix="/api")


TRAINING_PLAN_COACH_SYSTEM_PROMPT = """You are an expert running coach with access to comprehensive training data.

You will receive structured data including:
- User profile and race information
- Historical activity data (completed runs)
- Planned workout data (upcoming training)
- Weekly summaries and performance metrics

CRITICAL: For "this week" questions, ALWAYS use the "direct_answer" field if present. This contains the exact workouts for this week. Do NOT use other data sources for this week questions.

When answering questions:
1. Reference specific data points when relevant
2. Provide actionable insights based on the user's training patterns
3. Consider the user's race goals and timeline
4. Be encouraging and supportive while being honest about performance

For vague questions (like "How am I doing?" or "Tell me about my running"):
- Acknowledge what data you have available
- Ask 2-3 specific clarifying questions with options
- Provide examples of what you can help with
- Be encouraging and helpful

If you don't have complete data for a question, acknowledge this and ask for clarification."""


# Removed validate_user_query - not needed for simple system


def get_user_from_auth():
    """Helper function to get user_id from authentication"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, jsonify({"error": "unauthorized", "reason": "no_bearer"}), 401

    token = auth.split(" ", 1)[1]
    try:
        from src.utils.auth0_jwt import verify_and_decode

        claims = verify_and_decode(token)
    except Exception as e:
        return None, jsonify({"error": "unauthorized", "reason": str(e)}), 401

    from src.utils.auth_helpers import get_user_id_from_request

    user_id, error = get_user_id_from_request(claims, create_if_missing=False)
    if error:
        return None, error[0], error[1]  # Return (None, response, status_code)

    return user_id, None, None


@conversation_bp.route("/conversations", methods=["GET"])
def get_conversations():
    """Get all conversations for the current user."""
    user_id, error_response, status_code = get_user_from_auth()
    if error_response:
        return error_response, status_code

    session = get_session()
    try:

        conversations = (
            session.query(Conversation)
            .filter_by(user_id=user_id)
            .order_by(Conversation.updated_at.desc())
            .all()
        )

        result = []
        for conv in conversations:
            result.append(
                {
                    "id": str(conv.id),
                    "title": conv.title,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "message_count": len(conv.messages),
                }
            )

        return jsonify({"conversations": result}), 200

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to fetch conversations: {str(e)}"}), 500
    finally:
        session.close()


@conversation_bp.route("/conversations", methods=["POST"])
def create_conversation():
    """Create a new conversation."""
    user_id, error_response, status_code = get_user_from_auth()
    if error_response:
        return error_response, status_code

    session = get_session()
    try:

        conversation = Conversation(user_id=user_id, title="New Conversation")

        session.add(conversation)
        session.commit()

        return (
            jsonify(
                {
                    "id": str(conversation.id),
                    "title": conversation.title,
                    "created_at": conversation.created_at.isoformat(),
                }
            ),
            201,
        )

    except Exception as e:
        logger.info(f"❌ Error creating conversation: {e}")
        session.rollback()
        return jsonify({"error": f"Failed to create conversation: {str(e)}"}), 500
    finally:
        session.close()


@conversation_bp.route("/conversations/<conversation_id>", methods=["GET"])
def get_conversation(conversation_id):
    """Get a specific conversation with its messages."""
    user_id, error_response, status_code = get_user_from_auth()
    if error_response:
        return error_response, status_code

    session = get_session()
    try:

        conversation = (
            session.query(Conversation)
            .filter_by(id=conversation_id, user_id=user_id)
            .first()
        )

        if not conversation:
            return jsonify({"error": "Conversation not found"}), 404

        messages = []
        for msg in conversation.messages:
            messages.append(
                {
                    "id": str(msg.id),
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                }
            )

        return (
            jsonify(
                {
                    "id": str(conversation.id),
                    "title": conversation.title,
                    "created_at": conversation.created_at.isoformat(),
                    "updated_at": conversation.updated_at.isoformat(),
                    "messages": messages,
                }
            ),
            200,
        )

    except Exception as e:
        logger.info(f"❌ Error fetching conversation: {e}")
        return jsonify({"error": f"Failed to fetch conversation: {str(e)}"}), 500
    finally:
        session.close()


@conversation_bp.route("/conversations/<conversation_id>/messages", methods=["POST"])
def send_message(conversation_id):
    """Send a message in a conversation and get a fast response."""
    if not request.is_json:
        return jsonify({"error": "Request content-type must be application/json"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400

    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Invalid or missing 'message'"}), 400

    user_id, error_response, status_code = get_user_from_auth()
    if error_response:
        return error_response, status_code

    session = get_session()
    try:
        start_time = time.time()

        # Get the conversation
        conversation = (
            session.query(Conversation)
            .filter_by(id=conversation_id, user_id=user_id)
            .first()
        )

        if not conversation:
            return jsonify({"error": "Conversation not found"}), 404

        # Add user message
        user_msg = ConversationMessage(
            conversation_id=conversation_id, role="user", content=message.strip()
        )
        session.add(user_msg)

        # Update conversation title if this is the first message
        if len(conversation.messages) == 0:
            conversation.title = message.strip()[:50] + (
                "..." if len(message) > 50 else ""
            )

        # Get smart context based on question analysis
        try:
            from src.services.smart_data_service import SmartDataService

            data_service = SmartDataService(str(user_id))
            context = data_service.get_context_for_question(message.strip())
            data_service.close()
        except Exception as e:
            logger.error(f"Smart context creation failed: {str(e)}")
            # Fallback to simple context
            context = {
                "current_date": time.strftime("%Y-%m-%d"),
                "user_id": str(user_id),
                "question": message.strip(),
                "data_sources": [],
                "error": str(e),
            }

        # Build GPT messages
        gpt_messages = build_gpt_messages(
            context, conversation.messages, message.strip()
        )

        # Get GPT response (automatic rate limiting + cost tracking via OpenAIService)
        try:
            gpt_response, usage_info = get_conversation_response(
                gpt_messages,
                user_id=str(user_id),  # Required for security tracking
                require_json=False,
                question=message.strip(),
            )
        except RateLimitExceededError as e:
            logger.warning(
                f"OpenAI rate limit exceeded for user {user_id}. "
                f"Retry after {e.retry_after:.1f} seconds"
            )
            return error_response(
                message=f"Rate limit exceeded. Please try again in {int(e.retry_after)} seconds.",
                status_code=429,
                error_code="OPENAI_RATE_LIMIT_EXCEEDED",
                details={
                    "retry_after_seconds": int(e.retry_after),
                    "limit": "10 requests per minute",
                },
            )
        except CostLimitExceededError as e:
            logger.warning(
                f"OpenAI cost limit exceeded for user {user_id}. " f"Error: {e.message}"
            )
            return error_response(
                message=e.message or "Daily cost limit exceeded.",
                status_code=429,
                error_code="OPENAI_COST_LIMIT_EXCEEDED",
                details={
                    "limit_type": "daily_cost",
                    "exceeded_by": round(e.exceeded_by, 4) if e.exceeded_by else None,
                },
            )

        # Cost is already calculated and tracked by OpenAIService
        # Extract from usage_info (no duplicate calculation needed)
        request_cost = usage_info.get("cost", 0.0)

        # Get rate limit and cost status for response
        rate_limit_stats = get_user_stats(str(user_id))
        cost_stats = get_user_cost_stats(str(user_id))

        # Add transparency if enabled
        if False:  # Disabled transparency for simple system
            gpt_response = AITransparency.add_transparency_to_response(
                gpt_response, context
            )

        # Add assistant message
        assistant_msg = ConversationMessage(
            conversation_id=conversation_id, role="assistant", content=gpt_response
        )
        session.add(assistant_msg)

        # Update conversation timestamp
        conversation.updated_at = datetime.utcnow()

        session.commit()

        response_time = time.time() - start_time

        # Log interaction if enabled
        if False:  # Disabled logging for simple system
            AITransparency.log_ai_interaction(
                user_id, message.strip(), gpt_response, context, response_time
            )

        return (
            jsonify(
                {
                    "message": "Message sent successfully",
                    "response": gpt_response,
                    "message_id": str(user_msg.id),
                    "response_time": response_time,
                    "context_used": {
                        "context_loaded": bool(context),
                        "context_length": len(context) if context else 0,
                    },
                    "rate_limit": {
                        "remaining": rate_limit_stats["remaining"],
                        "limit": rate_limit_stats["limit"],
                        "used": rate_limit_stats["request_count"],
                    },
                    "cost": {
                        "request_cost": round(request_cost, 6),
                        "today_cost": cost_stats["today_cost"],
                        "limit": cost_stats["limit"],
                        "remaining": cost_stats["remaining"],
                        "percent_used": cost_stats["percent_used"],
                    },
                    "token_usage": {
                        "prompt_tokens": usage_info.get("prompt_tokens", 0),
                        "completion_tokens": usage_info.get("completion_tokens", 0),
                        "total_tokens": usage_info.get("total_tokens", 0),
                        "model": usage_info.get("model", "gpt-4o"),
                    },
                }
            ),
            200,
        )

    except Exception as e:
        logger.info(f"❌ Error sending message: {e}")
        import traceback

        traceback.print_exc()
        session.rollback()
        return jsonify({"error": f"Failed to send message: {str(e)}"}), 500
    finally:
        session.close()


@conversation_bp.route("/conversations/<conversation_id>", methods=["DELETE"])
def delete_conversation(conversation_id):
    """Delete a conversation."""
    user_id, error_response, status_code = get_user_from_auth()
    if error_response:
        return error_response, status_code

    session = get_session()
    try:

        conversation = (
            session.query(Conversation)
            .filter_by(id=conversation_id, user_id=user_id)
            .first()
        )

        if not conversation:
            return jsonify({"error": "Conversation not found"}), 404

        session.delete(conversation)
        session.commit()

        return jsonify({"message": "Conversation deleted successfully"}), 200

    except Exception as e:
        logger.info(f"❌ Error deleting conversation: {e}")
        session.rollback()
        return jsonify({"error": f"Failed to delete conversation: {str(e)}"}), 500
    finally:
        session.close()


def build_gpt_messages(
    context: dict, conversation_history: list, current_message: str
) -> list:
    """Build GPT messages with context and conversation history."""

    # Build system message with context
    system_content = TRAINING_PLAN_COACH_SYSTEM_PROMPT

    # Add context if provided (now a dict from simplified service)
    if context:
        import json

        context_json = json.dumps(context, indent=2)
        system_content += f"\n\n**Training Data:**\n{context_json}"

    messages = [{"role": "system", "content": system_content}]

    # Add conversation history (limit to last 10 messages)
    for msg in conversation_history[-10:]:
        messages.append({"role": msg.role, "content": msg.content})

    # Add current user message
    messages.append({"role": "user", "content": current_message})

    return messages

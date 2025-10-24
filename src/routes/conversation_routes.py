# src/routes/conversation_routes.py

import time
import logging
from flask import Blueprint, request, jsonify
from src.db.db_session import get_session
from src.db.models.conversations import Conversation, ConversationMessage
from src.utils.gpt_ops import get_conversation_response

logger = logging.getLogger(__name__)


from datetime import datetime

conversation_bp = Blueprint("conversation", __name__)


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

    sub = claims.get("sub")
    if not sub:
        return None, jsonify({"error": "missing_sub"}), 400

    from src.db.dao.user_identity_dao import resolve_user_id_from_auth_provider

    user_id = resolve_user_id_from_auth_provider(sub)
    if not user_id:
        return None, jsonify({"error": "User ID could not be resolved"}), 404

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

        # Get GPT response
        gpt_response = get_conversation_response(
            gpt_messages, require_json=False, question=message.strip()
        )

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

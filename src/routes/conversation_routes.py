# src/routes/conversation_routes.py

import time
from flask import Blueprint, request, jsonify, g
from src.db.db_session import get_session
from src.db.models.conversations import Conversation, ConversationMessage
from src.utils.gpt_ops import get_conversation_response
from src.utils.auth0_jwt import requires_auth
from src.services.simple_conversation_service import SimpleConversationService

# from src.compliance.ai_transparency import AITransparency


# Temporary simplified AI transparency
class AITransparency:
    @staticmethod
    def add_transparency_to_response(response, context):
        return response

    @staticmethod
    def log_ai_interaction(user_id, message, response, context, response_time):
        print(f"[AI Interaction] User: {user_id}, Response time: {response_time:.2f}s")


from src.config.conversation_config import ConversationConfig
from datetime import datetime
import uuid

conversation_bp = Blueprint("conversation", __name__)


JACK_DANIELS_COACH_SYSTEM_PROMPT = """You are a personalized running coach expert in the Jack Daniels Running Formula methodology.

Your role is to provide personalized coaching advice based on the runner's profile, training history, and recent activities. Use the Jack Daniels principles:
- VDOT-based training intensities
- Proper progression and periodization
- Quality over quantity
- Adequate recovery between hard sessions
- Long run progression (build 2-3 weeks, then 1 cutback week)
- Taper principles (2-3 weeks before race)

**CRITICAL: Data Accuracy Requirements:**
- ONLY reference workouts that are explicitly listed in the PLANNED WORKOUTS section
- If a day shows "NO WORKOUT PLANNED", that means NO RUN is scheduled for that day
- NEVER assume or hallucinate workouts that are not explicitly listed
- If you see "Sunday: NO WORKOUT PLANNED", the answer is NO - there is no Sunday run
- Do NOT make up or infer workouts based on patterns or assumptions

**Format your responses using Markdown** to make them clear and easy to read:
- Use **bold** for important points
- Use bullet points and numbered lists
- Create tables for training schedules or comparisons
- Use code blocks for specific pace calculations
- Use headers (##, ###) to organize sections
- Use blockquotes for key principles or quotes

**Data Analysis Guidelines:**
- Always reference the user's actual running data when available
- Provide specific insights based on their recent activities
- Use their actual pace, heart rate, and distance data for analysis
- Give personalized recommendations based on their training patterns

Provide practical, evidence-based advice that considers the runner's experience level, goals, and recent performance. Make responses comprehensive but well-organized."""


@conversation_bp.route("/conversations", methods=["GET"])
@requires_auth
def get_conversations():
    """Get all conversations for the current user."""
    print(
        f"[CONVERSATION] get_conversations called, user_id from g: {getattr(g, 'user_id', 'NOT SET')}"
    )
    session = get_session()
    try:
        user_id = g.user_id
        print(f"[CONVERSATION] user_id resolved: {user_id}")

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
        print(f"❌ Error fetching conversations: {e}")
        return jsonify({"error": f"Failed to fetch conversations: {str(e)}"}), 500
    finally:
        session.close()


@conversation_bp.route("/conversations", methods=["POST"])
@requires_auth
def create_conversation():
    """Create a new conversation."""
    session = get_session()
    try:
        user_id = g.user_id

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
        print(f"❌ Error creating conversation: {e}")
        session.rollback()
        return jsonify({"error": f"Failed to create conversation: {str(e)}"}), 500
    finally:
        session.close()


@conversation_bp.route("/conversations/<conversation_id>", methods=["GET"])
@requires_auth
def get_conversation(conversation_id):
    """Get a specific conversation with its messages."""
    session = get_session()
    try:
        user_id = g.user_id

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
        print(f"❌ Error fetching conversation: {e}")
        return jsonify({"error": f"Failed to fetch conversation: {str(e)}"}), 500
    finally:
        session.close()


@conversation_bp.route("/conversations/<conversation_id>/messages", methods=["POST"])
@requires_auth
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

    session = get_session()
    try:
        user_id = g.user_id
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

        # Get comprehensive context using simplified service
        context_service = SimpleConversationService(user_id)
        context = context_service.get_context(message.strip())
        context_service.close()

        # Build GPT messages
        gpt_messages = build_gpt_messages(
            context, conversation.messages, message.strip()
        )

        # Get GPT response (fast)
        gpt_response = get_conversation_response(gpt_messages, require_json=False)

        # Add transparency if enabled
        if ConversationConfig.COMPLIANCE["enable_transparency"]:
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
        if ConversationConfig.COMPLIANCE["log_interactions"]:
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
        print(f"❌ Error sending message: {e}")
        import traceback

        traceback.print_exc()
        session.rollback()
        return jsonify({"error": f"Failed to send message: {str(e)}"}), 500
    finally:
        session.close()


@conversation_bp.route("/conversations/<conversation_id>", methods=["DELETE"])
@requires_auth
def delete_conversation(conversation_id):
    """Delete a conversation."""
    session = get_session()
    try:
        user_id = g.user_id

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
        print(f"❌ Error deleting conversation: {e}")
        session.rollback()
        return jsonify({"error": f"Failed to delete conversation: {str(e)}"}), 500
    finally:
        session.close()


def build_gpt_messages(
    context: str, conversation_history: list, current_message: str
) -> list:
    """Build GPT messages with context and conversation history."""

    # Build system message with context
    system_content = JACK_DANIELS_COACH_SYSTEM_PROMPT

    # Add context if provided (now a string from simplified service)
    if context:
        system_content += f"\n\n{context}"

    messages = [{"role": "system", "content": system_content}]

    # Add conversation history
    for msg in conversation_history[
        -ConversationConfig.get_context_limit("conversation_history") :
    ]:
        messages.append({"role": msg.role, "content": msg.content})

    # Add current user message
    messages.append({"role": "user", "content": current_message})

    return messages

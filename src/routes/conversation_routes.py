# src/routes/conversation_routes.py

import time
import re
from flask import Blueprint, request, jsonify, g
from src.db.db_session import get_session
from src.db.models.conversations import Conversation, ConversationMessage
from src.utils.gpt_ops import get_conversation_response
from src.utils.auth0_jwt import requires_auth
from src.services.strategic_conversation_service import StrategicConversationService

# from src.compliance.ai_transparency import AITransparency


# Temporary simplified AI transparency
class AITransparency:
    @staticmethod
    def add_transparency_to_response(response, context):
        return response

    @staticmethod
    def log_ai_interaction(user_id, message, response, context, response_time):
        logger.info(
            f"[AI Interaction] User: {user_id}, Response time: {response_time:.2f}s"
        )


from src.config.conversation_config import ConversationConfig
from datetime import datetime
import uuid

conversation_bp = Blueprint("conversation", __name__)


TRAINING_PLAN_COACH_SYSTEM_PROMPT = """You are an expert running coach specializing in strategic training plan evaluation and optimization.

**Your Role:**
- Analyze training plans using strategic coaching metrics and periodization principles
- Evaluate training load ratios, intensity distribution, and completion rates
- Provide specific, actionable feedback based on Jack Daniels principles
- Assess pace consistency, easy run percentages, and race preparation timing
- Connect individual performance data to broader training strategy

**Strategic Data Available:**
- Weekly insights with training load ratios and completion rates
- Easy run percentage analysis (80%+ ideal for proper recovery)
- Pace consistency metrics (lower standard deviation = better)
- Weeks until race for proper periodization timing
- Planned vs actual volume comparisons
- Historical performance data and upcoming workouts
- Recent longest runs with detailed metrics
- Heart rate trending analysis
- Performance metrics and training progress

**Strategic Analysis Framework:**
1. **Training Load Analysis**: Volume completion rates and progression
2. **Intensity Distribution**: Easy run percentage and hard/easy balance
3. **Performance Consistency**: Pace consistency and workout completion rates
4. **Periodization Timing**: Weeks until race and training phase appropriateness
5. **Recovery Balance**: Rest days, easy runs, and recovery indicators
6. **Performance Progression**: Connect individual runs to training goals

**Clarification Protocol:**
When questions are ambiguous or could have multiple interpretations, ALWAYS ask clarifying questions:

**Time Period Ambiguity:**
- "Recently" → Ask: "Do you mean this week, last week, this month, or last 30 days?"
- "Lately" → Ask: "What time period are you interested in?"
- "How am I doing?" → Ask: "Are you asking about this week, this month, or overall progress?"

**Performance Ambiguity:**
- "My pace" → Ask: "Are you asking about your average pace, race pace, or easy run pace?"
- "My heart rate" → Ask: "Do you want to know your average HR, max HR, or HR zones?"
- "My training" → Ask: "Are you asking about volume, intensity, consistency, or overall progress?"

**Analysis Ambiguity:**
- "Am I ready?" → Ask: "Ready for what? Your next race, increased volume, or harder workouts?"
- "How's my progress?" → Ask: "Are you asking about pace improvement, distance progression, or overall fitness?"

**Response Format:**
- Use **bold** for key strategic findings
- Reference specific metrics (training load %, easy run %, etc.)
- Provide concrete recommendations based on data
- Use tables for metric comparisons
- Focus on actionable periodization advice
- Connect individual performance to broader training strategy
- Ask clarifying questions when ambiguous

**Critical Requirements:**
- Base analysis on the strategic coaching metrics provided
- Reference specific percentages and ratios from the data
- Provide periodization recommendations based on weeks until race
- Consider training load ratios and completion rates
- Focus on intensity distribution and recovery balance
- Connect individual runs to training goals and race preparation
- Always ask clarifying questions when requests are ambiguous
- Never guess what the user means - always clarify first

**Example Clarification Responses:**
- "I'd be happy to analyze your longest run! To give you the most relevant insights, could you clarify: Are you asking about your longest run this week, this month, or in the last 30 days?"
- "I can help with your pace analysis! To provide the most useful feedback, are you interested in your average training pace, your race pace, or your easy run pace?"
- "I'd love to assess your training progress! To give you targeted insights, are you asking about your volume progression, pace improvement, or overall fitness gains?"

Be thorough, strategic, and data-driven in your coaching analysis. Always clarify ambiguous requests before providing analysis."""


def validate_user_query(query):
    """Validate user query for safety and appropriateness"""
    if not query or not isinstance(query, str):
        return False, "Query must be a non-empty string"

    # Check query length
    if len(query) > 1000:
        return False, "Query too long (max 1000 characters)"

    # Check for potentially harmful content
    harmful_patterns = [
        r"<script.*?>.*?</script>",  # Script tags
        r"javascript:",  # JavaScript URLs
        r"data:.*?base64",  # Data URLs
        r"<iframe.*?>.*?</iframe>",  # Iframe tags
    ]

    for pattern in harmful_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            return False, "Query contains potentially harmful content"

    return True, "Query is valid"


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
        logger.info(f"[CONVERSATION] user_id resolved: {user_id}")

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
        logger.info(f"❌ Error fetching conversations: {e}")
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
        logger.info(f"❌ Error creating conversation: {e}")
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
        logger.info(f"❌ Error fetching conversation: {e}")
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

        # Get comprehensive context using strategic service
        context_service = StrategicConversationService(user_id)
        context = context_service.get_context(message.strip())
        context_service.close()

        # Build GPT messages
        gpt_messages = build_gpt_messages(
            context, conversation.messages, message.strip()
        )

        # Get GPT response with smart model selection
        gpt_response = get_conversation_response(
            gpt_messages, require_json=False, question=message.strip()
        )

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
        logger.info(f"❌ Error sending message: {e}")
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
        logger.info(f"❌ Error deleting conversation: {e}")
        session.rollback()
        return jsonify({"error": f"Failed to delete conversation: {str(e)}"}), 500
    finally:
        session.close()


def build_gpt_messages(
    context: str, conversation_history: list, current_message: str
) -> list:
    """Build GPT messages with context and conversation history."""

    # Build system message with context
    system_content = TRAINING_PLAN_COACH_SYSTEM_PROMPT

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

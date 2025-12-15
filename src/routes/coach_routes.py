"""
Coach Routes - Test endpoint for new Coach system.
"""

import logging
from flask import Blueprint, request, jsonify

from src.db.db_session import get_session
from src.utils.auth_helpers import get_user_id_from_request
from coach.orchestrator import CoachOrchestrator

logger = logging.getLogger(__name__)

coach_bp = Blueprint("coach", __name__, url_prefix="/api/coach")


@coach_bp.route("/test", methods=["POST"])
def test_coach():
    """
    Test endpoint for new Coach system.

    Request body:
    {
        "question": "How did my run go yesterday?"
    }

    Returns:
    {
        "response": "Formatted response from coach",
        "metadata": {
            "intent": "workout_review",
            "intent_confidence": 0.95,
            "safety_flags": [],
            ...
        },
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cost": 0.001,
            "model": "gpt-4o"
        }
    }
    """
    if not request.is_json:
        return jsonify({"error": "Request content-type must be application/json"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400

    question = data.get("question")
    if not isinstance(question, str) or not question.strip():
        return jsonify({"error": "Invalid or missing 'question'"}), 400

    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    session = get_session()
    try:
        # Get conversation history if provided
        conversation_history = data.get("conversation_history", [])

        # Create orchestrator and process question
        orchestrator = CoachOrchestrator(session, str(user_id))
        result = orchestrator.process_question(
            question=question.strip(),
            conversation_history=conversation_history,
        )

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error in Coach test endpoint: {e}", exc_info=True)
        return jsonify({"error": f"Failed to process question: {str(e)}"}), 500
    finally:
        session.close()

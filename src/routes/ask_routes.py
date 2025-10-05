from flask import Blueprint, request, jsonify, g
from src.utils.gpt_ops import format_prompt, get_gpt_response
from src.db.db_session import get_session
from src.db.dao.activity_dao import ActivityDAO
from datetime import datetime, timedelta
from src.utils.auth0_jwt import requires_auth
from src.services.training_plan_data_assembler import assemble_training_plan_data
from src.services.training_plan_service import build_training_plan_prompt
import uuid

ask_bp = Blueprint("ask", __name__)


@ask_bp.route("/ask", methods=["POST"])
@requires_auth
def ask():
    if not request.is_json:
        print("Error: Content-Type is not JSON")
        return jsonify({"error": "Request content-type must be application/json"}), 400

    data = request.get_json()
    print(f"Received data: {data}")

    if not data:
        print("Error: Missing JSON payload")
        return jsonify({"error": "Missing JSON payload"}), 400

    question = data.get("question")

    if not isinstance(question, str) or not question.strip():
        print("Error: Invalid or missing 'question'")
        return jsonify({"error": "Invalid or missing 'question'"}), 400

    sanitized_question = " ".join(question.strip().split())

    # Use the same data assembly process as training plans
    session = get_session()
    try:
        # Debug: Check what's in g
        print(f"🔍 Flask g object keys: {list(g.__dict__.keys())}")
        print(f"🔍 Flask g.user_id: {getattr(g, 'user_id', 'NOT_SET')}")
        
        # Get user_id from authenticated JWT token
        user_id_str = g.user_id  # This comes from the @requires_auth decorator
        
        # Convert string to UUID object as expected by assemble_training_plan_data
        user_id = uuid.UUID(user_id_str)

        # Assemble comprehensive training data using the same system as training plans
        data_bundle = assemble_training_plan_data(session, user_id)
        print(f"Data bundle keys: {list(data_bundle.keys())}")

        # Build a coaching prompt using the user's question and their training data
        coaching_prompt = f"""You are a smart running coach. A runner is asking you a question about their training.

Please provide helpful, personalized advice based on their training history and profile.

USER QUESTION:
{sanitized_question}

RUNNER PROFILE:
{data_bundle.get('user_profile', {})}

WEEKLY TRAINING SUMMARIES:
{data_bundle.get('weekly_summaries', [])}

RECENT ACTIVITIES:
{data_bundle.get('activities', [])}

Please provide a helpful, encouraging response that addresses their question specifically."""

        print(f"Generated coaching prompt: {coaching_prompt[:200]}...")

        gpt_response = get_gpt_response(coaching_prompt)
        print(f"Full GPT Response: {gpt_response}")
    except Exception as e:
        print(f"❌ Error in GPT processing: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"GPT processing failed: {str(e)}"}), 500
    finally:
        session.close()

    return (
        jsonify(
            {
                "message": "✅ GPT response generated",
                "question": sanitized_question,
                "response": gpt_response,
            }
        ),
        200,
    )

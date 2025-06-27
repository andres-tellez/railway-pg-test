# src/routes/ask_routes.py

from flask import Blueprint, request, jsonify

ask_bp = Blueprint('ask', __name__)

@ask_bp.route('/ask', methods=['POST'])
def ask():
    if not request.is_json:
        return jsonify({"error": "Request content-type must be application/json"}), 400

    data = request.get_json()

    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400

    question = data.get("question")
    athlete_id = data.get("athlete_id")

    if not isinstance(question, str) or not question.strip():
        return jsonify({"error": "Invalid or missing 'question'"}), 400

    try:
        athlete_id = int(athlete_id)
        if athlete_id <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid or missing 'athlete_id' (must be a positive integer)"}), 400

    sanitized_question = " ".join(question.strip().split())

    return jsonify({
        "message": "✅ Question received",
        "athlete_id": athlete_id,
        "question": sanitized_question
    }), 200

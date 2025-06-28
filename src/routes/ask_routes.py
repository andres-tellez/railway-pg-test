from flask import Blueprint, request, jsonify
from src.utils.gpt_ops import format_prompt, get_gpt_response
from src.db.db_session import get_session
from src.db.dao.activity_dao import ActivityDAO
from datetime import datetime, timedelta

ask_bp = Blueprint('ask', __name__)

@ask_bp.route('/ask', methods=['POST'])
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
    athlete_id = data.get("athlete_id")

    if not isinstance(question, str) or not question.strip():
        print("Error: Invalid or missing 'question'")
        return jsonify({"error": "Invalid or missing 'question'"}), 400

    try:
        athlete_id = int(athlete_id)
        if athlete_id <= 0:
            raise ValueError
    except (ValueError, TypeError):
        print("Error: Invalid or missing 'athlete_id'")
        return jsonify({"error": "Invalid or missing 'athlete_id' (must be a positive integer)"}), 400

    sanitized_question = " ".join(question.strip().split())

    
    from datetime import date, timedelta
    # Get start of current week (Monday)
    today = date.today()
    start_date = today - timedelta(days=today.weekday())

    session = get_session()
    try:
        activities = ActivityDAO.get_activities_by_athlete(session, athlete_id)
        filtered = [
            a for a in activities
            if a.start_date and start_date <= a.start_date.date() <= today
        ]

        activity_data = [
            {
                "start_date": a.start_date.strftime("%Y-%m-%d %H:%M:%S"),
                "conv_distance": round(a.conv_distance, 2),
                "duration": f"{round(a.moving_time / 60)} minutes"
            }
            for a in filtered
        ]
    finally:
        session.close()

    print(f"Activity data: {activity_data}")

    prompt = format_prompt(sanitized_question, activity_data)
    print(f"Generated prompt: {prompt}")

    gpt_response = get_gpt_response(prompt)
    print(f"Full GPT Response: {gpt_response}")

    return jsonify({
        "message": "✅ GPT response generated",
        "athlete_id": athlete_id,
        "question": sanitized_question,
        "response": gpt_response
    }), 200

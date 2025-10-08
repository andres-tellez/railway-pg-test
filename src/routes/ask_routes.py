from flask import Blueprint, request, jsonify, g
from src.utils.gpt_ops import get_gpt_response
from src.db.db_session import get_session
from datetime import datetime, timedelta
from src.utils.auth0_jwt import requires_auth

ask_bp = Blueprint("ask", __name__)

JACK_DANIELS_COACH_PROMPT = """You are a running coach expert in the Jack Daniels Running Formula methodology.

Your role is to answer running-related questions using Jack Daniels' proven principles:
- VDOT-based training intensities
- Proper progression and periodization
- Quality over quantity
- Adequate recovery between hard sessions
- Long run progression (build 2-3 weeks, then 1 cutback week)
- Taper principles (2-3 weeks before race)

Provide practical, evidence-based advice grounded in the Jack Daniels methodology.
Keep responses concise and actionable."""


@ask_bp.route("/ask", methods=["POST"])
@requires_auth
def ask():
    """Simple Ask Coach endpoint using Jack Daniels methodology."""
    if not request.is_json:
        return jsonify({"error": "Request content-type must be application/json"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400

    question = data.get("question")
    if not isinstance(question, str) or not question.strip():
        return jsonify({"error": "Invalid or missing 'question'"}), 400

    sanitized_question = " ".join(question.strip().split())

    session = get_session()
    try:
        user_id = g.user_id  # Use raw string from JWT, same as get_current_plan

        # Build context from user's training plan if they ask about it
        question_lower = sanitized_question.lower()
        context = ""

        if any(
            keyword in question_lower
            for keyword in [
                "plan",
                "training",
                "workout",
                "schedule",
                "mileage",
                "week",
            ]
        ):
            print(f"🔍 Keyword match found, loading training plan for user {user_id}")
            # Load the user's training plan
            from src.db.models.plans import Plan
            from sqlalchemy.orm import joinedload

            # Debug: Check all plans to see user_id format
            all_plans = session.query(Plan).limit(5).all()
            print(f"🔍 Debug: Found {len(all_plans)} plans in database")
            for p in all_plans:
                print(
                    f"   Plan {p.id}: user_id='{p.user_id}' (match: {p.user_id == user_id})"
                )

            plan = (
                session.query(Plan)
                .options(joinedload(Plan.workouts))
                .filter_by(user_id=user_id)  # Use same format as get_current_plan
                .order_by(Plan.created_at.desc())
                .first()
            )

            print(f"🔍 Query result: {plan}")

            if plan:
                print(
                    f"✅ Plan found: ID={plan.id}, Race={plan.race_distance} on {plan.race_date}"
                )
                workouts = sorted(plan.workouts, key=lambda w: w.date)

                context += f"\n\nUSER'S CURRENT TRAINING PLAN:\n"
                context += f"- Race Goal: {plan.race_distance} on {plan.race_date}\n"
                context += f"- Total Workouts: {len(workouts)} workouts\n"
                context += f"- Plan Period: {workouts[0].date if workouts else 'N/A'} to {workouts[-1].date if workouts else 'N/A'}\n"
                context += f"\nUPCOMING WORKOUTS (first 10):\n"

                # Add detailed workouts
                for workout in workouts[:10]:
                    context += f"- {workout.date} ({workout.date.strftime('%A')}): {workout.workout_type} - {workout.miles}mi, {workout.target_zone}\n"
                    if workout.description:
                        context += f"  Description: {workout.description}\n"

                print(f"✅ Context built: {len(context)} characters")
            else:
                print(f"⚠️ No training plan found for user {user_id}")

        # Build simple prompt
        prompt = f"""{JACK_DANIELS_COACH_PROMPT}

USER QUESTION:
{sanitized_question}
{context}
"""

        print(f"\n📝 Full prompt sent to GPT:")
        print(f"{'='*80}")
        print(prompt)
        print(f"{'='*80}\n")

        # Get response from GPT
        gpt_response = get_gpt_response(prompt, require_json=False)
        print(f"\n✅ GPT Response received: {len(gpt_response)} characters")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to process question: {str(e)}"}), 500
    finally:
        session.close()

    return (
        jsonify(
            {
                "message": "✅ Response generated",
                "question": sanitized_question,
                "response": gpt_response,
            }
        ),
        200,
    )

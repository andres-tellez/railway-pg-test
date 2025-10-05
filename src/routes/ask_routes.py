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

        # Determine what type of data the user is asking about based on their question
        question_lower = sanitized_question.lower()
        
        # Keywords that suggest they want training plan analysis
        training_plan_keywords = [
            'training plan', 'planned workouts', 'my plan', 'the plan', 
            'week by week', 'monthly', 'schedule', 'upcoming', 'future',
            'rate this plan', 'analyze this plan', 'how does this plan look'
        ]
        
        # Keywords that suggest they want historical activity analysis
        historical_keywords = [
            'past', 'previous', 'historical', 'last week', 'last month',
            'recent activities', 'strava', 'what i did', 'my runs',
            'training history', 'past performance', 'previous workouts'
        ]
        
        # Determine context
        wants_training_plan = any(keyword in question_lower for keyword in training_plan_keywords)
        wants_historical = any(keyword in question_lower for keyword in historical_keywords)
        
        # Default to training plan if no clear indication
        if not wants_historical and not wants_training_plan:
            wants_training_plan = True  # Default to training plan analysis
        
        coaching_prompt = ""
        
        if wants_training_plan:
            # Load the user's generated training plan
            from src.db.models.plans import Plan
            from sqlalchemy.orm import joinedload
            
            plan = (
                session.query(Plan)
                .options(joinedload(Plan.workouts))
                .filter_by(user_id=str(user_id))
                .order_by(Plan.created_at.desc())
                .first()
            )
            
            if not plan:
                return jsonify({"error": "No training plan found. Please generate a training plan first."}), 404
            
            # Get user profile for context
            from src.db.models.user_profile import UserProfile
            user_profile = session.query(UserProfile).filter_by(user_id=str(user_id)).first()
            
            # Build training plan data for analysis
            workouts = sorted(plan.workouts, key=lambda w: w.date)
            
            # Group workouts by week for analysis
            from collections import defaultdict
            from datetime import datetime, timedelta
            
            weekly_data = defaultdict(list)
            for workout in workouts:
                # Get the Monday of the week for this workout
                workout_date = workout.date
                days_since_monday = workout_date.weekday()
                week_start = workout_date - timedelta(days=days_since_monday)
                week_key = week_start.strftime('%Y-%m-%d')
                weekly_data[week_key].append(workout)
            
            # Build coaching prompt for training plan analysis
            coaching_prompt = f"""You are an elite running coach with 20+ years of experience. A runner is asking you to analyze their TRAINING PLAN.

TRAINING PLAN CONTEXT:
- Race Date: {plan.race_date}
- Race Distance: {plan.race_distance}
- Plan Start: {workouts[0].date if workouts else 'N/A'}
- Total Workouts: {len(workouts)}
- Training Days: {user_profile.training_days if user_profile else 'Not specified'}

USER QUESTION:
{sanitized_question}

WEEKLY TRAINING PLAN ANALYSIS:
"""
            
            # Add weekly workout summaries
            for week_start, week_workouts in sorted(weekly_data.items()):
                total_miles = sum(w.miles for w in week_workouts)
                long_run = max((w.miles for w in week_workouts), default=0)
                workout_types = [w.workout_type for w in week_workouts]
                
                coaching_prompt += f"""
Week of {week_start}:
- Total Miles: {total_miles:.1f}
- Longest Run: {long_run:.1f} miles
- Workouts: {', '.join(workout_types)}
- Workout Details:
"""
                for workout in week_workouts:
                    coaching_prompt += f"  * {workout.date}: {workout.workout_type} - {workout.miles} miles"
                    if workout.target_zone:
                        coaching_prompt += f" ({workout.target_zone})"
                    if workout.focus:
                        coaching_prompt += f" - Focus: {workout.focus}"
                    coaching_prompt += "\n"
            
            coaching_prompt += f"""
RACE DAY: {plan.race_date}

Please analyze this TRAINING PLAN week by week and provide expert coaching feedback. 
Consider the runner's age (49), training days (Mon, Wed, Thu, Sat), and marathon goal.
Focus on the generated training plan workouts and their structure.

Please provide a helpful, encouraging response that addresses their question specifically."""
        
        else:
            # Load historical activities for analysis
            data_bundle = assemble_training_plan_data(session, user_id)
            
            # Build coaching prompt for historical analysis
            coaching_prompt = f"""You are an elite running coach with 20+ years of experience. A runner is asking you to analyze their TRAINING HISTORY.

USER QUESTION:
{sanitized_question}

RUNNER PROFILE:
{data_bundle.get('user_profile', {})}

WEEKLY TRAINING SUMMARIES:
{data_bundle.get('weekly_summaries', [])}

RECENT ACTIVITIES:
{data_bundle.get('activities', [])}

Please analyze their HISTORICAL TRAINING DATA and provide expert coaching feedback. 
Consider their past performance, training patterns, and areas for improvement.

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

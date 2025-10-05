from flask import Blueprint, request, jsonify, g
from src.utils.gpt_ops import format_prompt, get_gpt_response, get_expert_coaching_response, build_expert_coaching_prompt
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

        # Keywords that suggest expert coaching request
        expert_coaching_keywords = [
            'expert', 'coach', 'training plan', 'marathon', 'mileage', 'weekly', 
            'analysis', 'rate', 'grade', 'injury', 'safe', 'age', '49', 'masters',
            'physiology', 'periodization', 'recovery', 'adaptation', 'performance',
            'assessment', 'evaluation', 'scientific', 'evidence-based'
        ]

        # Determine context - prioritize training plan analysis when user asks about "the plan"
        wants_training_plan = any(keyword in question_lower for keyword in training_plan_keywords)
        wants_historical = any(keyword in question_lower for keyword in historical_keywords)
        is_expert_request = any(keyword in question_lower for keyword in expert_coaching_keywords)

        # If user asks about "the training plan" or "my plan", prioritize training plan analysis
        if wants_training_plan and any(phrase in question_lower for phrase in ['the training plan', 'my plan', 'this plan', 'the plan']):
            is_expert_request = False  # Override expert request to use training plan analysis
            wants_historical = False

        # Default to training plan if no clear indication
        if not wants_historical and not wants_training_plan:
            wants_training_plan = True  # Default to training plan analysis

        coaching_prompt = ""

        # Use expert coaching system for complex requests
        if is_expert_request:
            # Build expert data bundle
            data_bundle = {
                "user_profile": {
                    "runner_level": "Intermediate",
                    "training_days": ["Mon", "Wed", "Thu", "Sat"],
                    "main_goal": "Marathon training",
                    "race_distance": "Marathon"
                },
                "activities": [],
                "weekly_summaries": []
            }
            
            # Load historical activities for expert analysis
            data_bundle_historical = assemble_training_plan_data(session, user_id)
            data_bundle.update(data_bundle_historical)
            
            # Build expert coaching prompt
            expert_prompt = build_expert_coaching_prompt(data_bundle, sanitized_question, user_age=49)
            gpt_response = get_expert_coaching_response(expert_prompt)
            
        elif wants_training_plan:
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

            # Build expert data bundle for training plan analysis
            data_bundle = {
                "user_profile": {
                    "runner_level": "Intermediate",
                    "training_days": ["Mon", "Wed", "Thu", "Sat"] if not user_profile or not user_profile.training_days else (
                        user_profile.training_days if isinstance(user_profile.training_days, list) 
                        else user_profile.training_days.split(',')
                    ),
                    "main_goal": "Marathon training",
                    "race_distance": plan.race_distance or "Marathon",
                    "age": 49
                },
                "activities": [],
                "weekly_summaries": []
            }
            
            # Build expert coaching prompt using centralized system
            expert_prompt = build_expert_coaching_prompt(data_bundle, sanitized_question, user_age=49)
            
            # Add training plan specific context to expert prompt
            training_plan_context = f"""

TRAINING PLAN CONTEXT:
- Race Date: {plan.race_date}
- Race Distance: {plan.race_distance}
- Plan Start: {workouts[0].date if workouts else 'N/A'}
- Total Workouts: {len(workouts)}
- Training Days: {user_profile.training_days if user_profile else 'Not specified'}

WEEKLY TRAINING PLAN ANALYSIS:
"""

            # Add weekly workout summaries
            for week_start, week_workouts in sorted(weekly_data.items()):
                total_miles = sum(w.miles for w in week_workouts)
                long_run = max((w.miles for w in week_workouts), default=0)
                workout_types = [w.workout_type for w in week_workouts]

                training_plan_context += f"""
Week of {week_start}:
- Total Miles: {total_miles:.1f}
- Longest Run: {long_run:.1f} miles
- Workouts: {', '.join(workout_types)}
- Workout Details:
"""
                for workout in week_workouts:
                    training_plan_context += f"  * {workout.date}: {workout.workout_type} - {workout.miles} miles"
                    if workout.target_zone:
                        training_plan_context += f" ({workout.target_zone})"
                    if workout.focus:
                        training_plan_context += f" - Focus: {workout.focus}"
                    training_plan_context += "\n"

            training_plan_context += f"""
RACE DAY: {plan.race_date}

Please provide a comprehensive, evidence-based analysis using Dr. Sarah Chen's expertise that addresses their question with the depth and scientific rigor expected from a PhD-level coach specializing in masters athletes."""

            # Combine expert prompt with training plan context
            full_expert_prompt = expert_prompt + training_plan_context
            
            # Use expert coaching system
            gpt_response = get_expert_coaching_response(full_expert_prompt)

        else:
            # Load historical activities for analysis
            data_bundle = assemble_training_plan_data(session, user_id)

            # Build coaching prompt for historical analysis
            coaching_prompt = f"""You are Dr. Sarah Chen, an elite running coach and exercise physiologist with 25+ years of experience. You hold a PhD in Exercise Physiology, are certified by USATF Level 3, RRCA Level 2, and have coached over 2,000 runners including Olympic qualifiers, Boston Marathon qualifiers, and masters athletes. You specialize in masters athletes (40+ age group) and are a published researcher on aging and endurance performance.

EXPERT COACHING APPROACH:
- Analyze historical data using exercise physiology principles
- Identify performance trends and patterns
- Assess training consistency and progression
- Evaluate recovery patterns and injury risk factors
- Consider age-related adaptations and limitations
- Provide evidence-based recommendations for improvement

USER QUESTION:
{sanitized_question}

RUNNER PROFILE:
{data_bundle.get('user_profile', {})}

WEEKLY TRAINING SUMMARIES:
{data_bundle.get('weekly_summaries', [])}

RECENT ACTIVITIES:
{data_bundle.get('activities', [])}

EXPERT ANALYSIS REQUIREMENTS:
1. PERFORMANCE TREND ANALYSIS: Evaluate progression, consistency, and performance patterns
2. TRAINING LOAD ASSESSMENT: Analyze volume, intensity, and recovery balance
3. INJURY RISK EVALUATION: Identify potential risk factors from historical data
4. EFFICIENCY ANALYSIS: Assess training effectiveness and areas for optimization
5. AGE-SPECIFIC CONSIDERATIONS: Factor in masters athlete physiology and adaptations
6. GOAL ALIGNMENT: Evaluate how historical training aligns with stated objectives
7. IMPROVEMENT OPPORTUNITIES: Identify specific areas for enhancement

Please provide a comprehensive, evidence-based analysis of their historical training data with the depth and expertise expected from a PhD-level coach specializing in masters athletes."""

        print(f"Generated expert coaching prompt: {len(full_expert_prompt if 'full_expert_prompt' in locals() else expert_prompt)} characters")
        print(f"Using expert coaching system: {is_expert_request}")
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
                "message": "✅ Expert coaching response generated" if is_expert_request else "✅ GPT response generated",
                "question": sanitized_question,
                "response": gpt_response,
                "expert_mode": is_expert_request,
            }
        ),
        200,
    )

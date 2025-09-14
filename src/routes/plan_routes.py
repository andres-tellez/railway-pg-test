# src/routes/plan_routes.py

from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

import src.db.db_session as db_session
from src.services import training_plan_service
from src.services.training_plan_service import PlanValidationError
from src.db.db_session import get_session


plan_bp = Blueprint("plan", __name__, url_prefix="/api/plan")


@plan_bp.route("/generate", methods=["POST"])
def generate_plan_route():
    """
    Generate a new training plan for the authenticated user.
    Expects JSON: { "race_date": "YYYY-MM-DD", "race_distance": "Marathon", "user_id": "<uuid>" }
    Returns: { "plan_id": int }
    """
    data = request.get_json() or {}
    race_date_str = data.get("race_date")
    race_distance = data.get("race_distance")
    user_id_str = data.get("user_id")  # TODO: replace with Auth0 later

    if not race_date_str or not race_distance or not user_id_str:
        return (
            jsonify({"error": "race_date, race_distance, and user_id are required"}),
            400,
        )

    try:
        race_date = datetime.strptime(race_date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "race_date must be YYYY-MM-DD"}), 400

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        return jsonify({"error": "user_id must be a valid UUID"}), 400

    session: Session = get_session()
    try:
        plan = training_plan_service.generate_plan(
            session, user_id=user_id, race_date=race_date, race_distance=race_distance
        )
        # success
        return jsonify({"plan_id": plan.id}), 201

    except ValueError as e:
        # used for: "No user found ..." from service
        session.rollback()
        return jsonify({"error": "User not found"}), 404

    except PlanValidationError as e:
        session.rollback()
        return jsonify({"error": str(e)}), 400

    except Exception as e:
        import traceback

        print("🔥 Unhandled Exception in /api/plan/generate:")
        traceback.print_exc()  # ← prints the full traceback
        session.rollback()
        return jsonify({"error": "Internal server error"}), 500

    finally:
        session.close()


from flask import g  # ✅ add if using g.user_id
from sqlalchemy.orm import joinedload
from src.db.models.plans import Plan


@plan_bp.route("/<int:plan_id>", methods=["GET"])
def get_plan_by_id(plan_id):
    """
    Retrieve a plan and its workouts by ID for the authenticated user.
    """
    session: Session = get_session()

    try:
        user_id = getattr(g, "user_id", None)  # replace with static UUID if needed
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401

        plan = (
            session.query(Plan)
            .options(joinedload(Plan.workouts))
            .filter_by(id=plan_id, user_id=user_id)
            .first()
        )

        if not plan:
            return jsonify({"error": "Plan not found"}), 404

        return (
            jsonify(
                {
                    "plan": {
                        "id": plan.id,
                        "plan_name": plan.plan_name,
                        "race_date": (
                            plan.race_date.isoformat() if plan.race_date else None
                        ),
                        "race_distance": plan.race_distance,
                        "notes": plan.notes,
                        "created_by": plan.created_by,
                        "created_at": (
                            plan.created_at.isoformat() if plan.created_at else None
                        ),
                    },
                    "workouts": [
                        {
                            "id": w.id,
                            "date": w.date.isoformat(),
                            "workout_type": w.workout_type,
                            "description": w.description,
                            "miles": w.miles,
                            "intensity": w.intensity,
                        }
                        for w in sorted(plan.workouts, key=lambda w: w.date)
                    ],
                }
            ),
            200,
        )

    except Exception as e:
        import traceback

        print("🔥 Unhandled Exception in GET /api/plan/<id>:")
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500

    finally:
        session.close()


@plan_bp.before_request
def inject_user_id():
    """Simulate Auth0 user via X-User-Id header for testing/dev."""
    user_id = request.headers.get("X-User-Id")
    if user_id:
        try:
            g.user_id = uuid.UUID(user_id)
        except ValueError:
            g.user_id = None

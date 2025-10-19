"""
user_data_routes.py

User Data Management Routes (GDPR Compliance)
===========================================

This module handles user data management for GDPR and Strava API compliance:
- Data export
- Account deletion
- Data access requests

All endpoints require authentication.
"""

from flask import Blueprint, jsonify, request, g
from sqlalchemy import text, delete
from sqlalchemy.dialects.postgresql import UUID
import json
from datetime import datetime

from src.db.db_session import get_session
from src.utils.auth0_jwt import requires_auth
from src.db.models.user_identity import UserIdentity
from src.db.models.user_profile import UserProfile
from src.db.models.user_athletes import UserAthleteLink
from src.db.models.activities import Activity
from src.db.models.plans import Plan
from src.db.models.tokens import Token

user_data_bp = Blueprint("user_data", __name__)


@user_data_bp.get("/user/export-data")
@requires_auth
def export_user_data():
    """
    Export all user data in JSON format (GDPR Article 20 - Right to Data Portability).
    Returns all personal data and Strava activity data for the authenticated user.
    """
    session = get_session()
    try:
        internal_user_id = getattr(g, "user_id", None)

        if not internal_user_id:
            return jsonify({"error": "User not authenticated"}), 401

        # Collect all user data
        export_data = {
            "export_date": datetime.utcnow().isoformat(),
            "user_id": str(internal_user_id),
            "data": {},
        }

        # 1. User Identity
        user_identity = (
            session.query(UserIdentity).filter_by(user_id=internal_user_id).first()
        )
        if user_identity:
            export_data["data"]["identity"] = {
                "email": user_identity.email,
                "email_verified": user_identity.email_verified,
                "name": user_identity.name,
                "picture": user_identity.picture,
                "updated_at": (
                    user_identity.updated_at.isoformat()
                    if user_identity.updated_at
                    else None
                ),
            }

        # 2. User Profile (training preferences)
        user_profile = (
            session.query(UserProfile).filter_by(user_id=internal_user_id).first()
        )
        if user_profile:
            export_data["data"]["profile"] = {
                "age": user_profile.age,
                "gender": user_profile.gender,
                "fitness_level": user_profile.fitness_level,
                "training_days": user_profile.training_days,
                "max_long_run": user_profile.max_long_run,
                "race_distance": user_profile.race_distance,
                "race_date": (
                    user_profile.race_date.isoformat()
                    if user_profile.race_date
                    else None
                ),
                "goal_time": user_profile.goal_time,
                "injury_history": user_profile.injury_history,
                "run_preference": user_profile.run_preference,
            }

        # 3. Athlete Links (Strava connection)
        athlete_links = (
            session.query(UserAthleteLink).filter_by(user_id=internal_user_id).all()
        )
        export_data["data"]["strava_connections"] = [
            {
                "athlete_id": link.athlete_id,
                "connected_at": (
                    link.linked_at.isoformat()
                    if hasattr(link, "linked_at") and link.linked_at
                    else None
                ),
            }
            for link in athlete_links
        ]

        # 4. Activities (Strava data)
        activities = session.query(Activity).filter_by(user_id=internal_user_id).all()
        export_data["data"]["activities"] = [
            {
                "activity_id": act.activity_id,
                "name": act.name,
                "type": act.type,
                "start_date": act.start_date.isoformat() if act.start_date else None,
                "distance": act.distance,
                "moving_time": act.moving_time,
                "average_speed": act.average_speed,
                "average_heartrate": act.average_heartrate,
                "max_heartrate": act.max_heartrate,
                "total_elevation_gain": act.total_elevation_gain,
                "hr_zone_1": act.hr_zone_1,
                "hr_zone_2": act.hr_zone_2,
                "hr_zone_3": act.hr_zone_3,
                "hr_zone_4": act.hr_zone_4,
                "hr_zone_5": act.hr_zone_5,
            }
            for act in activities
        ]

        # 5. Training Plans
        plans = session.query(Plan).filter_by(user_id=internal_user_id).all()
        export_data["data"]["training_plans"] = [
            {
                "plan_id": plan.id,
                "plan_name": plan.plan_name,
                "notes": plan.notes,
                "start_date": plan.start_date.isoformat() if plan.start_date else None,
                "race_date": plan.race_date.isoformat() if plan.race_date else None,
                "race_distance": plan.race_distance,
                "created_at": plan.created_at.isoformat() if plan.created_at else None,
            }
            for plan in plans
        ]

        # Count totals
        export_data["summary"] = {
            "total_activities": len(activities),
            "total_plans": len(plans),
            "total_strava_connections": len(athlete_links),
        }

        return jsonify(export_data), 200

    except Exception as e:
        print(f"❌ Error exporting user data: {e}", flush=True)
        return jsonify({"error": "Failed to export data", "detail": str(e)}), 500
    finally:
        session.close()


@user_data_bp.delete("/user/delete-account")
@requires_auth
def delete_user_account():
    """
    Permanently delete all user data (GDPR Article 17 - Right to Erasure).

    This will delete:
    - User identity
    - User profile
    - User-athlete links
    - All activities
    - All training plans
    - All API tokens

    Deletion is immediate and irreversible.
    """
    session = get_session()
    try:
        internal_user_id = getattr(g, "user_id", None)

        if not internal_user_id:
            return jsonify({"error": "User not authenticated"}), 401

        print(f"🗑️ Starting account deletion for user: {internal_user_id}", flush=True)

        # Track deletions
        deletions = {
            "activities": 0,
            "plans": 0,
            "athlete_links": 0,
            "tokens": 0,
            "profile": 0,
            "identity": 0,
        }

        # 1. Delete activities
        activities_result = (
            session.query(Activity).filter_by(user_id=internal_user_id).delete()
        )
        deletions["activities"] = activities_result
        print(f"  ✓ Deleted {activities_result} activities", flush=True)

        # 2. Delete training plans
        plans_result = session.query(Plan).filter_by(user_id=internal_user_id).delete()
        deletions["plans"] = plans_result
        print(f"  ✓ Deleted {plans_result} training plans", flush=True)

        # 3. Delete athlete links and associated tokens
        athlete_links = (
            session.query(UserAthleteLink).filter_by(user_id=internal_user_id).all()
        )
        for link in athlete_links:
            # Delete tokens for this athlete
            tokens_result = (
                session.query(Token).filter_by(athlete_id=link.athlete_id).delete()
            )
            deletions["tokens"] += tokens_result

        athlete_links_result = (
            session.query(UserAthleteLink).filter_by(user_id=internal_user_id).delete()
        )
        deletions["athlete_links"] = athlete_links_result
        print(
            f"  ✓ Deleted {athlete_links_result} athlete links and {deletions['tokens']} tokens",
            flush=True,
        )

        # 4. Delete user profile
        profile_result = (
            session.query(UserProfile).filter_by(user_id=internal_user_id).delete()
        )
        deletions["profile"] = profile_result
        print(f"  ✓ Deleted user profile", flush=True)

        # 5. Delete user identity (this should cascade to any remaining data)
        identity_result = (
            session.query(UserIdentity).filter_by(user_id=internal_user_id).delete()
        )
        deletions["identity"] = identity_result
        print(f"  ✓ Deleted user identity", flush=True)

        # Commit all deletions
        session.commit()

        print(f"✅ Account deletion complete for user: {internal_user_id}", flush=True)
        print(f"   Summary: {deletions}", flush=True)

        return (
            jsonify(
                {
                    "success": True,
                    "message": "All your data has been permanently deleted",
                    "deleted": deletions,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        session.rollback()
        print(f"❌ Error deleting user account: {e}", flush=True)
        import traceback

        traceback.print_exc()
        return jsonify({"error": "Failed to delete account", "detail": str(e)}), 500
    finally:
        session.close()


@user_data_bp.post("/user/consent")
@requires_auth
def log_user_consent():
    """
    Log user consent for data processing (GDPR compliance).
    Records timestamp and consent details.
    """
    session = get_session()
    try:
        internal_user_id = getattr(g, "user_id", None)

        if not internal_user_id:
            return jsonify({"error": "User not authenticated"}), 401

        data = request.get_json() or {}
        consent_type = data.get("consent_type", "strava_data_access")
        timestamp = data.get("timestamp", datetime.utcnow().isoformat())

        # Log consent (you can store this in a dedicated consent table if needed)
        print(
            f"✅ User consent logged: user={internal_user_id}, type={consent_type}, timestamp={timestamp}",
            flush=True,
        )

        # For now, we'll just acknowledge. In production, you might store this in a consent_log table
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Consent recorded",
                    "user_id": str(internal_user_id),
                    "consent_type": consent_type,
                    "timestamp": timestamp,
                }
            ),
            200,
        )

    except Exception as e:
        print(f"❌ Error logging consent: {e}", flush=True)
        return jsonify({"error": "Failed to log consent", "detail": str(e)}), 500
    finally:
        session.close()


@user_data_bp.get("/user/data-summary")
@requires_auth
def get_data_summary():
    """
    Get a summary of all user data stored in SmartCoach.
    Useful for transparency and GDPR Article 15 (Right of Access).
    """
    session = get_session()
    try:
        internal_user_id = getattr(g, "user_id", None)

        if not internal_user_id:
            return jsonify({"error": "User not authenticated"}), 401

        # Count data items
        activities_count = (
            session.query(Activity).filter_by(user_id=internal_user_id).count()
        )
        plans_count = session.query(Plan).filter_by(user_id=internal_user_id).count()
        athlete_links_count = (
            session.query(UserAthleteLink).filter_by(user_id=internal_user_id).count()
        )

        has_profile = (
            session.query(UserProfile).filter_by(user_id=internal_user_id).first()
            is not None
        )
        has_identity = (
            session.query(UserIdentity).filter_by(user_id=internal_user_id).first()
            is not None
        )

        return (
            jsonify(
                {
                    "user_id": str(internal_user_id),
                    "data_stored": {
                        "activities": activities_count,
                        "training_plans": plans_count,
                        "strava_connections": athlete_links_count,
                        "has_profile": has_profile,
                        "has_identity": has_identity,
                    },
                    "your_rights": {
                        "export": "You can export all your data at /api/user/export-data",
                        "delete": "You can delete your account at /api/user/delete-account",
                        "access": "You can view this summary anytime",
                    },
                }
            ),
            200,
        )

    except Exception as e:
        print(f"❌ Error getting data summary: {e}", flush=True)
        return jsonify({"error": "Failed to get data summary", "detail": str(e)}), 500
    finally:
        session.close()

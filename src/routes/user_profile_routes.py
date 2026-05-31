"""
User Profile Routes Module
==========================

Provides API endpoints for user profile management and onboarding.

Endpoints:
----------
POST /api/onboarding
    Create or update user's onboarding profile

GET  /api/onboarding
    Fetch user's onboarding profile

Dependencies:
-------------
- UserProfileSchema: Pydantic validation schema
- user_profile_dao: Database operations for profiles
- requires_auth: JWT authentication decorator

Data Managed:
------------
- User profile information (race goals, fitness level, etc.)
- Height (feet/inches)
- Age group
- Training preferences
- Race information

Note:
-----
All endpoints use internal UUID (from g.user_id) rather than Auth0 sub.
Profile data is used for personalized training plan generation.
"""

from __future__ import annotations

from typing import Any, Dict
from enum import Enum

from flask import Blueprint, request, jsonify, g, current_app
from pydantic import ValidationError

from src.db.dao.user_profile_dao import save_user_profile, get_user_profile
from src.schemas.user_profile_schema import UserProfileSchema
from src.utils.auth0_jwt import requires_auth
from src.db.db_session import get_session
from src.services.heart_rate.hrmax_resolution_service import HRMaxResolutionService
from src.services.heart_rate.heart_rate_orchestration_service import (
    HeartRateZoneOrchestrationService,
)

# Note: sync_max_hr_from_strava removed - Strava API doesn't return max_heartrate
from src.services.training_plan.recalculate_hr_zones_service import (
    recalculate_hr_zones_for_user,
    recalculate_hr_zones_for_plan,
)
from src.db.models.plans import Plan
from src.utils.user_profile_age_group import age_group_band_from_birth_year
from src.utils.hr_zone_constants import manual_max_hr_bpm_bounds
from src.utils.resting_hr_source import resolve_resting_hr_source_for_save

user_profile_bp = Blueprint("user_profile", __name__, url_prefix="/api")


def _coerce_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


@user_profile_bp.post("/onboarding")
@requires_auth
def submit_user_profile():
    """
    Create/update a user's onboarding profile.
    Always uses the internal UUID from identity, not the raw Auth0 sub.
    """
    internal_user_id = getattr(g, "user_id", None)  # <-- UUID from your middleware
    if not internal_user_id:
        return jsonify({"status": "error", "message": "No internal user_id"}), 401

    data = request.get_json(silent=True) or {}
    current_app.logger.debug(f"[submit_user_profile] Received data: {data}")

    # Mobile clients may send snake_case HR fields.
    if "resting_hr" in data and "restingHr" not in data:
        data["restingHr"] = data["resting_hr"]
    if "resting_hr_source" in data and "restingHrSource" not in data:
        data["restingHrSource"] = data["resting_hr_source"]

    # No mapping needed - age_group is now a string column that stores user-friendly ranges like "30-39"

    # Accept legacy height fields
    if "heightFeet" in data or "heightInches" in data:
        feet = _coerce_int(data.pop("heightFeet", 0))
        inches = _coerce_int(data.pop("heightInches", 0))
        if feet == 0 and inches == 0:
            return (
                jsonify({"status": "error", "message": "Height must be numeric"}),
                400,
            )
        data["height"] = {"feet": feet, "inches": inches}

    # Force user_id to internal UUID (not client-provided)
    data["user_id"] = str(internal_user_id)

    try:
        validated = UserProfileSchema.model_validate(data)
        user_dict: Dict[str, Any] = validated.model_dump(exclude_unset=True)

        # Flatten height
        if "height" in user_dict:
            height = user_dict.pop("height") or {}
            feet = height.get("feet")
            inches = height.get("inches")
            if feet is None or inches is None:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Height (feet and inches) is required",
                        }
                    ),
                    400,
                )
            user_dict["height_feet"] = feet
            user_dict["height_inches"] = inches

        # Map ageGroup to age_group (camelCase -> snake_case; merge + DAO use age_group)
        if "ageGroup" in user_dict:
            user_dict["age_group"] = user_dict.pop("ageGroup")

        if "birthYear" in user_dict:
            user_dict["birth_year"] = user_dict.pop("birthYear")

        # Map unitSystem to unit_system (camelCase -> snake_case)
        if "unitSystem" in user_dict:
            user_dict["unit_system"] = user_dict.pop("unitSystem")

        # Map restingHr to resting_hr (camelCase -> snake_case)
        if "restingHr" in user_dict:
            user_dict["resting_hr"] = user_dict.pop("restingHr")

        requested_resting_hr_source = user_dict.pop("restingHrSource", None)
        if requested_resting_hr_source is None:
            requested_resting_hr_source = user_dict.pop("resting_hr_source", None)
        elif "resting_hr_source" in user_dict:
            user_dict.pop("resting_hr_source", None)

        if "maxHrActive" in user_dict:
            user_dict["max_hr_active"] = user_dict.pop("maxHrActive")

        user_dict.pop("max_hr", None)

        # Enum -> primitive
        for k, v in list(user_dict.items()):
            if isinstance(v, Enum):
                user_dict[k] = v.value
            elif isinstance(v, list):
                user_dict[k] = [
                    item.value if isinstance(item, Enum) else item for item in v
                ]

        # Always overwrite with UUID
        user_dict["user_id"] = str(internal_user_id)

        session = get_session()
        try:
            old_profile = get_user_profile(session, str(internal_user_id)) or {}
            raw_body = request.get_json(silent=True) or {}
            explicit_max_hr_active = any(
                k in raw_body for k in ("max_hr_active", "maxHrActive")
            )

            merged: Dict[str, Any] = {**old_profile, **user_dict}
            merged["user_id"] = str(internal_user_id)

            if merged.get("birth_year") is not None:
                merged["age_group"] = age_group_band_from_birth_year(
                    int(merged["birth_year"])
                )

            if merged.get("max_hr_manual") is not None:
                try:
                    mh_int = int(merged["max_hr_manual"])
                except (TypeError, ValueError):
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "message": "max_hr_manual must be an integer",
                            }
                        ),
                        400,
                    )
                lo, hi = manual_max_hr_bpm_bounds(merged.get("birth_year"))
                if mh_int < lo or mh_int > hi:
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "message": (
                                    f"Max HR must be between {lo} and {hi} bpm"
                                    + (
                                        " for your age (add birth year under Profile for narrower guidance)."
                                        if merged.get("birth_year") is None
                                        else " for your age."
                                    )
                                ),
                            }
                        ),
                        400,
                    )

            old_resting_hr = old_profile.get("resting_hr")
            new_resting_hr = merged.get("resting_hr")

            old_effective = HRMaxResolutionService.get_effective_max_hr(old_profile)

            if (
                merged.get("max_hr_manual") is not None
                and merged.get("max_hr_manual") != old_profile.get("max_hr_manual")
                and not explicit_max_hr_active
            ):
                merged["max_hr_active"] = "manual"

            new_effective = HRMaxResolutionService.get_effective_max_hr(merged)

            resolved_source = resolve_resting_hr_source_for_save(
                raw_body=raw_body,
                requested_source=requested_resting_hr_source,
                new_resting_hr=new_resting_hr,
            )
            if resolved_source is not None:
                from datetime import datetime

                merged["resting_hr_source"] = resolved_source
                merged["resting_hr_updated_at"] = datetime.now()

            merged.pop("max_hr", None)
            save_user_profile(session, merged)

            should_recalc = False
            if new_resting_hr is not None and new_resting_hr != old_resting_hr:
                should_recalc = True
            if new_effective != old_effective:
                should_recalc = True

            if should_recalc:
                try:
                    from src.services.training_plan.recalculate_hr_zones_service import (
                        recalculate_hr_zones_for_user,
                    )

                    recalc_results = recalculate_hr_zones_for_user(
                        session, str(internal_user_id)
                    )
                    current_app.logger.info(
                        f"Recalculated HR zones after HR data update: {len(recalc_results)} plans updated"
                    )
                except Exception as e:
                    current_app.logger.warning(
                        f"Could not recalculate HR zones after HR data update: {e}"
                    )
        finally:
            session.close()

        return (
            jsonify({"status": "success", "message": "Profile saved successfully"}),
            200,
        )

    except ValidationError as e:
        current_app.logger.error(
            f"[submit_user_profile] Validation error: {e.errors()}"
        )
        return jsonify({"status": "error", "errors": e.errors()}), 400
    except Exception as e:
        current_app.logger.exception(
            "submit_user_profile failed for user_id=%s", internal_user_id
        )
        return jsonify({"status": "error", "message": "Failed to save profile"}), 500


@user_profile_bp.get("/onboarding")
@requires_auth
def get_user_profile_route():
    """
    Fetch onboarding profile for the authenticated user.
    Uses internal UUID from g.user_id.
    """
    internal_user_id = getattr(g, "user_id", None)
    if not internal_user_id:
        return jsonify({"status": "error", "message": "No user"}), 401

    session = get_session()
    try:
        profile_dict = get_user_profile(session, str(internal_user_id))
        if not profile_dict:
            return (
                jsonify({"status": "error", "message": "User profile not found"}),
                404,
            )
        try:
            if HeartRateZoneOrchestrationService.sanitize_unreliable_stored_max_hr_auto(
                session, str(internal_user_id)
            ):
                profile_dict = get_user_profile(session, str(internal_user_id))
                if not profile_dict:
                    return (
                        jsonify(
                            {"status": "error", "message": "User profile not found"}
                        ),
                        404,
                    )
        except Exception as e:
            current_app.logger.warning(
                "sanitize_unreliable_stored_max_hr_auto on GET onboarding: %s", e
            )
        profile_dict = dict(profile_dict)
        if profile_dict.get("max_hr_auto") is None:
            try:
                HeartRateZoneOrchestrationService.refresh_auto_hrmax_from_activities(
                    session, str(internal_user_id), force=False
                )
                fresh = get_user_profile(session, str(internal_user_id))
                if fresh:
                    profile_dict = dict(fresh)
            except Exception as e:
                current_app.logger.warning(
                    "refresh_auto_hrmax on GET onboarding failed: %s", e
                )
        profile_dict["max_hr"] = HRMaxResolutionService.get_trusted_max_hr_for_zones(
            profile_dict
        )
        return jsonify({"status": "success", "data": profile_dict}), 200
    except Exception:
        current_app.logger.exception(
            "get_user_profile failed for user_id=%s", internal_user_id
        )
        return jsonify({"status": "error", "message": "Failed to fetch profile"}), 500
    finally:
        session.close()


@user_profile_bp.post("/profile/sync-max-hr")
@requires_auth
def sync_max_hr():
    """
    Note: This endpoint is not functional - Strava API doesn't return max_heartrate.
    Users must enter max HR manually. This endpoint returns an informative error.
    """
    return (
        jsonify(
            {
                "status": "error",
                "message": (
                    "Strava API doesn't provide max heart rate. "
                    "Please enter your max HR manually. "
                    "To find it: Go to Strava → Settings → My Performance → Heart Rate Zones. "
                    "Look for 'Based on Max Heart Rate' and enter that value in your profile."
                ),
            }
        ),
        400,
    )


@user_profile_bp.post("/profile/recalculate-hr-zones")
@requires_auth
def recalculate_hr_zones():
    """
    Recalculate HR zones for all workouts in active plans.
    Useful when max HR changes or HR zone calculation logic is updated.
    """
    internal_user_id = getattr(g, "user_id", None)
    if not internal_user_id:
        return jsonify({"status": "error", "message": "No user"}), 401

    session = get_session()
    try:
        # Optional: allow specifying a plan_id, otherwise recalculate all active plans
        data = request.get_json(silent=True) or {}
        plan_id = data.get("plan_id")

        if plan_id:
            # Recalculate for specific plan
            result = recalculate_hr_zones_for_plan(session, plan_id)
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": f"Recalculated HR zones for plan {plan_id}",
                        "data": result,
                    }
                ),
                200,
            )
        else:
            # Recalculate for all active plans
            results = recalculate_hr_zones_for_user(session, str(internal_user_id))
            total_updated = sum(
                r.get("updated", 0) for r in results.values() if isinstance(r, dict)
            )
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": f"Recalculated HR zones for {len(results)} plan(s)",
                        "data": {
                            "plans": results,
                            "total_workouts_updated": total_updated,
                        },
                    }
                ),
                200,
            )
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        current_app.logger.exception(
            "recalculate_hr_zones failed for user_id=%s", internal_user_id
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Failed to recalculate HR zones: {str(e)}",
                }
            ),
            500,
        )
    finally:
        session.close()

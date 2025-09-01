# src/routes/user_profile_routes.py
from __future__ import annotations

from typing import Any, Dict, Mapping
from enum import Enum

from flask import Blueprint, request, jsonify, g, current_app
from pydantic import ValidationError

from src.db.dao.user_profile_dao import save_user_profile, get_user_profile
from src.schemas.user_profile_schema import UserProfileSchema
from src.utils.auth0_jwt import requires_auth

user_profile_bp = Blueprint("user_profile", __name__, url_prefix="/api")


def _safe_to_mapping(row: Any) -> Mapping[str, Any]:
    if row is None:
        return {}
    m = getattr(row, "_mapping", None)
    if m is not None:
        return m
    if isinstance(row, Mapping):
        return row
    return dict(row)


def normalize_postgres_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    current_app.logger.debug("normalize_postgres_row IN: %r", row)
    out: Dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, list):
            out[k] = [item.value if isinstance(item, Enum) else item for item in v]
        elif isinstance(v, Enum):
            out[k] = v.value
        else:
            out[k] = v
    current_app.logger.debug("normalize_postgres_row OUT: %r", out)
    return out


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
    Always uses the Auth0 subject from the access token; the client cannot override it.
    """
    sub = (getattr(g, "current_user", {}) or {}).get("sub")
    if not sub:
        return jsonify({"status": "error", "message": "No user"}), 401

    data = request.get_json(silent=True) or {}
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

    # Force user_id to token sub (schema still expects it)
    data["user_id"] = sub

    try:
        validated = UserProfileSchema.model_validate(data)
        user_dict: Dict[str, Any] = validated.model_dump(exclude_unset=True)

        # Flatten height if present
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

        # Enum -> primitive
        for k, v in list(user_dict.items()):
            if isinstance(v, Enum):
                user_dict[k] = v.value
            elif isinstance(v, list):
                user_dict[k] = [
                    item.value if isinstance(item, Enum) else item for item in v
                ]

        # Enforce the sub
        user_dict["user_id"] = sub

        save_user_profile(user_dict)
        return (
            jsonify({"status": "success", "message": "Profile saved successfully"}),
            200,
        )

    except ValidationError as e:
        return jsonify({"status": "error", "errors": e.errors()}), 400
    except Exception as e:
        current_app.logger.exception("submit_user_profile failed for sub=%s", sub)
        return jsonify({"status": "error", "message": "Failed to save profile"}), 500


@user_profile_bp.get("/user")
@requires_auth
def get_user():
    """
    Lightweight Auth0 debug endpoint.
    """
    return jsonify({"ok": True, "user": getattr(g, "current_user", {})}), 200


@user_profile_bp.get("/onboarding")
@requires_auth
def get_user_profile_route():
    """
    Fetch onboarding profile for the authenticated user (Auth0 sub).
    """
    sub = (getattr(g, "current_user", {}) or {}).get("sub")
    if not sub:
        return jsonify({"status": "error", "message": "No user"}), 401
    try:
        profile = get_user_profile(sub)
        if not profile:
            return (
                jsonify({"status": "error", "message": "User profile not found"}),
                404,
            )
        normalized = normalize_postgres_row(_safe_to_mapping(profile))
        return jsonify({"status": "success", "data": normalized}), 200
    except Exception:
        current_app.logger.exception("get_user_profile failed for sub=%s", sub)
        return jsonify({"status": "error", "message": "Failed to fetch profile"}), 500

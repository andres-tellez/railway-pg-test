from __future__ import annotations

from typing import Any, Dict, Mapping
from enum import Enum

from flask import Blueprint, request, jsonify
from pydantic import ValidationError

from src.db.dao.user_profile_dao import save_user_profile, get_user_profile
from src.schemas.user_profile_schema import UserProfileSchema
from src.utils.auth0_jwt import requires_auth

user_profile_bp = Blueprint("user_profile", __name__, url_prefix="/api")


def _safe_to_mapping(row: Any) -> Mapping[str, Any]:
    """
    Accepts a SQLAlchemy Row/RowMapping, dict-like, or plain dict and returns a mapping.
    Falls back to dict(row) if possible.
    """
    if row is None:
        return {}
    # SQLAlchemy 1.4/2.0 Row has _mapping which is already dict-like
    m = getattr(row, "_mapping", None)
    if m is not None:
        return m
    if isinstance(row, Mapping):
        return row
    return dict(row)  # last resort


def normalize_postgres_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Convert SQLAlchemy/PG row values into JSON-safe primitives:
    - Enums -> .value
    - Lists[Enum] -> Lists[str]
    - Leaves other primitives as-is
    """
    print("🔍 normalize_postgres_row called with:", row, flush=True)
    normalized: Dict[str, Any] = {}
    for key, val in row.items():
        if isinstance(val, list):
            normalized[key] = [
                item.value if isinstance(item, Enum) else item for item in val
            ]
        elif isinstance(val, Enum):
            normalized[key] = val.value
        else:
            normalized[key] = val
    print("✅ Normalized result:", normalized, flush=True)
    return normalized


def _coerce_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


@requires_auth
@user_profile_bp.route("/onboarding", methods=["POST"])
def submit_user_profile():
    """
    Create/update a user's onboarding profile.

    Body: JSON with at minimum `user_id`.
    Supports height in two forms:
      - flat fields: heightFeet, heightInches
      - nested: {"height": {"feet": int, "inches": int}}
    Pydantic will validate the rest (enums, arrays, etc.).
    """
    data = request.get_json(silent=True)
    print("📨 Incoming payload:", data, flush=True)

    if not isinstance(data, dict):
        return (
            jsonify({"status": "error", "message": "Missing or invalid JSON body"}),
            400,
        )

    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Missing user_id"}), 400

    # 🧱 Normalize height from flat fields (frontend may send heightFeet/heightInches)
    if "heightFeet" in data or "heightInches" in data:
        feet = _coerce_int(data.pop("heightFeet", 0))
        inches = _coerce_int(data.pop("heightInches", 0))
        if feet == 0 and inches == 0:
            # If they provided non-numeric text or blanks, surface a helpful error
            # instead of silently storing 0/0.
            return (
                jsonify({"status": "error", "message": "Height must be numeric"}),
                400,
            )
        data["height"] = {"feet": feet, "inches": inches}
        print("🔧 Normalized + coerced height:", data["height"], flush=True)

    try:
        # Validate + coerce to domain model
        validated = UserProfileSchema.model_validate(data)
        print(f"✅ Schema validated for user_id={user_id}", flush=True)

        user_dict: Dict[str, Any] = validated.model_dump(exclude_unset=True)
        print("📤 model_dump result:", user_dict, flush=True)

        # 🔁 Flatten height into DB columns if present
        if "height" in user_dict:
            height_obj = user_dict.pop("height") or {}
            feet = height_obj.get("feet")
            inches = height_obj.get("inches")

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
            print(
                f"📐 Flattened height_feet={feet}, height_inches={inches}", flush=True
            )

        # 🧼 Coerce Enums/lists of Enums to primitive values for DB
        for k, v in list(user_dict.items()):
            if isinstance(v, Enum):
                user_dict[k] = v.value
            elif isinstance(v, list):
                user_dict[k] = [
                    item.value if isinstance(item, Enum) else item for item in v
                ]

        # Ensure the user id is always set/overrides anything in payload
        user_dict["user_id"] = user_id

        # ✅ Include longestRun if present
        if "longestRun" in validated.model_fields_set:
            user_dict["longest_run"] = validated.longestRun

        print("📦 FINAL user_dict going to DB:", user_dict, flush=True)

        # Upsert via DAO
        save_user_profile(user_dict)
        return (
            jsonify({"status": "success", "message": "Profile saved successfully"}),
            200,
        )

    except ValidationError as e:
        print(f"❌ Validation error for user_id={user_id}: {e.errors()}", flush=True)
        return jsonify({"status": "error", "errors": e.errors()}), 400
    except Exception as e:
        print(f"❌ Database error for user_id={user_id}: {e}", flush=True)
        return jsonify({"status": "error", "message": "Failed to save profile"}), 500


@requires_auth
@user_profile_bp.route("/onboarding", methods=["GET"])
def get_user_profile_route():
    """
    Fetch a user's onboarding profile.
    Query param: user_id
    """
    user_id = request.args.get("user_id")
    print(f"🌐 Incoming GET /onboarding with user_id={user_id}", flush=True)

    if not user_id:
        return jsonify({"status": "error", "message": "Missing user_id"}), 400

    try:
        profile = get_user_profile(user_id)
        if not profile:
            return (
                jsonify({"status": "error", "message": "User profile not found"}),
                404,
            )

        normalized = normalize_postgres_row(_safe_to_mapping(profile))
        return jsonify({"status": "success", "data": normalized}), 200

    except Exception as e:
        print(f"❌ Error fetching profile for user_id={user_id}: {e}", flush=True)
        return jsonify({"status": "error", "message": "Failed to fetch profile"}), 500

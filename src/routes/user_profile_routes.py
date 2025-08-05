from flask import Blueprint, request, jsonify
from pydantic import ValidationError
from enum import Enum
from src.db.dao.user_profile_dao import save_user_profile, get_user_profile
from src.schemas.user_profile_schema import UserProfileSchema

user_profile_bp = Blueprint("user_profile", __name__, url_prefix="/api")


def normalize_postgres_row(row: dict) -> dict:
    print("🔍 normalize_postgres_row called with:", row, flush=True)
    normalized = {}
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


@user_profile_bp.route("/onboarding", methods=["POST"])
def submit_user_profile():
    data = request.get_json()
    print("📨 Incoming payload:", data, flush=True)

    if not data:
        return jsonify({"status": "error", "message": "Missing JSON body"}), 400

    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Missing user_id"}), 400

    # 🧱 Normalize height from flat fields
    if "heightFeet" in data or "heightInches" in data:
        try:
            feet = int(data.pop("heightFeet", 0))
            inches = int(data.pop("heightInches", 0))
            data["height"] = {"feet": feet, "inches": inches}
            print("🔧 Normalized + coerced height:", data["height"], flush=True)
        except ValueError:
            return (
                jsonify({"status": "error", "message": "Height must be numeric"}),
                400,
            )

    try:
        validated = UserProfileSchema.model_validate(data)
        print(f"✅ Schema validated for user_id={user_id}", flush=True)

        user_dict = validated.model_dump(exclude_unset=True)
        print("📤 model_dump result:", user_dict, flush=True)

        # 🔁 Flatten height into DB columns
        if "height" in user_dict:
            height_obj = user_dict.pop("height")
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

        # 🧼 Coerce Enums to values
        for k, v in user_dict.items():
            if isinstance(v, Enum):
                user_dict[k] = v.value
            elif isinstance(v, list):
                user_dict[k] = [
                    item.value if isinstance(item, Enum) else item for item in v
                ]

        # ✅ Fix hasInjury
        if isinstance(user_dict.get("hasInjury"), bool):
            user_dict["hasInjury"] = "Yes" if user_dict["hasInjury"] else "No"

        user_dict["user_id"] = user_id
        print("📦 FINAL user_dict going to DB:", user_dict, flush=True)

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


@user_profile_bp.route("/onboarding", methods=["GET"])
def get_user_profile_route():
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

        normalized = normalize_postgres_row(dict(profile))
        return jsonify({"status": "success", "data": normalized}), 200

    except Exception as e:
        print(f"❌ Error fetching profile for user_id={user_id}: {e}", flush=True)
        return jsonify({"status": "error", "message": "Failed to fetch profile"}), 500

"""
Deterministic Coach ``agent-messages`` turns for structured profile patches.

Pairs with mobile ``structured_input_only`` + ``structured_input.kind``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Union

from pydantic import ValidationError

from src.db.dao.user_profile_dao import get_user_profile, save_user_profile
from src.db.models.conversations import Conversation, ConversationMessage
from src.schemas.user_profile_schema import UserProfileSchema
from src.utils.user_profile_age_group import age_group_band_from_birth_year

logger = logging.getLogger("smartcoach_mobile_coach")


def coerce_structured_patch_user_profile_birth_year(data: dict) -> Optional[int]:
    raw = data.get("structured_input")
    if not isinstance(raw, dict):
        return None
    if str(raw.get("kind") or "").strip() != "patch_user_profile":
        return None
    up = raw.get("updates")
    if not isinstance(up, dict):
        return None
    by = up.get("birthYear")
    if by is None:
        by = up.get("birth_year")
    if by is None:
        return None
    try:
        y = int(by)
    except (TypeError, ValueError):
        return None
    try:
        UserProfileSchema.model_validate(
            {"user_id": "00000000-0000-0000-0000-000000000001", "birthYear": y}
        )
    except ValidationError:
        return None
    return y


@dataclass
class PatchBirthYearApplied:
    assistant_payload: Dict[str, Any]
    user_message: ConversationMessage


def maybe_apply_patch_user_profile_birth_year(
    session: Any,
    *,
    internal_user_id: str,
    birth_year: int,
    conversation: Conversation,
    message_body: str,
    prior_messages_count: int,
) -> Union[PatchBirthYearApplied, Dict[str, Any]]:
    """
    Persist profile birth_year (+ derived age_group) and append transcript rows.

    Returns PatchBirthYearApplied on success, or `{ "status": int, "error": ..., "detail": ... }` on failure.
    """
    old_profile = get_user_profile(session, str(internal_user_id))
    if not old_profile:
        return {
            "status": 400,
            "error": "profile_required",
            "detail": "Complete onboarding profile before saving birth year from Coach.",
        }

    merged: Dict[str, Any] = dict(old_profile)
    merged["birth_year"] = birth_year
    merged["age_group"] = age_group_band_from_birth_year(birth_year)
    merged["user_id"] = str(internal_user_id)

    merged.pop("max_hr", None)
    save_user_profile(session, merged)

    assistant_payload: Dict[str, Any] = {
        "type": "text",
        "content": "Got it — I've saved your birth year.",
        "data": {},
    }
    serialized = json.dumps(assistant_payload, separators=(",", ":"))

    user_msg = ConversationMessage(
        conversation_id=conversation.id,
        role="user",
        content=message_body.strip(),
    )
    session.add(user_msg)
    assistant_msg = ConversationMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=serialized,
    )
    session.add(assistant_msg)

    if prior_messages_count == 0:
        conversation.title = message_body.strip()[:50] + (
            "..." if len(message_body.strip()) > 50 else ""
        )
    conversation.updated_at = datetime.utcnow()

    logger.info(
        "[smartcoach_mobile_coach] patch_user_profile birth_year structured_only user=%s year=%s",
        str(internal_user_id)[:8],
        birth_year,
    )

    session.flush()

    return PatchBirthYearApplied(
        assistant_payload=assistant_payload, user_message=user_msg
    )

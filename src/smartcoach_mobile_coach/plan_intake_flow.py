"""
Deterministic plan-intake helpers for coach-driven plan creation.

This module keeps collection/validation state outside the LLM:
- merge partial updates from conversation turns
- validate normalized fields
- report missing required fields
- build a final PlanCreateSchema payload for deterministic generation
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from dateutil import parser as date_parser

from src.schemas.plan_schema import PlanCreateSchema, PrimaryGoal
from src.utils.date_helpers import DAY_NAMES_ABBREV

REQUIRED_FIELDS: tuple[str, ...] = (
    "race_date",
    "race_distance",
    "primary_goal",
    "training_days",
)


def _normalize_goal(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    t = value.strip().lower()
    if not t:
        return None
    if t in ("just finish", "finish", "complete", "complete race"):
        return PrimaryGoal.JUST_FINISH.value
    if t in ("target time", "goal time", "time goal", "pr", "pb"):
        return PrimaryGoal.TARGET_TIME.value
    return None


def _normalize_day(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    t = value.strip().lower()
    if not t:
        return None
    aliases = {
        "mon": "Mon",
        "monday": "Mon",
        "tue": "Tue",
        "tues": "Tue",
        "tuesday": "Tue",
        "wed": "Wed",
        "wednesday": "Wed",
        "thu": "Thu",
        "thur": "Thu",
        "thurs": "Thu",
        "thursday": "Thu",
        "fri": "Fri",
        "friday": "Fri",
        "sat": "Sat",
        "saturday": "Sat",
        "sun": "Sun",
        "sunday": "Sun",
    }
    return aliases.get(t)


def _normalize_training_days(value: Any) -> Optional[List[str]]:
    raw_days: List[Any]
    if isinstance(value, list):
        raw_days = value
    elif isinstance(value, str):
        cleaned = value.replace("/", ",").replace(" and ", ",")
        raw_days = [p.strip() for p in cleaned.split(",") if p.strip()]
    else:
        return None

    out: List[str] = []
    for d in raw_days:
        nd = _normalize_day(d)
        if nd is None:
            return None
        if nd not in out:
            out.append(nd)
    return out or None


def _normalize_date_yyyy_mm_dd(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    t = value.strip()[:10]
    try:
        datetime.strptime(t, "%Y-%m-%d")
        return t
    except ValueError:
        return None


def _parse_race_date_natural_language(raw: Any) -> Optional[str]:
    """
    Accept strict YYYY-MM-DD or common spoken / typed race dates.

    Uses dateutil for flexible phrases (e.g. "October 11 of 2026", "Oct 11, 2026").
    """
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    strict = _normalize_date_yyyy_mm_dd(s)
    if strict:
        return strict
    try:
        default = datetime.now().replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
        dt = date_parser.parse(s, default=default, fuzzy=True)
    except (ValueError, TypeError, OverflowError, OSError):
        return None
    return dt.date().isoformat()


def _normalize_target_time_phrase(raw: Any) -> Optional[str]:
    """
    Map common spoken goal times into a short clock string (max 20 chars for schema).

    Examples: "3 hours 40 minutes" -> "3:40:00", "3h40m" -> "3:40:00", "3:40" -> "3:40".
    """
    if not isinstance(raw, str):
        return None
    t = raw.strip()
    if not t:
        return None
    if re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", t):
        return t[:20]
    compact = re.sub(r"\s+", " ", t)
    m = re.match(
        r"(?i)^\s*(\d{1,2})\s*h(?:rs?|ours?)?\s*(\d{1,2})\s*m(?:ins?|inutes?)?\s*$",
        compact,
    )
    if m:
        return f"{int(m.group(1))}:{int(m.group(2)):02d}:00"[:20]
    m = re.search(
        r"(?i)(\d{1,2})\s*(?:hours?|hrs?)\s*(?:and\s*)?(\d{1,2})\s*(?:minutes?|mins?)",
        compact,
    )
    if m:
        return f"{int(m.group(1))}:{int(m.group(2)):02d}:00"[:20]
    return t[:20]


def user_confirms_plan_intake(user_message: str) -> bool:
    """
    True when the user is clearly confirming a ready-to-generate plan summary.

    Short messages only; negation / correction cues disable the fast path.
    """
    raw = (user_message or "").strip()
    if not raw or len(raw) > 96:
        return False
    s = raw.lower()
    if re.search(
        r"\b(but|except|change|wrong|actually|instead|not quite|hold on|wait)\b",
        s,
    ):
        return False
    if re.search(r"\b(no|nope|cancel|stop|don'?t)\b", s):
        return False
    core = re.sub(r"[\s.!?…,;:\"'`]+", " ", s).strip()
    if raw.strip() in ("👍", "✓", "✅"):
        return True
    one_word = core.replace(" ", "")
    if one_word in (
        "y",
        "ye",
        "yes",
        "yep",
        "yup",
        "ok",
        "okay",
        "k",
        "sure",
        "👍",
        "✓",
    ):
        return True
    if re.match(
        r"^(yes|yeah|yep|yup|correct|right|confirm|confirmed|absolutely|definitely|"
        r"looks good|look good|sounds good|sound good|go ahead|please do|"
        r"that'?s right|that is right|all good|perfect)(\b|[\s.!?]|$)",
        core,
    ):
        return True
    return False


def _coerce_state(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    out = dict(raw)
    if not isinstance(out.get("draft"), dict):
        out["draft"] = {}
    return out


def _missing_required_fields(draft: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for f in REQUIRED_FIELDS:
        v = draft.get(f)
        if v is None:
            out.append(f)
            continue
        if isinstance(v, str) and not v.strip():
            out.append(f)
            continue
        if isinstance(v, list) and not v:
            out.append(f)
            continue
    if draft.get("primary_goal") == PrimaryGoal.TARGET_TIME.value and not (
        isinstance(draft.get("target_time"), str)
        and draft.get("target_time", "").strip()
    ):
        out.append("target_time")
    return out


def _human_missing_label(field_name: str) -> str:
    labels = {
        "race_date": "race date",
        "race_distance": "race distance",
        "primary_goal": "goal type",
        "training_days": "training days",
        "target_time": "target time",
        "long_run_day": "long run day",
    }
    return labels.get(field_name, field_name.replace("_", " "))


def _confirmation_summary(draft: Dict[str, Any]) -> str:
    race_distance = draft.get("race_distance") or "race"
    race_date = draft.get("race_date") or "TBD date"
    goal = draft.get("primary_goal") or "TBD goal"
    tdays = ", ".join(draft.get("training_days") or [])
    lr = draft.get("long_run_day") or "auto"
    return (
        f"{race_distance} on {race_date}; goal: {goal}; training days: {tdays}; "
        f"long run day: {lr}."
    )


def _auto_fill_long_run_day(draft: Dict[str, Any]) -> None:
    if draft.get("long_run_day"):
        return
    tdays = draft.get("training_days")
    if not isinstance(tdays, list) or not tdays:
        return
    order = {d: i for i, d in enumerate(DAY_NAMES_ABBREV)}
    draft["long_run_day"] = sorted(tdays, key=lambda d: order.get(d, -1))[-1]


def update_plan_intake_state(
    current_state: Optional[Dict[str, Any]],
    *,
    updates: Optional[Dict[str, Any]] = None,
    clear_fields: Optional[List[str]] = None,
    reset: bool = False,
) -> Dict[str, Any]:
    state = _coerce_state(None if reset else current_state)
    draft: Dict[str, Any] = dict(state.get("draft") or {})
    errors: List[str] = []

    if clear_fields:
        for f in clear_fields:
            if isinstance(f, str) and f in draft:
                draft.pop(f, None)

    up = updates or {}
    if not isinstance(up, dict):
        up = {}

    for key, raw in up.items():
        if key == "race_date":
            nd = _parse_race_date_natural_language(raw)
            if nd is None:
                errors.append(
                    "race_date must be a real calendar day "
                    "(e.g. 2026-10-11 or October 11, 2026)."
                )
            else:
                draft["race_date"] = nd
        elif key == "race_distance":
            if isinstance(raw, str) and raw.strip():
                draft["race_distance"] = raw.strip()
            else:
                errors.append("race_distance must be a non-empty string.")
        elif key == "race_name":
            if raw is None:
                draft.pop("race_name", None)
            elif isinstance(raw, str):
                draft["race_name"] = raw.strip()[:255]
            else:
                errors.append("race_name must be a string.")
        elif key == "race_location":
            if raw is None:
                draft.pop("race_location", None)
            elif isinstance(raw, str):
                draft["race_location"] = raw.strip()[:255]
            else:
                errors.append("race_location must be a string.")
        elif key == "primary_goal":
            ng = _normalize_goal(raw)
            if ng is None:
                errors.append("primary_goal must be 'Just Finish' or 'Target Time'.")
            else:
                draft["primary_goal"] = ng
        elif key == "target_time":
            if raw is None:
                draft.pop("target_time", None)
            elif isinstance(raw, str) and raw.strip():
                draft["target_time"] = _normalize_target_time_phrase(raw.strip())
            else:
                errors.append("target_time must be a non-empty string when provided.")
        elif key == "training_days":
            ndays = _normalize_training_days(raw)
            if ndays is None:
                errors.append(
                    "training_days must be day abbreviations or names (e.g. Tue, Thu, Sat)."
                )
            else:
                draft["training_days"] = ndays
        elif key == "long_run_day":
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                draft.pop("long_run_day", None)
            else:
                nd = _normalize_day(raw)
                if nd is None:
                    errors.append("long_run_day must be a valid weekday.")
                else:
                    draft["long_run_day"] = nd
        elif key in ("notes", "plan_name", "user_timezone"):
            if raw is None:
                draft.pop(key, None)
            elif isinstance(raw, str):
                draft[key] = raw.strip()
            else:
                errors.append(f"{key} must be a string.")

    if "training_days" in draft and draft.get("long_run_day"):
        tdays = draft.get("training_days") or []
        if draft["long_run_day"] not in tdays:
            errors.append("long_run_day must be one of training_days.")

    _auto_fill_long_run_day(draft)

    missing = _missing_required_fields(draft)
    status = "ready_to_confirm" if not missing else "collecting"
    state = {
        "version": 1,
        "status": status,
        "draft": draft,
        "missing_required": missing,
        "missing_required_labels": [_human_missing_label(m) for m in missing],
        "ready_to_generate": len(missing) == 0 and len(errors) == 0,
        "errors": errors,
        "confirmation_summary": _confirmation_summary(draft),
    }
    return state


def build_plan_request_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    draft = dict((state or {}).get("draft") or {})
    if not draft:
        raise ValueError("No plan intake draft found.")

    # Final schema validation (deterministic gate)
    validated = PlanCreateSchema.model_validate(draft)
    out = validated.model_dump()
    if not out.get("long_run_day"):
        _auto_fill_long_run_day(out)
    return out


def summarize_this_week_from_plan_rows(
    plan_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build a compact, model-friendly summary from persisted workout rows.
    """
    if not plan_rows:
        return {"workouts": [], "count": 0, "total_miles": 0.0}
    sorted_rows = sorted(plan_rows, key=lambda r: r.get("date") or "")
    first = sorted_rows[0].get("date")
    try:
        first_date = datetime.strptime(str(first)[:10], "%Y-%m-%d").date()
    except ValueError:
        first_date = date.today()
    week_start = first_date
    week_end = week_start.fromordinal(week_start.toordinal() + 6)
    in_week: List[Dict[str, Any]] = []
    for r in sorted_rows:
        ds = str(r.get("date") or "")[:10]
        try:
            d = datetime.strptime(ds, "%Y-%m-%d").date()
        except ValueError:
            continue
        if week_start <= d <= week_end:
            in_week.append(r)

    total = 0.0
    simple_rows: List[Dict[str, Any]] = []
    for r in in_week:
        miles = float(r.get("miles") or 0.0)
        total += miles
        simple_rows.append(
            {
                "date": r.get("date"),
                "workout_type": r.get("workout_type"),
                "miles": round(miles, 2),
                "description": r.get("description"),
            }
        )

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "count": len(simple_rows),
        "total_miles": round(total, 2),
        "workouts": simple_rows,
    }

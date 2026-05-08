"""
Deterministic plan-intake helpers for coach-driven plan creation.

This module keeps collection/validation state outside the LLM:
- merge partial updates from conversation turns
- validate normalized fields
- report missing required fields
- build a final PlanCreateSchema payload for deterministic generation
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from dateutil import parser as date_parser

from src.coaching_intelligence.intake_alignment import evaluate_intake_alignment_state
from src.schemas.plan_schema import PlanCreateSchema, PrimaryGoal
from src.utils.date_helpers import DAY_NAMES_ABBREV

_POSTURE_STATES_FOR_STORAGE = frozenset(
    {"PERFORMANCE_LEANING", "BALANCED", "DURABILITY_FIRST"}
)

REQUIRED_FIELDS: tuple[str, ...] = (
    "race_distance",
    "race_date",
    "primary_goal",
    "training_days",
)

PLAN_UX_STAGE_UNDERSTAND_RUNNER = "understand_runner"
PLAN_UX_STAGE_GOAL_ALIGNMENT = "goal_alignment"
PLAN_UX_STAGE_DETAILS = "details"
PLAN_UX_STAGE_CONFIRM = "confirm"
PLAN_UX_STAGE_FAST_TRACK = "fast_track"
PLAN_UX_STAGE_GENERATED = "generated"


def _intake_alignment_feature_enabled() -> bool:
    return (
        os.getenv("SMARTCOACH_ENABLE_INTAKE_ALIGNMENT_V1") or ""
    ).strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _recompute_alignment_branch(
    alignment: Dict[str, Any],
    draft: Dict[str, Any],
) -> Dict[str, Any]:
    """
    After merging alignment answers, refresh ``alignment.state`` so ``ui_prompt`` and
    observability match resolved flags (stale state used to repeat the same chips).
    """
    if not _intake_alignment_feature_enabled():
        return alignment
    stance = alignment.get("ambition_stance")
    if not stance:
        return alignment
    answers = dict(alignment.get("answers") or {})
    asked = [
        str(x)
        for x in list(alignment.get("asked_categories") or [])
        if isinstance(x, str)
    ]
    qc_raw = alignment.get("question_count")
    try:
        qc = int(qc_raw) if qc_raw is not None else 0
    except (TypeError, ValueError):
        qc = 0
    if qc == 0 and asked:
        qc = len(asked)
    qc = max(0, min(3, qc))

    ast = evaluate_intake_alignment_state(
        ambition_stance=str(stance),
        primary_goal=str(draft.get("primary_goal") or ""),
        frequency_flexible=answers.get("frequency_flexible"),
        posture_priority=answers.get("posture_priority"),
        timeline_flexible=answers.get("timeline_flexible"),
        question_count=qc,
    )
    answers = dict(answers)
    ps_state = ast.get("posture_state")
    if not answers.get("posture_priority") and isinstance(ps_state, str):
        if ps_state in _POSTURE_STATES_FOR_STORAGE:
            answers["posture_priority"] = ps_state
    prior_attr = [
        str(x) for x in list(alignment.get("attributions") or []) if isinstance(x, str)
    ]
    merged_attr = sorted(set(prior_attr + list(ast.get("attributions") or [])))
    observability = dict(alignment.get("observability") or {})
    observability.update(
        {
            "pause_fired": bool(ast.get("pause_required")),
            "posture_selected": ast.get("posture_state"),
            "alignment_resolved": bool(ast.get("generation_ready")),
            "question_count": ast.get("question_count"),
        }
    )
    return {
        **alignment,
        "answers": answers,
        "state": ast,
        "attributions": merged_attr,
        "observability": observability,
    }


def schedule_confirmation_system_section(intake_state: Optional[Dict[str, Any]]) -> str:
    """
    When the client shows Yes/No for draft training days, steer model prose to match chips.
    """
    if not isinstance(intake_state, dict):
        return ""
    ux = intake_state.get("ux") if isinstance(intake_state.get("ux"), dict) else {}
    if not ux.get("schedule_confirm_before_posture"):
        return ""
    return (
        "## Schedule confirmation (matches inline Yes / No)\n"
        "Inline controls ask whether their **current draft training days** are correct **before** "
        "any alignment tradeoff (posture) question.\n"
        "- Ground briefly in what they already committed (weekdays from intake).\n"
        "- Ask **one** yes/no style closing question that matches **Yes** / **No, change days** — "
        "not posture, performance, durability, or recovery philosophy.\n"
        "- Do **not** ask them to confirm posture or priorities on this turn."
    ).strip()


def plan_intake_alignment_pause_active(intake_state: Optional[Dict[str, Any]]) -> bool:
    """
    True when intake alignment is blocking generation (pause_required, not resolved).

    Used by orchestrator guardrails and UI hints — same condition as
    ``alignment_pause_coaching_facts_system_section`` emitting non-empty text.
    """
    if not isinstance(intake_state, dict):
        return False
    al = intake_state.get("alignment")
    if not isinstance(al, dict):
        return False
    st = al.get("state")
    if not isinstance(st, dict):
        return False
    return bool(st.get("pause_required")) and not bool(st.get("generation_ready"))


def alignment_pause_coaching_facts_system_section(
    intake_state: Optional[Dict[str, Any]],
) -> str:
    """
    Deterministic facts + instructions so the LLM interprets tension before alignment chips.
    Does not prescribe user-facing wording.
    """
    if not isinstance(intake_state, dict):
        return ""
    if not _intake_alignment_feature_enabled():
        return ""
    al = intake_state.get("alignment")
    if not isinstance(al, dict):
        return ""
    st = al.get("state")
    if not isinstance(st, dict):
        return ""
    if not plan_intake_alignment_pause_active(intake_state):
        return ""
    draft = intake_state.get("draft")
    if not isinstance(draft, dict):
        draft = {}
    cats = [
        str(x)
        for x in list(st.get("allowed_question_categories") or [])
        if isinstance(x, str)
    ]
    next_cat = cats[0] if cats else ""
    tdays = draft.get("training_days")
    day_list = tdays if isinstance(tdays, list) else []
    day_count = len(day_list)
    days_preview = ", ".join(str(d) for d in day_list) if day_list else "n/a"

    return (
        "## Intake alignment — coach-facing facts (read silently; do not dump as a list to the user)\n"
        "This section appears **after** **## Athlete activity snapshot** when that block is present—use it.\n"
        "**Ground your opening** in **at least one concrete fact** from the activity snapshot "
        "(e.g. typical weekly mileage band, run frequency, or longest recent run) **and** tie it to what "
        "they already entered (goal type, target time if set, training days). Show you are reasoning "
        "about *their* situation—not generic advice.\n"
        "\n"
        "Before the **inline controls** ask the next question, write like a coach—not a workflow:\n"
        "1. **Interpret** what the signals imply for *this* athlete in **1–2 short sentences**.\n"
        "2. **Name the tension or tradeoff** (stated goal vs current structure / volume) in **one sentence**.\n"
        "3. **Explain why the next question matters** for staying healthy, consistent, or realistic pacing—in **one sentence**.\n"
        "4. Then ask **one** question that matches the **inline chips** (do not invent a different question).\n"
        "\n"
        "Deterministic context (ground truth; translate into plain language—never echo raw key names or rule codes to the user):\n"
        f"- **Ambition stance:** {al.get('ambition_stance')}\n"
        f"- **Baseline band (recent volume proxy):** {al.get('baseline_band')}\n"
        f"- **Goal demand:** {al.get('goal_demand')}\n"
        f"- **Primary goal (draft):** {draft.get('primary_goal')}\n"
        f"- **Target time (draft):** {draft.get('target_time') or 'n/a'}\n"
        f"- **Training days:** {day_count} ({days_preview})\n"
        f"- **Next alignment topic (must match chips):** {next_cat or 'n/a'}\n"
        "\n"
        "If there is **no** activity snapshot block (thin data), say so briefly and lean on the deterministic "
        "stance/band lines above—still connect goal and schedule before the chips.\n"
        "\n"
        "Keep coaching prose before the chips to **at most 5 short sentences** total (interpretation may need two); "
        "warm and specific; no filler openers (“Great!”, “I’m here to help”)."
    ).strip()


def structured_intake_core_v1_enabled() -> bool:
    """
    When true, core plan-intake athletic fields are owned by structured commits
    (inline controls + structured_input), not conversational NL merge into draft.
    """
    raw = (os.getenv("SMARTCOACH_STRUCTURED_INTAKE_CORE_V1") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _normalize_goal(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    t = value.strip().lower()
    if not t:
        return None
    just_finish = (
        "just finish",
        "finish",
        "complete",
        "complete race",
        "just want to finish",
        "cross the finish line",
        "finish the race",
        "finish healthy",
        "no time goal",
        "no specific time",
        "survive",
        "participate",
    )
    if t in just_finish:
        return PrimaryGoal.JUST_FINISH.value
    target_time = (
        "target time",
        "goal time",
        "time goal",
        "pr",
        "pb",
        "personal record",
        "beat my pr",
        "new pr",
        "get a pr",
        "set a time",
        "time-based",
        "clock goal",
        "qualify",
        "bq",
        "boston qualifier",
    )
    if t in target_time:
        return PrimaryGoal.TARGET_TIME.value
    # Light substring cues (whole-string already handled above).
    if any(
        phrase in t
        for phrase in (
            "personal record",
            "goal time",
            "target time",
            "qualifying time",
        )
    ):
        return PrimaryGoal.TARGET_TIME.value
    if any(
        phrase in t
        for phrase in (
            "just finish",
            "just want to finish",
            "only want to finish",
        )
    ):
        return PrimaryGoal.JUST_FINISH.value
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
        "mondays": "Mon",
        "tue": "Tue",
        "tues": "Tue",
        "tuesday": "Tue",
        "tuesdays": "Tue",
        "wed": "Wed",
        "wednesday": "Wed",
        "wednesdays": "Wed",
        "thu": "Thu",
        "thur": "Thu",
        "thurs": "Thu",
        "thursday": "Thu",
        "thursdays": "Thu",
        "fri": "Fri",
        "friday": "Fri",
        "fridays": "Fri",
        "sat": "Sat",
        "saturday": "Sat",
        "saturdays": "Sat",
        "sun": "Sun",
        "sunday": "Sun",
        "sundays": "Sun",
    }
    return aliases.get(t)


def _text_suggests_half_marathon(s: str) -> bool:
    """Match `race_distance_factory_v2._is_half_marathon` without importing a private helper."""
    if not s:
        return False
    tl = s.lower()
    return "half" in tl or "13.1" in tl


def _try_infer_race_distance(text: str) -> Optional[str]:
    """
    Infer Half Marathon vs Marathon from free text (race names, user phrases).

    Returns None when there is no clear signal so we do not guess arbitrary events.
    """
    if not isinstance(text, str):
        return None
    s = text.strip()
    if not s:
        return None
    if _text_suggests_half_marathon(s):
        return "Half Marathon"
    tl = s.lower()
    if "marathon" in tl or "26.2" in tl:
        return "Marathon"
    if re.search(r"\bfull\b", tl) and "half" not in tl:
        return "Marathon"
    return None


def _normalize_race_distance_intake(raw: str) -> str:
    """Map common synonyms onto supported labels; otherwise keep stripped text."""
    s = raw.strip()
    if not s:
        return s
    inferred = _try_infer_race_distance(s)
    if inferred:
        return inferred
    return s


def _fill_race_distance_from_named_event(draft: Dict[str, Any]) -> None:
    """When distance is still empty, infer from race_name / location / plan_name if unambiguous."""
    rd = draft.get("race_distance")
    if isinstance(rd, str) and rd.strip():
        return
    parts: List[str] = []
    for k in ("race_name", "race_location", "plan_name"):
        v = draft.get(k)
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())
    blob = " ".join(parts)
    inferred = _try_infer_race_distance(blob)
    if inferred:
        draft["race_distance"] = inferred


# Prefixes too generic to treat as a race title when followed by "Marathon".
_RACE_NAME_TRIVIAL_PREFIXES = frozenset(
    {
        "my",
        "a",
        "an",
        "the",
        "any",
        "this",
        "that",
        "our",
        "your",
        "for",
        "full",
        "half",
        "running",
        "do",
        "doing",
        "training",
        "train",
        "plan",
        "race",
        "next",
        "another",
        "first",
        "spring",
        "fall",
        "winter",
        "summer",
    }
)

# Leading words that often start the *sentence*, not the race title (overlap scan).
_RACE_NAME_BOILERPLATE_FIRST = frozenset(
    {
        "please",
        "can",
        "could",
        "would",
        "should",
        "will",
        "help",
        "want",
        "wanna",
        "need",
        "looking",
        "hoping",
        "trying",
        "build",
        "create",
        "make",
        "give",
        "set",
        "start",
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank",
        "ok",
        "okay",
        "yes",
        "yeah",
        "yep",
        "sure",
        "i",
        "we",
        "you",
        "got",
    }
)


def _extract_race_name_from_user_text(text: str) -> Optional[str]:
    """
    Best-effort event title from the user's message (e.g. "Chicago Marathon").

    Conservative: only matches ... Half Marathon / ... Marathon patterns, skips
    trivial leading words ("my marathon"), returns None when unsure.
    """
    if not isinstance(text, str):
        return None
    s = text.strip()
    if not s:
        return None
    if len(s) > 2000:
        s = s[:2000]

    def _clean_prefix(raw: str) -> str:
        p = re.sub(r"\s+", " ", raw.strip())
        p = re.sub(r"(?i)^the\s+", "", p).strip()
        return p

    def _usable_prefix(p: str) -> bool:
        if len(p) < 2:
            return False
        pl = p.lower()
        if pl in _RACE_NAME_TRIVIAL_PREFIXES:
            return False
        if pl.isdigit():
            return False
        first = pl.split()[0] if pl.split() else ""
        if first in _RACE_NAME_TRIVIAL_PREFIXES:
            return False
        if first in _RACE_NAME_BOILERPLATE_FIRST:
            return False
        return True

    def _best_name_from_pattern(
        pat: re.Pattern[str], suffix_words: str
    ) -> Optional[str]:
        """Scan with overlapping windows so we keep the longest usable title (not just the leftmost match)."""
        best: Optional[str] = None
        pos = 0
        while pos < len(s):
            m = pat.search(s, pos)
            if not m:
                break
            prefix = _clean_prefix(m.group(1))
            if _usable_prefix(prefix):
                pl = prefix.lower()
                if suffix_words == "Marathon" and pl.endswith(" half"):
                    pos = m.start() + 1
                    continue
                name = f"{prefix} {suffix_words}"
                name = re.sub(r"\s+", " ", name).strip()
                if 8 <= len(name) <= 255 and (best is None or len(name) > len(best)):
                    best = name[:255]
            pos = m.start() + 1
        return best

    # Longer suffix first so "… Half Marathon" wins when we also see the word "marathon".
    half_pat = re.compile(
        r"(?is)(?:\bthe\s+)?\b([A-Za-z0-9][\w\s\-',.&]{1,120}?)\s+half\s+marathon\b"
    )
    half_best = _best_name_from_pattern(half_pat, "Half Marathon")
    if half_best:
        return half_best

    marathon_pat = re.compile(
        r"(?is)(?:\bthe\s+)?\b([A-Za-z0-9][\w\s\-',.&]{1,120}?)\s+(?<!half\s)marathon\b"
    )
    return _best_name_from_pattern(marathon_pat, "Marathon")


def _fill_race_name_from_user_text(draft: Dict[str, Any], text: Optional[str]) -> None:
    """When race_name is still empty, derive it from the latest user message if it clearly names an event."""
    existing = draft.get("race_name")
    if isinstance(existing, str) and existing.strip():
        return
    extracted = _extract_race_name_from_user_text(text or "")
    if extracted:
        draft["race_name"] = extracted[:255]


def _expand_day_range(start_raw: str, end_raw: str) -> Optional[List[str]]:
    start = _normalize_day(start_raw.strip())
    end = _normalize_day(end_raw.strip())
    if start is None or end is None:
        return None
    si = DAY_NAMES_ABBREV.index(start)
    ei = DAY_NAMES_ABBREV.index(end)
    if si <= ei:
        return list(DAY_NAMES_ABBREV[si : ei + 1])
    return list(DAY_NAMES_ABBREV[si:]) + list(DAY_NAMES_ABBREV[: ei + 1])


def _training_day_phrase_sets() -> Dict[str, List[str]]:
    wk = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    we = ["Sat", "Sun"]
    all7 = list(DAY_NAMES_ABBREV)
    return {
        "weekdays": wk,
        "weekday": wk,
        "business days": wk,
        "business days of the week": wk,
        "weekends": we,
        "weekend": we,
        "every day": all7,
        "everyday": all7,
        "daily": all7,
        "all week": all7,
        "all seven days": all7,
        "seven days a week": all7,
    }


def _split_training_day_segments(s: str) -> List[str]:
    """Split user/comma text into pieces (comma, semicolon, 'and', 'plus')."""
    t = (s or "").strip()
    if not t:
        return []
    t = re.sub(r"\s+and\s+", ",", t, flags=re.I)
    t = re.sub(r"\s+plus\s+", ",", t, flags=re.I)
    t = t.replace(";", ",").replace("/", ",")
    return [p.strip() for p in t.split(",") if p.strip()]


def _merge_training_day_chunks(chunks: List[List[str]]) -> List[str]:
    """Preserve first-seen order (ranges stay chronological, incl. Fri→Mon wraps)."""
    seen: set[str] = set()
    out: List[str] = []
    for chunk in chunks:
        for d in chunk:
            if d not in seen:
                seen.add(d)
                out.append(d)
    return out


def _expand_training_days_segment(segment: str) -> Optional[List[str]]:
    """
    One phrase → weekday abbrevs, or None if not parseable.

    Supports ranges (Monday through Saturday), phrase presets (weekdays), and single days.
    """
    p = segment.strip()
    if not p:
        return []
    pl = re.sub(r"\s+", " ", p.lower())
    presets = _training_day_phrase_sets()
    if pl in presets:
        return list(presets[pl])
    # Compact hyphen/en-dash range without spaces: "Mon-Sat", "Mon–Sat"
    m_compact = re.match(r"(?is)^(\w{2,12})\s*[-–—]\s*(\w{2,12})$", p)
    if (
        m_compact
        and _normalize_day(m_compact.group(1))
        and _normalize_day(m_compact.group(2))
    ):
        return _expand_day_range(m_compact.group(1), m_compact.group(2))
    m = re.match(
        r"(?is)^(.+?)\s+(?:through|thru|to|-|–|—)\s+(.+)$",
        p,
    )
    if m:
        return _expand_day_range(m.group(1), m.group(2))
    nd = _normalize_day(p)
    if nd:
        return [nd]
    return None


def _normalize_training_days(value: Any) -> Optional[List[str]]:
    segments: List[str] = []
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, str):
                return None
            segments.extend(_split_training_day_segments(item))
    elif isinstance(value, str):
        segments = _split_training_day_segments(value)
    else:
        return None

    chunks: List[List[str]] = []
    for seg in segments:
        chunk = _expand_training_days_segment(seg)
        if chunk is None:
            return None
        chunks.append(chunk)

    merged = _merge_training_day_chunks(chunks)
    return merged or None


def _training_day_message_candidates(text: str) -> List[str]:
    """
    Build short strings to try with _normalize_training_days when the user
    mixes prose with a day range (e.g. "Thanks, Mon-Thu").
    """
    msg = (text or "").strip()
    if not msg:
        return []
    out: List[str] = []
    seen: set[str] = set()

    def _add(s: str) -> None:
        t = s.strip()
        if not t:
            return
        k = t.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)

    _add(msg)
    for part in re.split(r"[,;]", msg):
        _add(part)
    # Hyphen / en-dash weekday span within a longer line
    for m in re.finditer(
        r"(?is)\b([a-z]{3,12})\s*[-–—]\s*([a-z]{3,12})\b",
        msg,
    ):
        _add(f"{m.group(1)}-{m.group(2)}")
    # "Monday through Thursday" style
    for m in re.finditer(
        r"(?is)\b([a-z]+)\s+(?:through|thru|to)\s+([a-z]+)\b",
        msg,
    ):
        _add(f"{m.group(1)} through {m.group(2)}")
    return out


def _fill_training_days_from_user_message(
    draft: Dict[str, Any],
    ux: Dict[str, Any],
    text: Optional[str],
) -> None:
    """When ``training_days`` is still empty, parse weekday phrases from the user line."""
    td = draft.get("training_days")
    if isinstance(td, list) and len(td) > 0:
        return
    for cand in _training_day_message_candidates((text or "").strip()):
        ndays = _normalize_training_days(cand)
        if ndays:
            draft["training_days"] = ndays
            ux.pop("training_days_count", None)
            return


_TRAINING_DAY_COUNT_WORDS: Dict[str, int] = {
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
}


def _extract_training_days_count(value: Any) -> Optional[int]:
    """
    Recognize frequency-only schedule input (e.g. "5 days per week").

    This is intentionally *not* converted into weekdays. The deterministic
    generator still requires explicit days, so we store the count as UX context
    and keep `training_days` missing.
    """
    pieces: List[str] = []
    if isinstance(value, str):
        pieces = [value]
    elif isinstance(value, list):
        pieces = [p for p in value if isinstance(p, str)]
    else:
        return None

    text = " ".join(pieces).strip().lower()
    if not text:
        return None
    word_alt = "|".join(_TRAINING_DAY_COUNT_WORDS)
    m = re.search(
        rf"\b([3-7]|{word_alt})\s*(?:x|times?|days?)\s*(?:/|per|a)?\s*(?:week|wk)?\b",
        text,
        flags=re.I,
    )
    if not m:
        return None
    raw = m.group(1).lower()
    try:
        n = int(raw)
    except ValueError:
        n = _TRAINING_DAY_COUNT_WORDS.get(raw)
    return n if n in range(3, 8) else None


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


# Month name or abbreviation + day (optional ordinal / year). Used when the
# model omits ``race_date`` in ``updates`` but the user answered with a date phrase.
_RACE_DATE_PHRASE_RE = re.compile(
    r"(?is)\b("
    r"(?:january|february|march|april|may|june|july|august|september|october|november|december|"
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\.?)"
    r"\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?"
    r"(?:\s*,?\s*(\d{4}))?"
    r"\b"
)


def _extract_race_date_phrases_from_message(text: str) -> List[str]:
    """
    Build parse candidates: full message only when it plausibly names a calendar day
    (avoids dateutil on unrelated lines like “Time… 3:40”), then month+day substrings.
    """
    out: List[str] = []
    t = (text or "").strip()
    if not t:
        return out
    has_month_day = _RACE_DATE_PHRASE_RE.search(t) is not None
    has_numeric_date = re.search(
        r"(?is)\b\d{4}\s*[-/]\s*\d{1,2}\s*[-/]\s*\d{1,2}\b"
        r"|\b\d{1,2}\s*[-/]\s*\d{1,2}\s*[-/]\s*\d{2,4}\b",
        t,
    )
    if len(t) <= 72 and (has_month_day or has_numeric_date):
        out.append(t)
    found: List[tuple[int, int, str]] = []
    for m in _RACE_DATE_PHRASE_RE.finditer(t):
        month = m.group(1)
        day = m.group(2)
        year = m.group(3)
        chunk = f"{month.strip()} {day}".strip()
        if year:
            chunk = f"{chunk}, {year}"
        found.append((m.start(), len(m.group(0)), chunk))
    found.sort(key=lambda x: (-x[1], x[0]))
    for _, _, chunk in found:
        if chunk not in out:
            out.append(chunk)
    return out


def _fill_race_date_from_user_message(
    draft: Dict[str, Any], text: Optional[str]
) -> None:
    """When ``race_date`` is still empty, parse spoken dates from the latest user line."""
    rd = draft.get("race_date")
    if isinstance(rd, str) and rd.strip():
        return
    for candidate in _extract_race_date_phrases_from_message((text or "").strip()):
        nd = _parse_race_date_natural_language(candidate)
        if nd:
            draft["race_date"] = nd
            return


def _fill_primary_goal_from_user_message(
    draft: Dict[str, Any], text: Optional[str]
) -> None:
    """When ``primary_goal`` is empty, map short natural answers (e.g. just finish / time goal)."""
    pg = draft.get("primary_goal")
    if isinstance(pg, str) and pg.strip():
        return
    msg = (text or "").strip()
    if not msg:
        return
    ng = _normalize_goal(msg)
    if ng:
        draft["primary_goal"] = ng


def _infer_target_time_from_message(text: str) -> Optional[str]:
    """
    Pick a marathon-style clock time from free text (e.g. "3:40", "about 3:40:00").

    Ignores times with hour > 12 (reduces false positives vs odd numeric blobs).
    """
    if not isinstance(text, str):
        return None
    ts = text.strip()
    if not ts:
        return None
    if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", ts):
        return _normalize_target_time_phrase(ts)
    best: Optional[str] = None
    for m in re.finditer(r"\b(\d{1,2}:\d{2}(:\d{2})?)\b", ts):
        token = m.group(1)
        parts = token.split(":")
        try:
            h = int(parts[0])
            mi = int(parts[1])
        except (ValueError, IndexError):
            continue
        if not (0 <= h <= 12 and 0 <= mi <= 59):
            continue
        if h == 0 and mi == 0:
            continue
        cand = _normalize_target_time_phrase(token)
        if cand:
            best = cand
    return best


def _fill_goal_time_from_user_message(
    draft: Dict[str, Any], text: Optional[str]
) -> None:
    """When goal/time missing, infer Target Time + target_time from a clock phrase."""
    msg = (text or "").strip()
    if not msg:
        return
    norm_time = _infer_target_time_from_message(msg)
    if not norm_time:
        return
    pg = draft.get("primary_goal")
    tt = draft.get("target_time")
    has_pg = isinstance(pg, str) and pg.strip()
    has_tt = isinstance(tt, str) and tt.strip()
    if not has_pg:
        draft["primary_goal"] = PrimaryGoal.TARGET_TIME.value
        draft["target_time"] = norm_time
        return
    if pg == PrimaryGoal.TARGET_TIME.value and not has_tt:
        draft["target_time"] = norm_time
        return
    if pg == PrimaryGoal.JUST_FINISH.value:
        draft["primary_goal"] = PrimaryGoal.TARGET_TIME.value
        draft["target_time"] = norm_time


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


def plan_intake_premature_confirmation_reply(state: Dict[str, Any]) -> str:
    """
    User said yes to a summary, but deterministic intake is still incomplete.

    The model sometimes asks for final confirmation while ``ready_to_generate`` is
    still false (for example after a frequency count without concrete weekdays).
    Without this, ``generate_training_plan`` rejects the draft and the model may
    apologize and re-ask in a confusing loop.
    """
    missing = [m for m in (state.get("missing_required") or []) if isinstance(m, str)]
    ux_raw = state.get("ux")
    ux = ux_raw if isinstance(ux_raw, dict) else {}

    sentences: List[str] = []

    if "training_days" in missing:
        n = ux.get("training_days_count")
        if isinstance(n, int) and 3 <= n <= 7:
            sentences.append(
                f"I still need the **specific weekdays** you will run — you want **{n}** "
                "days per week, but I cannot infer the calendar pattern from the count alone. "
                "Which days should those be (for example: Monday through Saturday, or Tue / Thu / Sat)?"
            )
        else:
            sentences.append(
                "I still need **which days of the week** you plan to train "
                "(for example: Tue, Thu, Sat)."
            )

    other = [m for m in missing if m != "training_days"]
    if other:
        labels = ", ".join(_human_missing_label(m) for m in other)
        sentences.append(f"I also still need: **{labels}**.")

    if not sentences:
        sentences.append(
            "A few required plan details are still missing before I can generate — "
            "answer the last open item when you are ready."
        )

    return " ".join(sentences).strip()


def user_confirms_plan_intake(user_message: str) -> bool:
    """
    True when the user is clearly confirming a ready-to-generate plan summary.

    Short messages only; negation / correction cues disable the fast path.

    Must be a **whole-message** affirmation (trailing punctuation OK). Compound
    replies like "Yes. Saturdays" are **not** confirmations — they answer the
    prior coach question and must not trip yes→generate or premature-confirm paths.
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
    affirm_full = re.compile(
        r"(?is)^(?:"
        r"y|ye|yes|yep|yup|ok|okay|k|sure|"
        r"correct|right|confirm|confirmed|absolutely|definitely|"
        r"looks good|look good|sounds good|sound good|go ahead|please do|"
        r"that'?s right|that is right|all good|perfect"
        r")(?:\s*[.!?…,;:])*$"
    )
    if affirm_full.match(core):
        return True
    return False


def _coerce_state(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    out = dict(raw)
    if not isinstance(out.get("draft"), dict):
        out["draft"] = {}
    if not isinstance(out.get("ux"), dict):
        out["ux"] = {}
    return out


def _plan_ux_stage_for_state(
    draft: Dict[str, Any],
    missing: List[str],
    *,
    ready_to_generate: bool,
    had_prior_draft: bool,
    prior_ready_to_generate: bool,
) -> str:
    if ready_to_generate:
        if not had_prior_draft and not prior_ready_to_generate:
            return PLAN_UX_STAGE_FAST_TRACK
        return PLAN_UX_STAGE_CONFIRM
    if not draft:
        return PLAN_UX_STAGE_UNDERSTAND_RUNNER
    if "race_distance" in missing or "race_date" in missing:
        return PLAN_UX_STAGE_GOAL_ALIGNMENT
    return PLAN_UX_STAGE_DETAILS


def plan_runner_understanding_shown(state: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(state, dict):
        return False
    ux = state.get("ux")
    return isinstance(ux, dict) and bool(ux.get("runner_understanding_shown"))


def mark_plan_runner_understanding_shown(
    state: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(state, dict):
        return state
    out = dict(state)
    ux = dict(out.get("ux") or {})
    ux["runner_understanding_shown"] = True
    if not ux.get("stage") or ux.get("stage") == PLAN_UX_STAGE_UNDERSTAND_RUNNER:
        ux["stage"] = PLAN_UX_STAGE_GOAL_ALIGNMENT
    out["ux"] = ux
    return out


def _missing_required_fields(draft: Dict[str, Any]) -> List[str]:
    """
    Missing fields in intake order. When primary_goal is Target Time, ``target_time``
    is required immediately after goal type — before ``training_days`` — so structured
    UI and conversation ask for clock time next, not weekly schedule first.
    """
    out: List[str] = []
    for f in REQUIRED_FIELDS:
        v = draft.get(f)
        missing_f = False
        if v is None:
            missing_f = True
        elif isinstance(v, str) and not v.strip():
            missing_f = True
        elif isinstance(v, list) and not v:
            missing_f = True
        if missing_f:
            out.append(f)
        if f == "primary_goal" and not missing_f:
            pg = draft.get("primary_goal")
            if (
                isinstance(pg, str)
                and pg.strip() == PrimaryGoal.TARGET_TIME.value
                and not (
                    isinstance(draft.get("target_time"), str)
                    and draft.get("target_time", "").strip()
                )
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


def _normalize_alignment_bool(raw: Any) -> Optional[bool]:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("yes", "y", "true", "1"):
            return True
        if s in ("no", "n", "false", "0"):
            return False
    return None


def _normalize_alignment_posture(raw: Any) -> Optional[str]:
    if not isinstance(raw, str):
        return None
    s = raw.strip().lower()
    aliases = {
        "performance": "PERFORMANCE_LEANING",
        "performance_leaning": "PERFORMANCE_LEANING",
        "balanced": "BALANCED",
        "durability": "DURABILITY_FIRST",
        "durability_first": "DURABILITY_FIRST",
    }
    return aliases.get(s)


def _extract_alignment_answers_from_user_message(
    source_user_message: Optional[str],
) -> Dict[str, Any]:
    msg = (source_user_message or "").strip().lower()
    if not msg:
        return {}

    out: Dict[str, Any] = {}

    # Frequency flexibility (can add/adjust running days)
    if re.search(
        r"\b(add|another|extra|more)\s+(day|run)\b|\bcan\s+add\b|\bflexible\s+on\s+days\b",
        msg,
    ):
        out["frequency_flexible"] = True
    elif re.search(
        r"\b(can(?:not|'t)\s+add|no\s+extra\s+day|keep\s+the\s+same\s+days|fixed\s+schedule)\b",
        msg,
    ):
        out["frequency_flexible"] = False

    # Posture priority (performance vs durability vs balanced)
    if re.search(
        r"\b(balance|balanced|middle\s+ground|both)\b",
        msg,
    ):
        out["posture_priority"] = "BALANCED"
    elif re.search(
        r"\b(performance|faster|aggressive|push|chase\s+time|time\s+goal)\b",
        msg,
    ):
        out["posture_priority"] = "PERFORMANCE_LEANING"
    elif re.search(
        r"\b(durability|healthy|stay\s+healthy|injury|sustainable|consistency\s+first|safe)\b",
        msg,
    ):
        out["posture_priority"] = "DURABILITY_FIRST"

    # Timeline flexibility (race-date/time flexibility if needed)
    if re.search(
        r"\b(flexible\s+on\s+(date|timeline)|can\s+(move|shift|push)\s+(it|the\s+date)|date\s+is\s+flexible)\b",
        msg,
    ):
        out["timeline_flexible"] = True
    elif re.search(
        r"\b(date\s+is\s+fixed|timeline\s+is\s+fixed|cannot\s+move\s+(it|date)|can't\s+move\s+(it|date)|not\s+flexible)\b",
        msg,
    ):
        out["timeline_flexible"] = False

    return out


def update_plan_intake_state(
    current_state: Optional[Dict[str, Any]],
    *,
    updates: Optional[Dict[str, Any]] = None,
    clear_fields: Optional[List[str]] = None,
    reset: bool = False,
    source_user_message: Optional[str] = None,
) -> Dict[str, Any]:
    state = _coerce_state(None if reset else current_state)
    draft: Dict[str, Any] = dict(state.get("draft") or {})
    ux: Dict[str, Any] = dict(state.get("ux") or {})
    had_prior_draft = bool(draft)
    prior_ready_to_generate = bool(state.get("ready_to_generate"))
    errors: List[str] = []
    alignment = dict(state.get("alignment") or {})
    alignment_answers = dict(alignment.get("answers") or {})
    prior_alignment_answers = dict(alignment_answers)
    prior_training_days_for_expansion = (
        list(draft["training_days"])
        if isinstance(draft.get("training_days"), list)
        else None
    )
    prior_expansion_pending = bool(ux.get("training_days_expansion_pending"))

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
                draft["race_distance"] = _normalize_race_distance_intake(raw)
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
                day_count = _extract_training_days_count(raw)
                if day_count is not None:
                    ux["training_days_count"] = day_count
                    draft.pop("training_days", None)
                else:
                    errors.append(
                        "training_days must be weekdays or ranges (e.g. Monday through Saturday, "
                        "weekdays), abbreviations, or comma-separated lists."
                    )
            else:
                draft["training_days"] = ndays
                ux.pop("training_days_count", None)
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
        elif key == "alignment_frequency_flexible":
            v = _normalize_alignment_bool(raw)
            if v is None:
                errors.append("alignment_frequency_flexible must be boolean-like.")
            else:
                alignment_answers["frequency_flexible"] = v
        elif key == "alignment_posture_priority":
            v = _normalize_alignment_posture(raw)
            if v is None:
                errors.append(
                    "alignment_posture_priority must be one of performance, balanced, durability."
                )
            else:
                alignment_answers["posture_priority"] = v
        elif key == "alignment_timeline_flexible":
            v = _normalize_alignment_bool(raw)
            if v is None:
                errors.append("alignment_timeline_flexible must be boolean-like.")
            else:
                alignment_answers["timeline_flexible"] = v
        elif key == "alignment_question_asked_category":
            if isinstance(raw, str) and raw.strip():
                category = raw.strip()
                asked = [
                    str(x)
                    for x in list(alignment.get("asked_categories") or [])
                    if isinstance(x, str)
                ]
                asked.append(category)
                alignment["asked_categories"] = asked
                alignment["question_count"] = len(asked)
            else:
                errors.append(
                    "alignment_question_asked_category must be a non-empty string."
                )
        elif key == "schedule_days_confirmed":
            v = _normalize_alignment_bool(raw)
            if v is None:
                errors.append("schedule_days_confirmed must be boolean-like.")
            elif v is True:
                ux.pop("schedule_confirm_before_posture", None)
            else:
                ux.pop("schedule_confirm_before_posture", None)
                ux["training_days_expansion_pending"] = True
                draft.pop("training_days", None)
                ux.pop("training_days_count", None)

    _fill_race_distance_from_named_event(draft)
    _fill_race_name_from_user_text(draft, source_user_message)

    # When the model omits `race_distance` but the user answered in plain language
    # (e.g. "A marathon", "the full marathon"), infer from the latest message.
    # Named-event fill above only sees race_name/location/plan_name; bare phrases
    # like "a marathon" do not populate race_name (event-title regex needs a longer prefix).
    skip_nl_core = structured_intake_core_v1_enabled()
    if not skip_nl_core:
        rd_cur = draft.get("race_distance")
        if not (isinstance(rd_cur, str) and rd_cur.strip()):
            msg_rd = _try_infer_race_distance((source_user_message or "").strip())
            if msg_rd:
                draft["race_distance"] = msg_rd

        _fill_race_date_from_user_message(draft, source_user_message)

        _fill_primary_goal_from_user_message(draft, source_user_message)

        _fill_goal_time_from_user_message(draft, source_user_message)

        _fill_training_days_from_user_message(draft, ux, source_user_message)
    msg_alignment_answers = _extract_alignment_answers_from_user_message(
        source_user_message
    )
    if msg_alignment_answers:
        # Explicit `updates` values win; source-message extraction fills gaps.
        for key, value in msg_alignment_answers.items():
            if key not in alignment_answers:
                alignment_answers[key] = value

    if (
        alignment_answers.get("frequency_flexible") is True
        and prior_alignment_answers.get("frequency_flexible") is not True
    ):
        # User agreed to add/adjust capacity — must re-pick concrete weekdays next.
        ux["training_days_expansion_pending"] = True

    if (
        not skip_nl_core
        and "training_days" not in draft
        and "training_days_count" not in ux
    ):
        day_count = _extract_training_days_count(source_user_message)
        if day_count is not None:
            ux["training_days_count"] = day_count

    if "training_days" in draft and draft.get("long_run_day"):
        tdays = draft.get("training_days") or []
        if draft["long_run_day"] not in tdays:
            errors.append("long_run_day must be one of training_days.")

    _auto_fill_long_run_day(draft)

    # Cleared after user commits a new weekday set (structured `updates` or draft change).
    if ux.get("training_days_expansion_pending"):
        explicit_td = isinstance(up, dict) and "training_days" in up
        cur_td = draft.get("training_days")
        td_changed = False
        if isinstance(cur_td, list):
            if isinstance(prior_training_days_for_expansion, list):
                td_changed = cur_td != prior_training_days_for_expansion
            else:
                td_changed = True
        if explicit_td or td_changed:
            ux.pop("training_days_expansion_pending", None)

    expansion_cleared_this_turn = prior_expansion_pending and not ux.get(
        "training_days_expansion_pending"
    )
    if expansion_cleared_this_turn:
        ux["schedule_confirm_before_posture"] = True

    missing = _missing_required_fields(draft)
    if ux.get("training_days_expansion_pending"):
        if "training_days" not in missing:
            missing = ["training_days"] + [m for m in missing if m != "training_days"]
    ready_to_generate = len(missing) == 0 and len(errors) == 0
    status = "ready_to_confirm" if not missing else "collecting"
    ux["stage"] = _plan_ux_stage_for_state(
        draft,
        missing,
        ready_to_generate=ready_to_generate,
        had_prior_draft=had_prior_draft,
        prior_ready_to_generate=prior_ready_to_generate,
    )
    state = {
        "version": 1,
        "status": status,
        "draft": draft,
        "ux": ux,
        "missing_required": missing,
        "missing_required_labels": [_human_missing_label(m) for m in missing],
        "ready_to_generate": ready_to_generate,
        "errors": errors,
        "confirmation_summary": _confirmation_summary(draft),
    }
    merged_al: Optional[Dict[str, Any]] = None
    if alignment_answers:
        merged_al = {**alignment, "answers": alignment_answers}
    elif alignment:
        merged_al = dict(alignment)
    if merged_al is not None:
        state["alignment"] = _recompute_alignment_branch(merged_al, draft)
    if _intake_alignment_feature_enabled():
        al_out = state.get("alignment")
        if isinstance(al_out, dict):
            ast = al_out.get("state")
            if (
                isinstance(ast, dict)
                and ast.get("pause_required")
                and not ast.get("generation_ready")
            ):
                state["ready_to_generate"] = False
                state["status"] = "collecting"
                state["ux"]["stage"] = _plan_ux_stage_for_state(
                    draft,
                    state["missing_required"],
                    ready_to_generate=False,
                    had_prior_draft=had_prior_draft,
                    prior_ready_to_generate=prior_ready_to_generate,
                )
    return state


def build_core_structured_ui_prompt(
    intake_state: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Inline controls for core athletic intake when SMARTCOACH_STRUCTURED_INTAKE_CORE_V1 is on.

    Alignment pause prompts take precedence in the orchestrator; this fills remaining slots
    from ``missing_required[0]``.
    """
    if not structured_intake_core_v1_enabled():
        return None
    if not isinstance(intake_state, dict):
        return None
    if intake_state.get("ready_to_generate"):
        return None
    missing_raw = intake_state.get("missing_required") or []
    missing = [m for m in missing_raw if isinstance(m, str)]
    if not missing:
        return None
    first = missing[0]

    if first == "race_distance":
        return {
            "version": 1,
            "field_key": "plan_intake.race_distance",
            "control_type": "single_select_chips",
            "selection_mode": "single",
            "required": True,
            "prompt": "What distance are you training for?",
            "options": [
                {
                    "id": "dist_half",
                    "label": "Half marathon",
                    "user_message": "I'm training for a half marathon.",
                    "updates": {"race_distance": "Half Marathon"},
                },
                {
                    "id": "dist_full",
                    "label": "Marathon",
                    "user_message": "I'm training for a marathon.",
                    "updates": {"race_distance": "Marathon"},
                },
            ],
        }

    if first == "race_date":
        return {
            "version": 1,
            "field_key": "plan_intake.race_date",
            "control_type": "date_picker",
            "selection_mode": "single",
            "required": True,
            "prompt": "When is your race? Tap below to open your calendar.",
            "options": [],
        }

    if first == "primary_goal":
        return {
            "version": 1,
            "field_key": "plan_intake.primary_goal",
            "control_type": "single_select_chips",
            "selection_mode": "single",
            "required": True,
            "prompt": "Is the goal to finish strong, or are you targeting a specific time?",
            "options": [
                {
                    "id": "goal_finish",
                    "label": "Finish strong",
                    "user_message": "I want to finish strong — no specific time goal.",
                    "updates": {"primary_goal": PrimaryGoal.JUST_FINISH.value},
                },
                {
                    "id": "goal_time",
                    "label": "Target time",
                    "user_message": "I'm targeting a specific finish time.",
                    "updates": {"primary_goal": PrimaryGoal.TARGET_TIME.value},
                },
            ],
        }

    if first == "target_time":
        presets: List[tuple[str, str, str]] = [
            ("tt_300", "3:00", "3:00:00"),
            ("tt_315", "3:15", "3:15:00"),
            ("tt_330", "3:30", "3:30:00"),
            ("tt_345", "3:45", "3:45:00"),
            ("tt_400", "4:00", "4:00:00"),
            ("tt_430", "4:30", "4:30:00"),
            ("tt_500", "5:00", "5:00:00"),
        ]
        return {
            "version": 1,
            "field_key": "plan_intake.target_time",
            "control_type": "single_select_chips",
            "selection_mode": "single",
            "required": True,
            "prompt": "What finish time are you aiming for?",
            "options": [
                {
                    "id": pid,
                    "label": label,
                    "user_message": f"I'm aiming for about {label} (finish ~{clock}).",
                    "updates": {"target_time": clock},
                }
                for pid, label, clock in presets
            ],
        }

    if first == "training_days":
        ux_in = (
            intake_state.get("ux") if isinstance(intake_state.get("ux"), dict) else {}
        )
        expansion = bool(ux_in.get("training_days_expansion_pending"))
        prompt = (
            "Update your weekly running days — add your extra day or adjust the mix, "
            "then confirm."
            if expansion
            else "Which days work for training? Select all that apply, then confirm."
        )
        return {
            "version": 1,
            "field_key": "plan_intake.training_days",
            "control_type": "multi_select_chips",
            "selection_mode": "multi",
            "required": True,
            "prompt": prompt,
            "multi_select_submit": {
                "label": "Confirm days",
                "updates_key": "training_days",
            },
            "options": [
                {
                    "id": d,
                    "label": d,
                    "user_message": "",
                    "updates": {},
                }
                for d in DAY_NAMES_ABBREV
            ],
        }

    return None


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

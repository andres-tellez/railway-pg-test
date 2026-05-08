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

    _fill_race_distance_from_named_event(draft)
    _fill_race_name_from_user_text(draft, source_user_message)

    # When the model omits `race_distance` but the user answered in plain language
    # (e.g. "A marathon", "the full marathon"), infer from the latest message.
    # Named-event fill above only sees race_name/location/plan_name; bare phrases
    # like "a marathon" do not populate race_name (event-title regex needs a longer prefix).
    rd_cur = draft.get("race_distance")
    if not (isinstance(rd_cur, str) and rd_cur.strip()):
        msg_rd = _try_infer_race_distance((source_user_message or "").strip())
        if msg_rd:
            draft["race_distance"] = msg_rd

    _fill_race_date_from_user_message(draft, source_user_message)

    _fill_primary_goal_from_user_message(draft, source_user_message)

    _fill_goal_time_from_user_message(draft, source_user_message)

    _fill_training_days_from_user_message(draft, ux, source_user_message)

    if "training_days" not in draft and "training_days_count" not in ux:
        day_count = _extract_training_days_count(source_user_message)
        if day_count is not None:
            ux["training_days_count"] = day_count

    if "training_days" in draft and draft.get("long_run_day"):
        tdays = draft.get("training_days") or []
        if draft["long_run_day"] not in tdays:
            errors.append("long_run_day must be one of training_days.")

    _auto_fill_long_run_day(draft)

    missing = _missing_required_fields(draft)
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
    if alignment_answers:
        state["alignment"] = {
            **alignment,
            "answers": alignment_answers,
        }
    elif alignment:
        state["alignment"] = alignment
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

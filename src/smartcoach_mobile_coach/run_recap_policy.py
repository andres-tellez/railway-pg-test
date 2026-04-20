"""
Anchor-day run recap fastpath — eligibility only (single responsibility).

Orchestrator and ``run_recap_fastpath.wants_run_recap_fastpath`` use this so
phrase matching, safety blocks, and “first user turn” rules live in one place
with explicit ``reason_code`` values for logs and metadata.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional


def _fastpath_enabled() -> bool:
    return os.getenv("SMARTCOACH_RUN_RECAP_FASTPATH", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def prior_user_turn_count(conversation_history: List[Dict[str, str]]) -> int:
    """Count prior **user** rows with non-empty content (current message is not in history)."""
    return sum(
        1
        for m in conversation_history
        if (m.get("role") or "").strip() == "user" and (m.get("content") or "").strip()
    )


# Substrings: if any appear, do not use anchor-day recap fastpath (except
# "yesterday", which is handled via device anchor minus one calendar day when
# a recap phrase matches).
_ANCHOR_RECAP_BLOCKED = (
    "last run",
    "that run",
    "last race",
    "this run",
    "last week",
    "last sunday",
    "last monday",
    "on sunday",
    "on monday",
)

# Positive phrases (substring match on normalized lower text).
_ANCHOR_RECAP_PHRASES = (
    "how was my run",
    "how did my run go",
    "how did today go",
    "how was today",
    "how did today",
    "analyze my run",
    # Common contractions / variants that previously missed the fastpath
    "how's my run",
    "hows my run",
    "how is my run",
    "how did my run",
    "how went my run",
)


def _recap_phrase_hit(user_message: str) -> bool:
    t = (user_message or "").lower().strip()
    if not t or "drift" in t:
        return False
    return any(p in t for p in _ANCHOR_RECAP_PHRASES)


def _blocked_calendar_ambiguity(user_message: str) -> bool:
    t = (user_message or "").lower()
    return any(b in t for b in _ANCHOR_RECAP_BLOCKED)


def _wants_yesterday_run(user_message: str) -> bool:
    return "yesterday" in (user_message or "").lower()


def _previous_local_calendar_date(anchor_local_date: str) -> Optional[str]:
    """Return YYYY-MM-DD for the calendar day before ``anchor_local_date``."""
    ld = (anchor_local_date or "").strip()[:10]
    if len(ld) != 10:
        return None
    try:
        d = datetime.strptime(ld, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (d - timedelta(days=1)).isoformat()


@dataclass(frozen=True)
class RunRecapFastpathDecision:
    """Outcome of anchor-day run recap fastpath gating."""

    eligible: bool
    reason_code: str
    prior_user_turn_count: int
    prefetch_local_date: Optional[str] = None


def decide_run_recap_fastpath(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    anchor_local_date: str = "",
) -> RunRecapFastpathDecision:
    """
    Whether to attempt prefetch + single completion (no tools).

    Eligibility requires:
    - fastpath env on
    - message matches anchor recap phrases (and passes safety blocks)
    - **no prior user turns** in thread (assistant-only preamble like a welcome
      is OK — this is the athlete's first question in the Coach thread)

    When the user says **yesterday** alongside a recap phrase, prefetch uses
    ``anchor_local_date`` minus one calendar day (device-local). If
    ``anchor_local_date`` is missing or invalid, that variant is not eligible.
    """
    turns = prior_user_turn_count(conversation_history)
    if not _fastpath_enabled():
        return RunRecapFastpathDecision(False, "fastpath_disabled", turns)
    if turns > 0:
        return RunRecapFastpathDecision(False, "not_first_user_turn", turns)
    if not _recap_phrase_hit(user_message):
        return RunRecapFastpathDecision(False, "phrase_or_block_mismatch", turns)
    if _blocked_calendar_ambiguity(user_message):
        return RunRecapFastpathDecision(False, "phrase_or_block_mismatch", turns)
    if _wants_yesterday_run(user_message):
        prev_day = _previous_local_calendar_date(anchor_local_date)
        if not prev_day:
            return RunRecapFastpathDecision(
                False, "invalid_anchor_for_yesterday", turns
            )
        return RunRecapFastpathDecision(
            True, "eligible_yesterday", turns, prefetch_local_date=prev_day
        )
    return RunRecapFastpathDecision(True, "eligible", turns)

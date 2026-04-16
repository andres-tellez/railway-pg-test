"""
Anchor-day run recap fastpath — eligibility only (single responsibility).

Orchestrator and ``run_recap_fastpath.wants_run_recap_fastpath`` use this so
phrase matching, safety blocks, and “first user turn” rules live in one place
with explicit ``reason_code`` values for logs and metadata.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List


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


# Substrings: if any appear, do not use anchor-day recap fastpath.
_ANCHOR_RECAP_BLOCKED = (
    "last run",
    "that run",
    "last race",
    "this run",
    "yesterday",
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


def _message_matches_anchor_recap(user_message: str) -> bool:
    t = (user_message or "").lower().strip()
    if not t:
        return False
    if any(b in t for b in _ANCHOR_RECAP_BLOCKED):
        return False
    if "drift" in t:
        return False
    return any(p in t for p in _ANCHOR_RECAP_PHRASES)


@dataclass(frozen=True)
class RunRecapFastpathDecision:
    """Outcome of anchor-day run recap fastpath gating."""

    eligible: bool
    reason_code: str
    prior_user_turn_count: int


def decide_run_recap_fastpath(
    user_message: str, conversation_history: List[Dict[str, str]]
) -> RunRecapFastpathDecision:
    """
    Whether to attempt prefetch + single completion (no tools).

    Eligibility requires:
    - fastpath env on
    - message matches anchor recap phrases (and passes safety blocks)
    - **no prior user turns** in thread (assistant-only preamble like a welcome
      is OK — this is the athlete's first question in the Coach thread)
    """
    turns = prior_user_turn_count(conversation_history)
    if not _fastpath_enabled():
        return RunRecapFastpathDecision(False, "fastpath_disabled", turns)
    if turns > 0:
        return RunRecapFastpathDecision(False, "not_first_user_turn", turns)
    if not _message_matches_anchor_recap(user_message):
        return RunRecapFastpathDecision(False, "phrase_or_block_mismatch", turns)
    return RunRecapFastpathDecision(True, "eligible", turns)

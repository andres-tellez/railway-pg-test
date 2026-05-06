"""
Optional CoachTurnSections-shaped payload for run_summary (Phase 1).

Splits assistant Markdown insight into interpretation / grounding[] / close using
paragraph boundaries (same join order as mobile ``renderCoachTurnToText``).

Env ``SMARTCOACH_RUN_SUMMARY_SECTIONS_ENABLED`` (default **on**): set to ``0`` /
``false`` / ``no`` / ``off`` to omit ``sections`` and leave ``content`` untouched.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

_SPLIT_BLOCKS = re.compile(r"\n\s*\n+")


def run_summary_sections_enabled() -> bool:
    """Default on so Phase 1 can validate shape without extra Railway env."""
    raw = (os.getenv("SMARTCOACH_RUN_SUMMARY_SECTIONS_ENABLED") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def split_insight_markdown_into_sections(text: str) -> Optional[Dict[str, Any]]:
    """
    Heuristic split of coaching prose into CoachTurnSections-compatible fields.

    Rules:
    - Paragraphs are blocks separated by blank line(s).
    - Single block → interpretation only.
    - Multiple blocks: if last block contains ``?``, treat as optional **close**;
      middle blocks are **grounding**; first block is **interpretation**.
    - **nudge** is left unset (Phase 1 heuristic does not isolate it).
    """
    raw = (text or "").strip()
    if not raw:
        return None
    blocks = [b.strip() for b in _SPLIT_BLOCKS.split(raw) if b.strip()]
    if not blocks:
        return None
    if len(blocks) == 1:
        return {
            "interpretation": blocks[0],
            "grounding": [],
            "nudge": None,
            "close": None,
        }
    last = blocks[-1]
    if "?" in last:
        return {
            "interpretation": blocks[0],
            "grounding": blocks[1:-1],
            "nudge": None,
            "close": last,
        }
    return {
        "interpretation": blocks[0],
        "grounding": blocks[1:],
        "nudge": None,
        "close": None,
    }


def render_coach_turn_sections_to_content(sections: Dict[str, Any]) -> str:
    """Mirror mobile ``renderCoachTurnToText``: interpretation → grounding → nudge → close."""
    parts: List[str] = []
    interp = str(sections.get("interpretation") or "").strip()
    if interp:
        parts.append(interp)
    for g in sections.get("grounding") or []:
        if isinstance(g, str) and g.strip():
            parts.append(g.strip())
    nudge = sections.get("nudge")
    if isinstance(nudge, str) and nudge.strip():
        parts.append(nudge.strip())
    close = sections.get("close")
    if isinstance(close, str) and close.strip():
        parts.append(close.strip())
    return "\n\n".join(parts)


def enrich_run_summary_payload_with_sections(
    payload: Dict[str, Any],
) -> Tuple[Dict[str, Any], bool]:
    """
    Attach optional ``sections`` and set ``content`` to the canonical join of sections.

    Returns (possibly new dict, True) when ``sections`` were attached; else (payload, False).

    Old clients: unchanged keys ``type``, ``content``, ``data`` — ``content`` may be
    whitespace-normalized relative to the model output when sections are derived (same words,
    ``\\n\\n`` boundaries preserved between logical paragraphs).
    """
    if not run_summary_sections_enabled():
        return payload, False
    if payload.get("type") != "run_summary":
        return payload, False
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        return payload, False

    sections = split_insight_markdown_into_sections(content)
    if sections is None:
        return payload, False
    interp = str(sections.get("interpretation") or "").strip()
    if not interp:
        return payload, False

    derived = render_coach_turn_sections_to_content(sections)
    out = dict(payload)
    out["sections"] = sections
    out["content"] = derived
    return out, True

"""Session summary read path."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

SESSION_SUMMARY_READER_VERSION = 1
_MAX_SUMMARY_CHARS = 2000
_PROMPT_SECTION_HEADER = "## PRIOR SESSION SUMMARY"

logger = logging.getLogger(__name__)


def read_most_recent_session_summary(
    session: Session,
    user_id: str,
) -> Optional[str]:
    if not user_id:
        return None
    try:
        row = (
            session.execute(
                text(
                    "SELECT summary_text FROM session_summaries "
                    "WHERE user_id = :uid "
                    "ORDER BY created_at DESC "
                    "LIMIT 1"
                ),
                {"uid": user_id},
            )
            .mappings()
            .first()
        )
    except Exception as exc:
        logger.debug(
            "[session_summary_read] skipped (no session_summaries or query error): %s",
            exc,
        )
        try:
            session.rollback()
        except Exception:
            logger.debug(
                "[session_summary_read] rollback after read error failed",
                exc_info=True,
            )
        return None

    if row is None:
        return None
    summary = row.get("summary_text")
    if not isinstance(summary, str):
        return None
    trimmed = summary.strip()
    if not trimmed:
        return None
    if len(trimmed) > _MAX_SUMMARY_CHARS:
        cutoff = _MAX_SUMMARY_CHARS
        space = trimmed.rfind(" ", 0, cutoff)
        if space > cutoff - 120:
            cutoff = space
        trimmed = trimmed[:cutoff].rstrip() + " …"
    return trimmed


def session_summary_section(summary: Optional[str]) -> str:
    if not summary:
        return ""
    trimmed = summary.strip()
    if not trimmed:
        return ""
    return (
        f"{_PROMPT_SECTION_HEADER}\n"
        f"<!-- session_summary_reader_version: {SESSION_SUMMARY_READER_VERSION} -->\n"
        "\n"
        "Context from the user's most recent prior session with you. Treat as "
        "**reference**, not ground truth:\n"
        "\n"
        "- Use this to avoid re-asking questions the user has already answered and to "
        "  continue any open threads (e.g. a commitment they made, a goal they stated).\n"
        "- **Do not invent** details that are not in the summary. If the user asks about "
        "  something implied but not stated, ask them rather than fabricate (§19.1).\n"
        "- Prefer the current turn's tool payloads over this summary whenever they "
        "  disagree — summaries may lag reality.\n"
        "\n"
        f"{trimmed}\n"
    )


def has_prior_assistant_message(
    conversation_history,
) -> bool:
    if not isinstance(conversation_history, list):
        return False
    for msg in conversation_history:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        if role == "assistant" and isinstance(content, str) and content.strip():
            return True
    return False

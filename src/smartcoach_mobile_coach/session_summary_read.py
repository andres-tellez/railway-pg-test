"""
V1.6 Phase C 3C.10–3C.14 — session summary **read path** (Layer C).

**Purpose.** When a user opens a brand-new conversation, the coach
should not be amnesiac. If a prior session left a curated **session
summary** behind (short text describing what was discussed and any
commitments made), we inject that summary into the system prompt so
the coach can continue the relationship instead of starting cold.

**Scope of this module is the read path only.** The **writer**
(Layer B, end-of-session summarizer) lives on the Phase F roadmap —
3C.14 explicitly splits read vs write so the coach gets immediate
benefit from summaries as soon as the writer lands, without any
further orchestrator changes.

**What this module is:**

* a defensive reader (:func:`read_most_recent_session_summary`) that
  returns the latest stored summary for a user, or ``None`` when no
  summary exists (including the expected "table not yet created"
  state while Phase F is outstanding),
* a prompt-section formatter (:func:`session_summary_section`) that
  wraps the summary in a clearly-labeled block so the coach knows
  to treat it as context, not as fact — and so the coach **must
  not** invent details that are not in the summary (§19.1 strict
  contract).

**What this module is NOT:**

* a writer — Phase F,
* a fetcher of raw conversation messages — the Topic 6 privacy cap
  is "curated summary text only, no raw messages", and this module
  is structurally incapable of violating it because it only reads
  from the ``session_summaries`` table,
* a long-lived cache — summaries are small, reads are rare (opening
  turn only), and we want the latest row every time.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

SESSION_SUMMARY_READER_VERSION = 1

# Character cap applied **defensively on read** so a runaway summary
# row in the DB cannot bloat every opening-turn system prompt.
# The 3C.10 spec says ``≤ 500 tokens``; English averages ~4 chars per
# token with gpt-4 tokenization, so ~2000 chars is a safe upper bound
# that always stays under 500 tokens even for dense punctuation.
_MAX_SUMMARY_CHARS = 2000

# Label used in the prompt. Locked by contract tests — changing it
# breaks any existing logging / evals that grep for this header.
_PROMPT_SECTION_HEADER = "## PRIOR SESSION SUMMARY"

logger = logging.getLogger(__name__)


def read_most_recent_session_summary(
    session: Session,
    user_id: str,
) -> Optional[str]:
    """Return the most recent curated summary for ``user_id``, if any.

    Returns ``None`` on any of:

    * the ``session_summaries`` table does not exist yet (Phase F has
      not landed — this is the expected V1.6 state),
    * no row exists for this user,
    * the latest row's summary text is empty / whitespace / non-str,
    * any SQL or driver error (defensive — a broken read must never
      break a turn; we log and degrade to "no prior summary").

    The query hits the ``session_summaries`` table directly with raw
    SQL because the ORM model itself is Phase F work. Using
    :func:`sqlalchemy.text` keeps this module independent of any
    future migration ordering and means the moment Phase F creates
    the table + model, this reader starts producing summaries with
    zero further code change.

    Expected schema (Phase F):

    .. code-block:: sql

        session_summaries (
            id           UUID PRIMARY KEY,
            user_id      UUID NOT NULL REFERENCES user_identity(user_id),
            summary_text TEXT NOT NULL,
            created_at   TIMESTAMP NOT NULL DEFAULT now()
        );
    """
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
        # Table-missing / permission / driver error — any of these
        # map to "no summary available", not a turn-breaking failure.
        logger.debug(
            "[session_summary_read] skipped (no session_summaries or query error): %s",
            exc,
        )
        # Postgres marks the transaction aborted on any failed statement;
        # we must rollback before the shared request session runs further
        # queries (e.g. user_profile) or callers see InFailedSqlTransaction.
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
        # Truncate on a word boundary where possible. Ellipsis is
        # appended so the coach can see the summary was clipped and
        # avoid treating the tail as a hard stop.
        cutoff = _MAX_SUMMARY_CHARS
        # Find the nearest preceding space to avoid cutting mid-word.
        space = trimmed.rfind(" ", 0, cutoff)
        if space > cutoff - 120:  # keep the trim within 120 chars of the cap
            cutoff = space
        trimmed = trimmed[:cutoff].rstrip() + " …"
    return trimmed


def session_summary_section(summary: Optional[str]) -> str:
    """Format ``summary`` as a labeled system-prompt section.

    Returns ``""`` when the summary is ``None`` / empty — callers
    (orchestrator composition) rely on :func:`_join_nonempty_system_sections`
    to silently drop empty sections, so this function is safe to
    call unconditionally.

    When present, the returned block contains:

    * a clearly-labeled header (``## PRIOR SESSION SUMMARY``) so the
      coach can recognize this as *context from a past conversation*
      rather than freshly retrieved facts,
    * an explicit coach-must-not-invent instruction cross-referencing
      §19.1 (backend = truth, LLM = interpretation) — prevents the
      coach from fabricating detail beyond what the summary contains,
    * the summary body verbatim.
    """
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
    """Return True when the conversation already has an assistant turn.

    Used by the orchestrator to distinguish the **first-ever** turn
    of a brand-new thread (where summary injection is wanted) from
    an ``opening``-classified topic reset inside an existing thread
    (where the recent messages already provide the continuity — no
    summary needed).

    Accepts the orchestrator's ``List[Dict[str, str]]`` shape. Any
    non-list or malformed entries are treated as "no prior
    assistant" — the injection is defensive-preferred: missing
    context is strictly better than wrong context.
    """
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

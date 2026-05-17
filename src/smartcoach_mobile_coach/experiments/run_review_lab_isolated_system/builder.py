"""
Isolated system prompt for Run Review Lab (experiment).

When enabled, the lab completion omits the full orchestrator ``system_content``
stack (SYSTEM_PROMPT_BASE, metric glossary, plan contracts, coach tone / prose
shape, response directive, etc.) and replaces it with a short grounding block
plus small factual slices (device date, optional HR calibration, optional
thread continuity).

Lazy-imports orchestrator HR helper at call time to avoid import cycles while
``orchestrator`` is still loading.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.smartcoach_mobile_coach.thread_derived_context import DerivedThreadCoachContext

_ISOLATED_LAB_BASE = """
You are SmartCoach. This is a **run-review experiment turn**: the only structured
run data for grounding is in the **appended JSON** (not live tool results for
this completion).

Rules:
- Reply in **Markdown prose** (coach voice). Do **not** output JSON or code
  fences in your reply.
- Use **only** numbers and facts present in that JSON; if something is missing,
  say so — do **not** invent metrics.
- Simple comparisons and arithmetic **using values in the JSON** (e.g. deltas,
  zone percentages) are allowed.
- No medical diagnosis; for pain or injury concerns, suggest consulting a
  professional.
- Do **not** say you are calling tools or fetching data — this turn is
  single-shot with pre-loaded context only.
""".strip()


def build_isolated_lab_system_prefix(
    *,
    anchor_local_date: str,
    client_timezone: Optional[str],
    session: Session,
    internal_user_id: str,
    thread_ctx: Optional[DerivedThreadCoachContext] = None,
) -> str:
    """Return a compact system prefix for lab when ``SMARTCOACH_RUN_REVIEW_LAB_ISOLATED_SYSTEM`` is on."""
    parts: list[str] = [_ISOLATED_LAB_BASE]
    tz_display = (client_timezone or "").strip() or "unknown"
    date_token = (anchor_local_date or "").strip()[:10] or "unknown"
    parts.append(
        "\n## Device context\n"
        f"- User's local calendar date: **{date_token}** (IANA timezone: **{tz_display}**).\n"
        "- The run under review is described in the JSON below; ground the read there.\n"
    )

    from src.smartcoach_mobile_coach.orchestrator import (  # noqa: PLC0415 — lazy import
        _hr_calibration_system_section,
    )

    hr_block = _hr_calibration_system_section(session, str(internal_user_id))
    if hr_block.strip():
        parts.append("\n" + hr_block.strip())

    if thread_ctx is not None and thread_ctx.prior_run_summary_in_thread:
        aid = thread_ctx.last_structured_run_activity_id
        if isinstance(aid, int) and aid > 0:
            parts.append(
                "\n## Thread continuity\n"
                f"- This conversation already discussed a structured run summary; the latest "
                f"parsed `activity_id` from the thread is **{aid}** (should match the JSON "
                f"unless the user changed topics).\n"
            )

    return "\n".join(parts).strip() + "\n\n"

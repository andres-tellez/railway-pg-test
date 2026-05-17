"""
Assemble the additive system block for Run Review V2.

The orchestrator already builds a long, carefully-tuned system prompt
(``SYSTEM_PROMPT_BASE`` and friends). We do **not** replace that. We
**append** a focused block that:

1. Tells the model this is a *completed-run review* turn.
2. Embeds the compact JSON the model should ground on (single source of truth).
3. Lists a small set of evidence-reading rules — what counts, what to
   avoid — without dictating the verdict text.
4. For tempo / threshold / interval / progression / race intents, it adds
   one extra reminder: do **not** speak about the run like an easy run.

Strict rules we encode:

- The model must not invent numbers not present in the JSON.
- When the model cites session-level distance or HR, it must align with
  ``run_facts`` and the RunSummary card.

We add a single short example anchored on intent **shape only** ("tempo
session"), not on numbers, so we do not give the LLM a script. The
example is also marked as illustrative.

At import time this module loads ``rubric.md`` (coaching rubric text only;
no verdict code).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.smartcoach_mobile_coach.coach_tone_contract import (
    COACH_TONE_CONTRACT_BLOCK,
    COACH_TURN_PROSE_SHAPE_BLOCK,
)
from src.smartcoach_mobile_coach.run_review.context import RunReviewContext

RUN_REVIEW_RUBRIC_VERSION = "run_review_rubric_v1"

_RUN_REVIEW_RUBRIC_PATH = Path(__file__).with_name("rubric.md")


def _load_run_review_rubric_body() -> str:
    return _RUN_REVIEW_RUBRIC_PATH.read_text(encoding="utf-8")


_RUN_REVIEW_RUBRIC_TEXT = _load_run_review_rubric_body()


_RUN_REVIEW_HEADER = "## Completed-run review (RunReview V2)"


_GENERAL_GUIDANCE = (
    "You are reviewing **one specific completed run** for this athlete. "
    "Coach them like a thoughtful, experienced running coach.\n\n"
    "Rules for this turn:\n"
    "- Ground every number in the pre-loaded JSON below. Do **not** invent "
    "splits, paces, or HR values.\n"
    "- Use the evidence to find the story of the run. Explain what happened, "
    "why it likely happened, what is uncertain, and what the runner should learn.\n"
    "- Do not summarize the RunSummary card or merely restate headline stats.\n"
    "- Do not force an insight if the evidence is ordinary.\n"
    "- Focus on interpretation. **If** you cite distance, average pace, "
    "average HR, or max HR in prose, use **exactly** the values in "
    "``run_facts`` (authoritative). Do not use lap/split extremes as "
    "session-level avg or max HR.\n"
    "- For long easy/Z2 runs, consider distance/duration, HR control over time, "
    "splits shape, zone distribution, and whether the finish stayed controlled.\n"
    "- If ``similar_runs_count`` is small, say comparison evidence is limited and "
    "anchor your read on this run's splits, zones, and plan intent instead.\n"
    "- Use splits and HR progression only when they meaningfully explain the run.\n"
    "- Use comparisons to recent similar runs only when they add insight.\n"
    '- Avoid generic takeaways like "keep pace steady" unless splits clearly show '
    "pacing is the main issue.\n"
    "- Give one useful lesson the runner could not get from the card alone.\n"
    '- Use plain coaching language. Never use scare words like "red zone", '
    '"overtraining", or "burnout". Never describe a tempo or quality '
    "session as if it were an easy run.\n"
    "- If a metric is missing from the JSON (e.g. HR drift, zone bounds), "
    "do not cite it. Say what is unknown instead of inventing a cause.\n"
    "- Keep the reply tight. No bullet lists unless the user explicitly asked "
    "for splits.\n"
)


_QUALITY_SESSION_GUIDANCE = (
    "This run was planned as a **quality session** "
    "(tempo / threshold / interval / progression / race). Frame the read "
    "accordingly:\n"
    "- Elevated HR during the working portion is *expected*. Do not tell "
    'the athlete to "dial back effort" just because Z3+ HR appears.\n'
    "- The interesting questions are **execution** ones: did pace stay "
    "steady or drift? Did HR rise faster than pace? Were the main-block "
    "miles the right effort? Did they finish smooth or fade?\n"
    "- If the JSON shows pace slowing while HR stayed elevated late in "
    "the run, call that **late fade** in plain language and explain why "
    "it matters for tempo/quality work.\n"
)


_EASY_OR_LONG_GUIDANCE = (
    "This run was planned as an **easy or long run**. Frame the read "
    "accordingly:\n"
    "- The right question is whether effort stayed *aerobic*. HR creeping "
    "above Z2 across the run, or pace getting faster while HR climbs, "
    "suggests the run drifted harder than intended.\n"
    "- For clean easy/long runs, do not stop at reassurance. Use splits, zone "
    "distribution, duration, plan intent, and Evidence Pack context to explain "
    "what made the run controlled, what is uncertain, and what the runner "
    "should learn.\n"
)


_UNPLANNED_GUIDANCE = (
    "There is **no matched planned workout** for this run. Treat the run "
    "as an *unplanned* session: comment on what actually happened, but do "
    'not invent a planned intent (no "this was a tempo" unless the data '
    "and splits clearly say so). When in doubt, read it as an easy run.\n"
)


def _output_contract_block(ctx: RunReviewContext) -> str:
    sentence_range = "**3–6 sentences**"
    planned_type = (ctx.workout_intent.planned_type or "").strip().lower()
    is_long_easy = planned_type in {"long", "long_run"}
    if is_long_easy and isinstance(ctx.evidence_pack, dict):
        sentence_range = (
            "**4–8 sentences** are allowed for this long easy/Z2 run "
            "because Evidence Pack context is present"
        )
    return (
        "## Output format for this turn\n"
        "- Return Markdown prose only. No JSON, no code fences.\n"
        "- Prose shape: *interpretation* → *evidence* → *one takeaway*.\n"
        f"- Keep it concise: {sentence_range}.\n"
        "- The takeaway sentence must be specific and tied to the evidence "
        "you just cited (not a generic platitude).\n"
    )


_NO_TOOLS_NOTE = (
    "All evidence you need is already pre-loaded below. **Do not call any "
    "tools** for this turn — the orchestrator is operating in a single-"
    "completion review path."
)


def _intent_guidance_block(ctx: RunReviewContext) -> str:
    intent = ctx.workout_intent
    blocks: List[str] = []
    if intent.is_quality_session:
        blocks.append(_QUALITY_SESSION_GUIDANCE)
    elif intent.is_easy_or_long:
        blocks.append(_EASY_OR_LONG_GUIDANCE)
    if (intent.plan_status or "").lower() == "unplanned":
        blocks.append(_UNPLANNED_GUIDANCE)
    return "\n".join(blocks).strip()


def build_run_facts_for_prompt(ctx: RunReviewContext) -> Dict[str, Any]:
    """Session-level display metrics aligned with the RunSummary card.

    Keys mirror the ``run_facts`` section in ``rubric.md``. Missing or
    placeholder display values become JSON ``null``.
    """
    facts = ctx.facts if isinstance(ctx.facts, dict) else {}

    def pick_display(*keys: str) -> Optional[str]:
        for key in keys:
            raw = facts.get(key)
            if raw is None:
                continue
            text = str(raw).strip()
            if not text or text in ("—", "-", "n/a", "N/A"):
                continue
            return text
        return None

    return {
        "distance": pick_display("distance_display"),
        "avg_pace": pick_display("avg_pace_display"),
        "avg_hr": pick_display("avg_heart_rate_display"),
        "max_hr": pick_display("max_heart_rate_display"),
    }


def _run_facts_block(ctx: RunReviewContext) -> str:
    payload = build_run_facts_for_prompt(ctx)
    intro = (
        "## Authoritative `run_facts`\n\n"
        "These fields match the RunSummary card. When you cite distance, "
        "average pace, average heart rate, or max heart rate in prose, use "
        "**only** these values. Splits/laps may explain progression; they "
        "must not replace or contradict these session-level numbers.\n\n"
        "```json\n"
        f"{json.dumps(payload, default=str, indent=2)}\n"
        "```"
    )
    return intro


def _evidence_pack_block(ctx: RunReviewContext) -> Optional[str]:
    if not isinstance(ctx.evidence_pack, dict):
        return None
    return (
        "## Evidence Pack (factual only)\n\n"
        "Use this pack as structured evidence. It contains facts and simple arithmetic; "
        "it does not contain coaching verdict labels.\n\n"
        "```json\n"
        f"{json.dumps(ctx.evidence_pack, default=str, indent=2)}\n"
        "```"
    )


def _coaching_rubric_block() -> str:
    return "## Coaching Evaluation Rubric\n\n" f"{_RUN_REVIEW_RUBRIC_TEXT.rstrip()}\n"


def _splits_guidance_block(ctx: RunReviewContext) -> str:
    if not ctx.splits:
        return (
            "**Splits:** No per-lap data is available for this run. Make a "
            "session-level read using the metrics in the JSON; do not invent "
            "mile-by-mile numbers."
        )
    lines: List[str] = [
        "**Splits:** Per-lap rows are pre-loaded under ``splits``. Use them "
        "as the primary evidence for pace shape and HR shape across the run. "
        "Quote at most **2** specific mile/lap callouts in your prose."
    ]
    if ctx.splits_truncated:
        lines.append(
            "The splits array is **head + tail capped** for speed — early "
            "and late laps are present, the middle laps are omitted. Do not "
            "claim anything about the omitted middle."
        )
    return "\n".join(lines)


def build_run_review_system_appendix(ctx: RunReviewContext) -> str:
    """
    Return the additive system block to concatenate after the base prompt.

    Includes a single embedded JSON code block with the compact context.
    """
    compact = ctx.to_compact_dict()
    parts: List[str] = [
        "",
        _RUN_REVIEW_HEADER,
        _GENERAL_GUIDANCE,
    ]
    evidence_block = _evidence_pack_block(ctx)
    if evidence_block:
        parts.append(evidence_block)
    parts.append(_run_facts_block(ctx))
    intent_block = _intent_guidance_block(ctx)
    if intent_block:
        parts.append(intent_block)
    parts.append(_splits_guidance_block(ctx))
    parts.append(_output_contract_block(ctx))
    parts.append(_coaching_rubric_block())
    parts.append("## Pre-loaded run context (compact JSON)")
    parts.append("```json")
    parts.append(json.dumps(compact, default=str))
    parts.append("```")
    parts.append(_NO_TOOLS_NOTE)
    return "\n".join(parts)


def build_messages(
    *,
    base_system_content: str,
    ctx: RunReviewContext,
    conversation_history: List[Dict[str, str]],
    user_message: str,
    history_window: int,
) -> List[Dict[str, str]]:
    """
    Build the final ``messages`` array for the responder LLM call.

    Mirrors the assembly pattern in the legacy fastpath: one combined
    system message (base + V2 appendix), trailing conversation history
    clamped to ``history_window``, and the current user turn last.
    """
    base_for_v2 = _strip_global_contracts_for_run_review_v2(base_system_content or "")
    augmented_system = base_for_v2 + build_run_review_system_appendix(ctx)
    messages: List[Dict[str, str]] = [{"role": "system", "content": augmented_system}]
    if conversation_history:
        for m in conversation_history[-history_window:]:
            role = m.get("role")
            content = m.get("content")
            if (
                role in ("user", "assistant")
                and isinstance(content, str)
                and content.strip()
            ):
                messages.append({"role": str(role), "content": content.strip()})
    messages.append({"role": "user", "content": (user_message or "").strip()})
    return messages


def estimate_appendix_chars(ctx: RunReviewContext) -> int:
    """Cheap size sanity check used by tests to keep payloads bounded."""
    return len(build_run_review_system_appendix(ctx))


def appendix_for_test(ctx: RunReviewContext) -> str:  # pragma: no cover - test helper
    """Test-only re-export so tests don't depend on internal naming."""
    return build_run_review_system_appendix(ctx)


def compact_payload_for_test(  # pragma: no cover - test helper
    ctx: RunReviewContext,
) -> Dict[str, Any]:
    """Return the dict that gets embedded as JSON in the appendix."""
    return ctx.to_compact_dict()


def _strip_global_contracts_for_run_review_v2(base_system_content: str) -> str:
    """Remove global prose/tone contracts so V2 controls its own style.

    This runs only in RunReview V2 message assembly and leaves non-V2 paths
    unchanged.
    """
    text = str(base_system_content or "")
    for block in (COACH_TONE_CONTRACT_BLOCK, COACH_TURN_PROSE_SHAPE_BLOCK):
        if block and block in text:
            text = text.replace(block, "")
    text = re.sub(r"\n{3,}", "\n\n", text).rstrip()
    if text:
        text += "\n\n"
    return text

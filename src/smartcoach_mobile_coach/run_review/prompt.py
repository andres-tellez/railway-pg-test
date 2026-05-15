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
- The model must not repeat the headline RunSummaryCard stats verbatim.
- The model must use plain coaching language; never "red zone",
  "overtraining", or "burnout" framing.
- The model must close with one specific, actionable takeaway.

We add a single short example anchored on intent **shape only** ("tempo
session"), not on numbers, so we do not give the LLM a script. The
example is also marked as illustrative.

This file produces strings — no LLM calls, no I/O.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from src.smartcoach_mobile_coach.run_review.context import RunReviewContext


_RUN_REVIEW_HEADER = "## Completed-run review (RunReview V2)"


_GENERAL_GUIDANCE = (
    "You are reviewing **one specific completed run** for this athlete. "
    "Coach them like a thoughtful, experienced running coach: identify "
    "what the run was *meant* to be, judge how it actually went vs that "
    "intent, then leave them with one clear, actionable takeaway.\n\n"
    "Rules for this turn:\n"
    "- Ground every number in the pre-loaded JSON below. Do **not** invent "
    "splits, paces, or HR values.\n"
    "- Do **not** repeat the headline RunSummaryCard stats (distance, "
    "duration, avg pace, avg/max HR). The mobile app already shows those "
    "above your reply.\n"
    "- Read the *right* evidence: when splits are present they are usually "
    "the key signal. Look for pace drift across miles, HR drift across "
    "miles, late fade, big pace swings, and whether intensity matched the "
    "intent.\n"
    '- Use plain coaching language. Never use scare words like "red zone", '
    '"overtraining", or "burnout". Never describe a tempo or quality '
    "session as if it were an easy run.\n"
    "- If a metric is missing from the JSON (e.g. HR drift, zone bounds), "
    "do not cite it. Make a qualitative read or skip that point.\n"
    "- Keep the reply tight: **3–6 sentences** of prose. End with **one** "
    "specific takeaway sentence the athlete can apply next time. "
    "No bullet lists unless the user explicitly asked for splits.\n"
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
    "- A clean easy run will usually show steady pace, low-to-mid Z2 HR, "
    "and minor HR drift. Say so plainly when that's what the data shows.\n"
)


_UNPLANNED_GUIDANCE = (
    "There is **no matched planned workout** for this run. Treat the run "
    "as an *unplanned* session: comment on what actually happened, but do "
    'not invent a planned intent (no "this was a tempo" unless the data '
    "and splits clearly say so). When in doubt, read it as an easy run.\n"
)


_OUTPUT_CONTRACT = (
    "## Output format for this turn\n"
    "- Return Markdown prose only. No JSON, no code fences.\n"
    "- Prose shape: *interpretation* → *evidence* → *one takeaway*.\n"
    "- The takeaway sentence must be specific and tied to the evidence "
    "you just cited (not a generic platitude).\n"
)


_NO_TOOLS_NOTE = (
    "All evidence you need is already pre-loaded below. **Do not call any "
    "tools** for this turn — the orchestrator is operating in a single-"
    "completion review path."
)


def _example_block_for_intent(intent_type: str) -> str:
    """Tiny illustrative example showing *shape only*. No numbers."""
    if intent_type in (
        "tempo",
        "threshold",
        "interval",
        "intervals",
        "speed",
        "progression",
        "race",
    ):
        return (
            "Example shape (illustrative only, not a script):\n"
            "> This was a productive [intent] session. The middle miles held "
            "steady at the intended effort, and HR responded the way you'd "
            "want. The late drop in pace with HR still elevated is the part "
            "to watch — that's a late-fade signal, not a sign the whole run "
            "was too hard. Next time, start the working portion a touch more "
            "controlled so you finish smoother.\n"
        )
    if intent_type in ("easy", "recovery", "long", "long_run"):
        return (
            "Example shape (illustrative only, not a script):\n"
            "> This looked like a clean easy run overall. Pace stayed even "
            "and HR drifted only slightly across the miles, which is what "
            "you want from an aerobic day. One thing to watch is the gap "
            "between early and late HR — if it widens on a similar run, "
            "consider easing the start by a few seconds per mile.\n"
        )
    return (
        "Example shape (illustrative only, not a script):\n"
        "> This run shows steady early effort and a faster finish. The "
        "evidence to point at is the split-by-split pace shape, not the "
        "averages already on the card. One thing to take into the next run "
        "is being clearer about its intent — was this meant to be easy, or "
        "a controlled progression?\n"
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
    intent_block = _intent_guidance_block(ctx)
    if intent_block:
        parts.append(intent_block)
    parts.append(_splits_guidance_block(ctx))
    parts.append(_OUTPUT_CONTRACT)
    parts.append(
        _example_block_for_intent((ctx.workout_intent.planned_type or "").lower())
    )
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
    augmented_system = (base_system_content or "") + build_run_review_system_appendix(
        ctx
    )
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

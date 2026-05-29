"""
Plan-creation branch helpers extracted from the mobile orchestrator (Phase 7).
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import replace
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.coaching_intelligence.pre_generation_runner_review import (
    build_pre_generation_runner_review_v1,
    pre_generation_runner_review_system_section,
    runner_review_feature_enabled,
)
from src.smartcoach_mobile_coach.agent_tools import (
    _intake_alignment_enabled,
    tool_update_plan_intake,
)
from src.smartcoach_mobile_coach.dialogue_manager import (
    INTENT_PLAN_CREATION,
    ResponseDirective,
)
from src.smartcoach_mobile_coach.plan_creation_ui import (
    PHASE_AWAITING_TRADEOFF_CHOICE,
    PHASE_COLLECTING_ADDITIONAL_TRAINING_DAY,
    PHASE_COLLECTING_GOAL_ADJUSTMENT,
    PHASE_COLLECTING_TIMELINE_ADJUSTMENT,
    apply_review_to_plan_intake_ux_for_phase,
    compute_plan_creation_ui,
)
from src.smartcoach_mobile_coach.plan_intake_activity_context import (
    apply_plan_activity_preamble_to_assistant_markdown,
)
from src.smartcoach_mobile_coach.plan_intake_flow import (
    alignment_pause_coaching_facts_system_section,
    build_plan_request_from_state,
    mark_plan_runner_understanding_shown,
    plan_creation_split_confirm_enabled,
    plan_intake_alignment_pause_active,
    plan_runner_understanding_shown,
    schedule_confirmation_system_section,
    structured_intake_core_v1_enabled,
)
from src.smartcoach_mobile_coach.readiness_gate import get_or_compute_readiness_gate
from src.smartcoach_mobile_coach.thread_derived_context import DerivedThreadCoachContext

from . import phase_prompts

logger = logging.getLogger("smartcoach_mobile_coach")


def _anchor_date_from_device_context(
    anchor_local_date: Optional[str],
) -> Optional[date]:
    if not anchor_local_date or not str(anchor_local_date).strip():
        return None
    try:
        return date.fromisoformat(str(anchor_local_date).strip()[:10])
    except ValueError:
        return None


def _plan_intake_phase_system_section(
    intake_state: Optional[Dict[str, Any]],
) -> str:
    if not isinstance(intake_state, dict):
        return ""
    ux_phase = (
        intake_state.get("ux") if isinstance(intake_state.get("ux"), dict) else {}
    )
    phase0 = str(ux_phase.get("plan_creation_phase") or "")
    add_day_flow = (
        plan_creation_split_confirm_enabled()
        and phase0 == PHASE_COLLECTING_ADDITIONAL_TRAINING_DAY
    ) or (
        ux_phase.get("runner_add_day_pick_pending")
        and ux_phase.get("training_days_expansion_pending")
    )
    if add_day_flow:
        return phase_prompts.add_day.prompt(intake_state)
    if intake_state.get("ready_to_generate"):
        if plan_creation_split_confirm_enabled():
            ux = (
                intake_state.get("ux")
                if isinstance(intake_state.get("ux"), dict)
                else {}
            )
            if not ux.get("intake_confirmed"):
                return phase_prompts.awaiting_intake_recap_confirm.prompt(intake_state)
            if not ux.get("runner_review_delivered"):
                return phase_prompts.runner_review_delivered.prompt(intake_state)
            phase = str(ux.get("plan_creation_phase") or "")
            if phase in (
                PHASE_COLLECTING_GOAL_ADJUSTMENT,
                PHASE_COLLECTING_TIMELINE_ADJUSTMENT,
            ) or ux.get("runner_tradeoff_edit_focus") in ("goal", "timeline"):
                return phase_prompts.goal_adjustment.prompt(intake_state)
            tradeoff_chips = phase == PHASE_AWAITING_TRADEOFF_CHOICE or (
                not phase and ux.get("runner_tradeoff_pending")
            )
            if tradeoff_chips:
                return phase_prompts.tradeoff.prompt(intake_state)
            if not ux.get("plan_generation_confirmed"):
                return phase_prompts.plan_build_confirmation.prompt(intake_state)
            return phase_prompts.authorized.prompt(intake_state)
        return phase_prompts.ready_to_confirm.prompt(intake_state)
    return phase_prompts.collecting.prompt(intake_state)


PLAN_CREATION_SYSTEM_PROMPT_BASE = """
You are SmartCoach helping one runner create a training plan through deterministic server tools.
Primary objective: make plan setup feel like a real coaching conversation while preserving deterministic server intake and generation.

Required fields (exact keys for `update_plan_intake` `updates`): `race_distance`, `race_date`,
`primary_goal`, `training_days`, and `target_time` only when `primary_goal` is **Target Time**.
Optional enrichments any time before generate: `race_name`, `race_location`, `long_run_day`, `notes`, `plan_name`.

Experience stages:
- `understand_runner`: the server may prepend a short deterministic runner understanding summary. Do not repeat it.
- `goal_alignment`: ask naturally what they are training for; map the answer into race distance/name/date when possible.
- `details`: collect remaining details in natural language.
- `confirm`: summarize simply and ask whether it looks right.
- `fast_track`: if the user gave enough details upfront, skip redundant questions and move to confirmation.
- `generated`: after plan creation, explain what was created and point them to the Plan tab.

Intake behavior:
- **Always** call `update_plan_intake` on the latest user message (merge partial answers in `updates`).
- **While `missing_required` is non-empty, never end the turn with prose alone** — call `update_plan_intake` first so the server can merge fields (short prompts depend on tools for truth).
- Use the **latest tool result** `missing_required` as the source of truth for what is still missing.
- Ask **exactly one** clear question per turn when a question is needed. Do **not** ask overlapping questions.
- Never expose the words `missing_required`, `ready_to_generate`, field keys, or tool/status names to the user.
- Preferred first question: “What are you training for?” or “What are you training for right now?”
- Ask in coach language, not form language: “What are you training for?”, “Are you trying to finish strong or hit a specific time?”, “Which days of the week work best for you?”
- Do not use filler openers like “Great!”, “I’m here to help”, “I can help with that”, or “Let’s get started.”
- If the user volunteers several answers at once, pass them all in one `updates` object and then ask only
  for what remains in `missing_required`.
- If the user gives only a numeric running frequency (for example, “5 days per week”), pass that as
  `training_days` so the server can store the count, but **do not** invent weekdays. If `training_days`
  remains missing and `ux.training_days_count` is present, ask exactly one question: “Which days of the week work best for you?”
- **Never** ask for final “generate the plan?” yes/no until the latest `update_plan_intake` shows
  `ready_to_generate=true`. A days-per-week **count** alone is not a complete schedule—collect actual weekdays
  before any full-plan confirmation.
- If the latest tool result is `ready_to_generate=true`, do **not** ask another intake question. Move to confirmation.
- **Do not** ask for self-reported “experience level” or “beginner/intermediate/advanced” for this flow;
  baseline comes from their activity data, not chat labels.
- **Do not** ask how many **weeks** (or months) the plan should run or how long they want to train; the server sets length from **race date** and baseline. **Never** ask that even right after they gave a race date—ask the next `missing_required` field only.
- **Do not** suggest arbitrary race products (e.g. 5K/10K) as plan targets. Supported distances today are
  **Half Marathon** and **Marathon** only. If they want another distance, say it is not supported yet and
  offer Half or Full.
- For `primary_goal`, the only valid values are **Just Finish** and **Target Time** (exactly those phrases
  in `updates`). Frame the question as finishing the race vs hitting a goal time; if Target Time, ask for their
  goal finish time (clock or spoken duration); pass it as `target_time`.
- If the user gives a **clock time only** (e.g. “3:40”, “3:45:00”) without saying “target time”, still pass
  `primary_goal` **Target Time** and `target_time` in `updates` — the server can also infer this from the
  latest user message when the model omits it.
- After **Target Time** and `target_time` are in the intake draft, call **`get_training_targets`** before
  final plan confirmation. Use only the paces returned there for marathon / easy / tempo / threshold
  (destination). Explain that **plan workout paces** come from recent fitness (starting point), not goal
  pace on week one — never invent pace numbers in prose.
- For `race_distance`, when the user names a **full marathon** event (e.g. “Chicago Marathon”, “Boston”, “a fall
  marathon”) or clearly means 26.2, set `race_distance` to **Marathon** in the same `update_plan_intake` call and
  **do not** ask half vs full again. Only ask half vs full when the goal distance is ambiguous (no named marathon,
  no “half” / “13.1” / “marathon” / “26.2” signal). Same turn: set `race_name` to the event string they used.
- For `race_date`, ask when the race is; accept natural language and pass it as `race_date`.
- The server also parses common **date-only** replies (e.g. “October 11”) from the user’s last message into
  `race_date` when the model forgets to pass `updates`—check the tool intake draft before asking for the date again.
- The server also infers **weekday lists** (e.g. “Mon–Thu”, “Monday through Thursday”) from the user’s last message into
  `training_days` when the model forgets to pass them in `updates`—check the tool intake draft before asking for weekdays again.
- Whenever the user names a specific race, pass **`race_name`** in `updates` (exactly as they said is fine) so it
  appears on the saved plan; do not wait for a separate prompt if they already named it.
- After required fields are satisfied (`ready_to_generate` true) **and before** you ask for final yes/no to generate,
  you may ask **once** for optional `notes` (injuries, travel, constraints)—if they decline or ignore, proceed.

Confirmation and generate:
- Only call `generate_training_plan` after explicit user confirmation with `confirm=true`.
- Keep user-facing wording short and conversational: maximum **4 sentences** during intake (up to **3**
  runner-understanding sentences + **1** question); up to a short multi-line walkthrough right after successful generation.
- Confirmation should be simple: race, goal, schedule. Then ask “Does that look right?” or equivalent.
- Tool payload is the source of truth; never invent field values not returned by tools.
- For any target-time pace question, **`get_training_targets`** is the only authoritative source for goal paces.
- The server accepts common **spoken dates**, **spoken training-day ranges** (e.g. “Monday through Saturday”,
  “weekdays plus Saturday”), and **goal-time phrases** in tool updates; still pass what the user said in `updates`.

After a successful `generate_training_plan`, provide a compact walkthrough using `plan_generation` payload:
  1) confirm plan saved and mention start date (if present),
  2) one baseline line (`baseline.avg_weekly_miles`, `baseline.longest_recent_run_miles` when present),
  3) one high-level overview line (`overview.total_weeks`, `overview.phase_sequence`, peak long run or weekly mileage),
  4) show Week 1 workouts from `this_week.workouts` when present; otherwise say workouts are ready in Plan,
  5) explicitly direct the runner to the Plan tab for full details.
""".strip()


def _plan_creation_directive_stub(directive: ResponseDirective) -> str:
    return (
        "## Response directive (plan creation mode)\n"
        f"- Turn type: **{directive.turn_type}** | Intent: **{directive.intent}**\n"
        "- Keep the response concise and coach-like; this should feel like guidance, not a form.\n"
        "- Use `update_plan_intake` silently, then ask natural follow-up questions based on what is still missing. "
        "Do not expose field names or tool state to the user.\n"
        "- Ask exactly one question per turn when a question is needed. Preferred first question: "
        "“What are you training for?” Do not pair it with “Do you have a specific race in mind?”\n"
        "- Strip filler from your own wording: no “Great!”, “I’m here to help”, “I can help with that”, or “Let’s get started.”\n"
        "- Keep intake replies to 4 sentences max. If enough details are present, skip redundant questions and confirm.\n"
        "- If they gave a count like “5 days per week” but not actual weekdays, ask only: “Which days of the week work best for you?” "
        "Do not invent weekdays.\n"
        "- Do not ask final yes/no to generate until `ready_to_generate=true` from `update_plan_intake` "
        "(a frequency count is not enough—weekdays must be set first).\n"
        "- Follow **## Plan intake phase — …** in the system prompt: COLLECTING vs READY_TO_CONFIRM — never mix them.\n"
        "- Infer Marathon from named full marathons when unambiguous; do not re-ask half vs full in that case.\n"
        "- Do not ask experience level, plan length in weeks/months, or how long they want to train—length is from **race date** only. "
        "After they give a race date, never ask about duration; ask the next `missing_required` field only. "
        "Unsupported race distances: only Half / Marathon.\n"
        "- If all required details exist, show a simple confirmation summary (race, goal, schedule) and ask explicit yes/no.\n"
        "- Do not discuss unrelated run-analysis topics in this mode.\n"
    )


def _join_nonempty_system_sections(*sections: str) -> str:
    return "\n\n".join(s.strip() for s in sections if (s or "").strip())


def runner_review_required_before_generate() -> bool:
    """When false, runner-review section waits for ``ready_to_generate`` even if intake is confirmed."""
    raw = (
        (os.getenv("SMARTCOACH_RUNNER_REVIEW_REQUIRED_BEFORE_GENERATE") or "1")
        .strip()
        .lower()
    )
    return raw not in ("0", "false", "no", "off")


def _try_build_runner_review_bundle(
    session: Session,
    internal_user_id: str,
    plan_intake_state: Dict[str, Any],
    *,
    anchor_local_date: Optional[str] = None,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Build optional pre-generation runner review system section + API dict.

    Returns ``("", None)`` when the feature is off, split-confirm gates fail,
    or assessment/plan_request construction fails. When split-confirm is on
    and ``runner_review_required_before_generate()`` is true (default), the
    bundle is built after ``intake_confirmed`` even if ``ready_to_generate``
    is still pre-wired false — so Runner Analysis can render for LEVEL_READY
    and other states that still carry a trust-building card.

    Failures are logged and never break the turn.
    """
    if not runner_review_feature_enabled():
        return ("", None)
    if not isinstance(plan_intake_state, dict):
        return ("", None)
    if plan_creation_split_confirm_enabled():
        ux0 = (
            plan_intake_state.get("ux")
            if isinstance(plan_intake_state.get("ux"), dict)
            else {}
        )
        if not ux0.get("intake_confirmed"):
            return ("", None)
        if (
            ux0.get("runner_goal_edit_pending")
            or ux0.get("runner_tradeoff_edit_focus") == "goal"
        ):
            return ("", None)
        if not runner_review_required_before_generate():
            if not plan_intake_state.get("ready_to_generate"):
                return ("", None)
    elif not plan_intake_state.get("ready_to_generate"):
        return ("", None)
    try:
        plan_request = build_plan_request_from_state(plan_intake_state)
        gate_result = get_or_compute_readiness_gate(
            session=session,
            internal_user_id=str(internal_user_id),
            plan_request=plan_request,
            plan_intake_state=plan_intake_state,
            alignment_enabled=_intake_alignment_enabled(),
            anchor_local_date=_anchor_date_from_device_context(anchor_local_date),
        )
        assessment_api = gate_result.assessment_api
        readiness_api = gate_result.readiness_api
        logger.info(
            "[readiness_gate] %s",
            json.dumps(
                {
                    "trace_id": readiness_api.get("trace_id"),
                    "policy_version": readiness_api.get("policy_version"),
                    "decision": readiness_api.get("decision"),
                    "readiness_level": readiness_api.get("readiness_level"),
                    "reason_codes": readiness_api.get("reason_codes"),
                    "user_id": str(internal_user_id),
                    "plan_request_digest_sha256": gate_result.plan_request_digest_sha256,
                    "evidence_snapshot_id": readiness_api.get("evidence_snapshot_id"),
                    "cache_status": gate_result.cache_status,
                },
                default=str,
            ),
        )
        review = build_pre_generation_runner_review_v1(
            assessment_api=assessment_api,
            plan_request=plan_request,
            plan_generation_readiness=readiness_api,
        )
        review_api = review.as_api_dict()
        review_api["plan_generation_readiness"] = readiness_api
        section = pre_generation_runner_review_system_section(review_api)
        return (section, review_api)
    except Exception:
        logger.warning(
            "[smartcoach_mobile_coach] pre_generation_runner_review_bundle_failed",
            exc_info=True,
        )
        return ("", None)


def _plan_creation_minimal_system_content(
    *,
    plan_intake_ctx: Optional[Dict[str, Any]],
    anchor_local_date: str,
    client_timezone: Optional[str],
    activity_ctx_block: str,
    response_directive: ResponseDirective,
    user_message: str,
    thread_ctx: Any,
    pre_generation_review_section: str = "",
) -> str:
    """Minimal plan-creation system prompt (same sections as the pre-loop build)."""
    return _join_nonempty_system_sections(
        PLAN_CREATION_SYSTEM_PROMPT_BASE,
        _structured_intake_core_v1_plan_creation_addon(),
        _plan_intake_phase_system_section(plan_intake_ctx),
        _device_anchor_system_section(anchor_local_date, client_timezone),
        activity_ctx_block,
        pre_generation_review_section,
        alignment_pause_coaching_facts_system_section(plan_intake_ctx),
        schedule_confirmation_system_section(plan_intake_ctx),
        _plan_creation_directive_stub(response_directive),
        _plan_creation_system_section(
            user_message,
            response_directive.intent,
            thread_ctx,
        ),
    )


def _eager_merge_plan_intake_user_turn(
    session: Session,
    internal_user_id: str,
    *,
    thread_ctx: DerivedThreadCoachContext,
    user_message: str,
) -> DerivedThreadCoachContext:
    """Merge the current user line into deterministic intake before prompts and tools.

    Thread-derived context only reflects **prior** assistant JSON, so without this
    the model can see stale ``missing_required`` and repeat questions the user
    already answered in the **current** message.
    """
    prior = getattr(thread_ctx, "latest_plan_intake_state", None)
    if not isinstance(prior, dict) or not (user_message or "").strip():
        return thread_ctx
    try:
        out = tool_update_plan_intake(
            session,
            str(internal_user_id),
            {"updates": {}},
            current_state=prior,
            source_user_message=(user_message or "").strip(),
        )
        merged = out.get("plan_intake_state")
        if isinstance(merged, dict):
            return replace(thread_ctx, latest_plan_intake_state=merged)
    except Exception:
        logger.warning(
            "[smartcoach_mobile_coach] plan_intake_eager_merge_failed",
            exc_info=True,
        )
    return thread_ctx


def _natural_plan_intake_fallback_question(intake_state: Dict[str, Any]) -> str:
    """User-facing fallback when the model/tool loop returns plan state but no prose."""
    ux_fb = intake_state.get("ux") if isinstance(intake_state.get("ux"), dict) else {}
    phase_fb = str(ux_fb.get("plan_creation_phase") or "")
    if (
        phase_fb == "collecting_goal_adjustment"
        or ux_fb.get("runner_goal_edit_pending")
        or ux_fb.get("runner_tradeoff_edit_focus") == "goal"
    ):
        return "Got it. What goal do you want to use for this race instead?"
    alignment = intake_state.get("alignment")
    if isinstance(alignment, dict):
        st = alignment.get("state")
        if (
            isinstance(st, dict)
            and st.get("pause_required")
            and not st.get("generation_ready")
        ):
            allowed = st.get("allowed_question_categories") or []
            first = (
                allowed[0]
                if isinstance(allowed, list) and allowed and isinstance(allowed[0], str)
                else ""
            )
            if first == "frequency_flexibility":
                return (
                    "Before we generate your plan, use the options below to tell me how flexible "
                    "you can be with your weekly running structure for this goal."
                )
            if first == "timeline_flexibility":
                return "If needed, are you open to slightly adjusting timeline expectations?"
            return "What feels most adjustable for you right now?"

    if intake_state.get("ready_to_generate"):
        summ = (intake_state.get("confirmation_summary") or "").strip()
        if summ:
            return f"Here’s what I have: {summ} Does that look right?"
        return "I have enough to build the plan. Does that look right?"

    missing = intake_state.get("missing_required") or []
    first = missing[0] if missing and isinstance(missing[0], str) else ""
    if first == "race_distance":
        return "What are you training for — a half marathon or a marathon?"
    if first == "race_date":
        return "Do you already have a race date in mind?"
    if first == "primary_goal":
        return "Is the goal to finish strong, or are you targeting a specific time?"
    if first == "target_time":
        return "What finish time are you aiming for?"
    if first == "training_days":
        ux = intake_state.get("ux") if isinstance(intake_state.get("ux"), dict) else {}
        if ux.get("training_days_count"):
            return "Which days of the week work best for you?"
        return "How many days per week do you want to run, and which days usually work best?"
    return "Tell me a bit more about the race you want to train for."


def _ui_prompt_from_plan_intake_state(
    intake_state: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    return compute_plan_creation_ui(intake_state)


def _structured_intake_core_v1_plan_creation_addon() -> str:
    if not structured_intake_core_v1_enabled():
        return ""
    return (
        "## Structured intake (core athletic fields)\n"
        "- **Authoritative state:** `race_distance`, `race_date`, `primary_goal`, `target_time`, and "
        "`training_days` are committed via **mobile inline controls** + `structured_input` / tools. "
        "**Treat the latest tool `plan_intake_state.draft` as the only source of truth** for those fields.\n"
        "- **Do not** tell the athlete a core detail is saved unless it appears in that draft after the latest merge.\n"
        "- Prefer **not** passing those five keys in `update_plan_intake` `updates` from model inference; use "
        "optional fields (`race_name`, `race_location`, `notes`, `long_run_day`, …) there when helpful.\n"
        "- Your role for core slots: **coach copy, pacing, and explanation**—not silent extraction into those "
        "five keys.\n"
    ).strip()


# Premature “wrap up / confirm / generate” language while still in COLLECTING.
_PLAN_INTAKE_PREMATURE_CONFIRM_RE = re.compile(
    r"(?is)"
    r"(does\s+that\s+(all\s+)?look\s+right|"
    r"do\s+those\s+details\s+look|"
    r"sound(s)?\s+good\s+to\s+(you|go)|"
    r"ready\s+to\s+(generate|create)|"
    r"go\s+ahead\s+and\s+(create|generate)|"
    r"shall\s+i\s+(create|generate)|"
    r"does\s+everything\s+look|"
    r"look\s+right\s+to\s+you|"
    r"create\s+(your|this)\s+plan\s+now|"
    r"generate\s+(your|this)\s+plan)"
)


_PLAN_CREATION_FILLER_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*great[!.]?\s*", re.IGNORECASE),
    re.compile(
        r"^\s*i(?:'|’|\?)m here to help(?: you)?(?: with that)?[!.]?\s*",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*i can help(?: you)?(?: with that)?[!.]?\s*", re.IGNORECASE),
    re.compile(r"^\s*happy to help[!.]?\s*", re.IGNORECASE),
    re.compile(
        r"^\s*let(?:'|’|\?)s get started(?: on your training plan)?[!.]?\s*",
        re.IGNORECASE,
    ),
)


def _split_plan_creation_sentences(text: str) -> List[str]:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if not normalized:
        return []
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", normalized) if s.strip()]


def _strip_plan_creation_filler_sentence(sentence: str) -> str:
    out = sentence.strip()
    changed = True
    while changed:
        changed = False
        for pat in _PLAN_CREATION_FILLER_PATTERNS:
            new_out = pat.sub("", out).strip()
            if new_out != out:
                out = new_out
                changed = True
    return out


def _plan_intake_runner_analysis_relaxed_prose(
    intake_state: Optional[Dict[str, Any]],
) -> bool:
    """
    When True, skip the 4-sentence cap: Runner Analysis facts render in the app;
    model may add only brief warmth.
    """
    if not isinstance(intake_state, dict):
        return False
    if not intake_state.get("ready_to_generate"):
        return False
    if not plan_creation_split_confirm_enabled():
        return False
    ux = intake_state.get("ux") if isinstance(intake_state.get("ux"), dict) else {}
    if not ux.get("intake_confirmed"):
        return False
    if not ux.get("runner_review_delivered"):
        return True
    phase = str(ux.get("plan_creation_phase") or "")
    if phase == PHASE_AWAITING_TRADEOFF_CHOICE or ux.get("runner_tradeoff_pending"):
        return True
    return False


def _enforce_plan_creation_response_guardrails(
    text: str,
    *,
    plan_intake_state: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Lightweight UX guardrail for intake replies: no filler, <=4 sentences, one question.

    Runs on **model-authored text only** — callers apply deterministic preambles *after*
    this step so activity-overview paragraphs are not counted toward the sentence cap.

    Alignment pause turns may need an extra sentence (interpretation + choices + rationale + question);
    those allow five sentences.

    Runner Analysis / inline chip turns skip the sentence cap — structured facts render in the client.

    When still collecting (``ready_to_generate`` false), strip premature full-plan
    confirmation / generate language and fall back to the next deterministic question.
    """
    if not (text or "").strip():
        return text

    out = (text or "").strip()
    out = re.sub(r"(?m)^\s*\d+\.\s*", "", out).strip()
    if isinstance(plan_intake_state, dict) and not plan_intake_state.get(
        "ready_to_generate"
    ):
        if _PLAN_INTAKE_PREMATURE_CONFIRM_RE.search(out):
            return _natural_plan_intake_fallback_question(plan_intake_state)

    if _plan_intake_runner_analysis_relaxed_prose(plan_intake_state):
        return out

    max_kept = 5 if plan_intake_alignment_pause_active(plan_intake_state) else 4

    kept: List[str] = []
    question_seen = False
    for raw_sentence in _split_plan_creation_sentences(text):
        sentence = _strip_plan_creation_filler_sentence(raw_sentence)
        if not sentence:
            continue
        if sentence.rstrip().endswith("?"):
            if question_seen:
                continue
            question_seen = True
        kept.append(sentence)
        if len(kept) >= max_kept:
            break
    out = "\n".join(kept).strip() or (text or "").strip()
    out = re.sub(r"(?m)^\s*\d+\.\s*", "", out).strip()
    if isinstance(plan_intake_state, dict) and not plan_intake_state.get(
        "ready_to_generate"
    ):
        if _PLAN_INTAKE_PREMATURE_CONFIRM_RE.search(out):
            return _natural_plan_intake_fallback_question(plan_intake_state)
    return out


def _device_anchor_system_section(
    anchor_local_date: str, client_timezone: Optional[str]
) -> str:
    tz_display = (client_timezone or "").strip() or "unknown"
    return (
        f'## Device context (authoritative calendar "today")\n'
        f"- The user's local calendar date on their phone right now is **{anchor_local_date}** (IANA timezone: {tz_display}).\n"
        f"- **Vague single-run recap** (e.g. **how was my run**, **how was my last run**, **my run**) with **no** **`today`** in the message — and **not** clearly continuing a **different** run you already named in the **prior assistant** message — is the **most recent run in the DB**: call **`search_runs`** with **`limit=1`** (newest first), then **`get_run_summary`**. **Do not** call **`find_runs_by_date`** with **{anchor_local_date}** for that opening.\n"
        f"- **Explicit today:** when the message contains **`today`** (case-insensitive) and they mean this calendar day’s run, call **`find_runs_by_date`** with `local_date` exactly **{anchor_local_date}** (then **`get_run_summary`** as needed). Same split as run-recap fastpath.\n"
        f'- If they **just** asked about a **past** run you identified by **name/date** and now say **"how did I do?"** / **"how was it?"** / **"this run"** / similar, **do not** default to **{anchor_local_date}** — resolve via **`find_runs_by_date`** on the **date from your prior reply** or **`search_runs`** again, then **`get_run_summary`**.\n'
        f"- Use another `local_date` when the user clearly refers to that day (yesterday, weekday, YYYY-MM-DD, etc.), or follow thread-continuation rules.\n"
        f"- Never ask the user to specify the date for vague recap openings; use **`search_runs`** (**most recent**) unless **today** is explicit, then use **{anchor_local_date}**."
    )


def _plan_creation_system_section(
    user_message: str,
    intent: str,
    thread_ctx: Any,
) -> str:
    msg = (user_message or "").lower()
    intake_state = (
        thread_ctx.latest_plan_intake_state
        if hasattr(thread_ctx, "latest_plan_intake_state")
        else None
    )
    active = (
        intent == INTENT_PLAN_CREATION
        or isinstance(intake_state, dict)
        or any(
            k in msg
            for k in (
                "create a plan",
                "build a plan",
                "training plan",
                "plan for",
                "help me train",
                "make me a plan",
            )
        )
    )
    if not active:
        return ""

    lines = [
        "## Plan creation flow (deterministic intake + deterministic generation)",
        "- When this turn is about creating/updating a plan, always use tool `update_plan_intake` to capture the latest user details.",
        "- **While `missing_required` is non-empty:** call `update_plan_intake` with `updates` derived from the user's last message **before** your final reply — do not send only prose (minimal prompt relies on tools for truth).",
    ]
    if isinstance(intake_state, dict):
        draft = intake_state.get("draft") or {}
        rd = draft.get("race_date") if isinstance(draft, dict) else None
        if isinstance(rd, str) and rd.strip():
            lines.append(
                "- **`race_date` is already in intake** — do **not** ask how many weeks or months to train; "
                "plan length is fixed from that date. Ask only the next `missing_required` field."
            )
    lines.extend(
        [
            "- Ask exactly one question per turn when a question is needed. Use server order internally: race_distance, "
            "race_date, primary_goal (Just Finish | Target Time only), training_days, then target_time when goal is Target Time.",
            "- If the user names a full marathon (e.g. Chicago Marathon) or clearly means 26.2, pass `race_distance` "
            "(Marathon) and `race_name` in `update_plan_intake` the same turn—do not ask half vs full again.",
            "- Do not ask experience level, how many weeks/months the plan should run, or how long they want to train; "
            "plan length is **only** from race date + server rules. **Forbidden:** “How many weeks would you like…?” — never ask that. "
            "If `race_date` is already in intake, the next question must be the next `missing_required` field only (not duration). "
            "Non-supported race distances: plan generation supports Half Marathon and Marathon only.",
            "- Do not claim details are saved unless `update_plan_intake` confirms them.",
            "- Do not ask final yes/no to generate until `ready_to_generate=true` (a days-per-week count is not enough—"
            "concrete weekdays must be in intake first).",
            "- When `ready_to_generate=true`, present a simple confirmation summary and ask for explicit yes/no.",
            "- Call `generate_training_plan` only after explicit confirmation, with `confirm=true`.",
            "- Keep user-facing wording natural; never show tool names, field keys, `missing_required`, or `ready_to_generate` to the user.",
        ],
    )
    if isinstance(intake_state, dict):
        lines.extend(
            [
                "- Current deterministic intake state (from prior turn payload):",
                "```json",
                json.dumps(
                    {
                        "status": intake_state.get("status"),
                        "missing_required": intake_state.get("missing_required"),
                        "ready_to_generate": intake_state.get("ready_to_generate"),
                        "confirmation_summary": intake_state.get(
                            "confirmation_summary"
                        ),
                    },
                    default=str,
                ),
                "```",
            ]
        )
    return "\n".join(lines)


def build_deterministic_plan_intake_chip_assistant_payload(
    session: Session,
    internal_user_id: str,
    *,
    plan_intake_state: Dict[str, Any],
    anchor_local_date: str,
    activity_summary: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build the same structured assistant JSON shape as the tool loop’s text-plan-data path,
    without calling OpenAI. Used when the mobile client sends ``structured_input_only`` with
    ``structured_input`` so chip taps stay on the deterministic intake state machine.
    """
    pis_merged: Dict[str, Any] = dict(plan_intake_state)
    out_text = _natural_plan_intake_fallback_question(pis_merged)
    out_text = _enforce_plan_creation_response_guardrails(
        out_text,
        plan_intake_state=pis_merged,
    )
    runner_understanding_shown = plan_runner_understanding_shown(pis_merged)
    out_text_with_preamble = apply_plan_activity_preamble_to_assistant_markdown(
        out_text,
        plan_creation_mode=True,
        activity_summary=activity_summary,
        runner_understanding_already_shown=runner_understanding_shown,
    )
    if out_text_with_preamble != out_text:
        pis_merged = mark_plan_runner_understanding_shown(pis_merged)
    out_text = out_text_with_preamble

    structured_text: Dict[str, Any] = {
        "type": "text",
        "content": out_text,
        "data": {},
    }
    pis_for_client = dict(pis_merged)
    _, runner_review_api = _try_build_runner_review_bundle(
        session,
        str(internal_user_id),
        pis_for_client,
        anchor_local_date=anchor_local_date,
    )
    if runner_review_api is not None:
        structured_text["data"]["pre_generation_runner_review"] = runner_review_api
    if plan_creation_split_confirm_enabled() and pis_for_client.get(
        "ready_to_generate"
    ):
        apply_review_to_plan_intake_ux_for_phase(
            pis_for_client,
            runner_review_api,
            intake_confirmed=bool(
                (
                    pis_for_client.get("ux")
                    if isinstance(pis_for_client.get("ux"), dict)
                    else {}
                ).get("intake_confirmed")
            ),
        )
    structured_text["data"]["plan_intake_state"] = pis_for_client
    ui_prompt = _ui_prompt_from_plan_intake_state(pis_for_client)
    if isinstance(ui_prompt, dict):
        structured_text["data"]["ui_prompt"] = ui_prompt
    return structured_text

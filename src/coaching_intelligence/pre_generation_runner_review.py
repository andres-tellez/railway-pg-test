"""
Pre-generation runner review (v1) — thin narrative + routing hints for coach chat.

Built from ``pre_generation_runner_assessment`` (API dict), ``plan_request``, and
**``plan_generation_readiness``** (Wave 2+). Assessment status and user-facing
routing align exclusively with ``evaluate_plan_generation_readiness``; this module
does not run parallel goal-realism or ambition-based routing rules.

See docs/coaching-intelligence/PRE_GENERATION_RUNNER_REVIEW_V1.md for semantics,
limitations, and v2 backlog.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from src.coaching_intelligence.plan_generation_readiness import (
    evaluate_plan_generation_readiness,
)

SCHEMA_VERSION = "pre_generation_runner_review.v1"

STATUS_READY = "ready_to_generate"
STATUS_NEEDS_DECISION = "needs_user_decision"
STATUS_NEEDS_INFO = "needs_more_info"


def assessment_status_from_readiness(readiness_api: Dict[str, Any]) -> str:
    """
    Map ``plan_generation_readiness`` payload to runner-review ``assessment_status``.

    Single source of truth with orchestrator and plan-generation tool gating.
    """
    decision = str(readiness_api.get("decision") or "").strip()
    readiness_level = str(readiness_api.get("readiness_level") or "").strip()
    required_changes = {
        str(change)
        for change in list(readiness_api.get("required_changes") or [])
        if str(change).strip()
    }
    if decision == "allow":
        return STATUS_READY
    if (
        readiness_level == "insufficient_data"
        and "complete_alignment_questions" in required_changes
    ):
        return STATUS_NEEDS_INFO
    return STATUS_NEEDS_DECISION


def _reason_codes(plan_generation_readiness: Dict[str, Any]) -> Set[str]:
    return {
        str(c).strip()
        for c in list(plan_generation_readiness.get("reason_codes") or [])
        if str(c).strip()
    }


def runner_review_feature_enabled() -> bool:
    raw = (
        (os.getenv("SMARTCOACH_PRE_GENERATION_RUNNER_REVIEW_V1") or "1").strip().lower()
    )
    return raw not in ("0", "false", "no", "off")


def classify_assessment_status_v1(
    *,
    assessment_api: Dict[str, Any],
    plan_request: Dict[str, Any],
    plan_generation_readiness: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Runner-review status from ``plan_generation_readiness`` only.

    When ``plan_generation_readiness`` is omitted, it is computed via
    ``evaluate_plan_generation_readiness`` (same inputs as production).
    """
    readiness = plan_generation_readiness
    if readiness is None:
        readiness = evaluate_plan_generation_readiness(
            plan_request=plan_request,
            assessment_api=assessment_api,
        )
    return assessment_status_from_readiness(readiness)


def _allowed_actions_for_status(status: str) -> List[str]:
    if status == STATUS_NEEDS_INFO:
        return ["provide_alignment_answers", "adjust_intake_via_update_plan_intake"]
    if status == STATUS_NEEDS_DECISION:
        return [
            "expand_running_days",
            "adjust_goal",
            "adjust_timeline",
            "continue_tradeoff",
        ]
    return ["confirm_generate_when_ready"]


def _copy_lines_for_v1(
    *,
    status: str,
    assessment_api: Dict[str, Any],
    plan_request: Dict[str, Any],
    plan_generation_readiness: Dict[str, Any],
) -> tuple[List[str], List[str], str]:
    """summary_lines, concerns, recommended_next_step — driven by readiness reason_codes."""
    act = assessment_api.get("activity_summary") or {}
    ag = (
        assessment_api.get("ambition_gap")
        if isinstance(assessment_api.get("ambition_gap"), dict)
        else {}
    )
    ial = (
        assessment_api.get("intake_alignment_state")
        if isinstance(assessment_api.get("intake_alignment_state"), dict)
        else {}
    )
    rc = _reason_codes(plan_generation_readiness)
    activities_found = int(act.get("activities_found") or 0)
    avg_mi = float(act.get("avg_miles_per_week_approx") or 0.0)
    stance = str(ag.get("stance") or "")
    primary_goal = str(plan_request.get("primary_goal") or "")

    summary_lines: List[str] = []
    concerns: List[str] = []
    nxt = ""

    if status == STATUS_NEEDS_INFO:
        unresolved = [str(x) for x in list(ial.get("unresolved_flags") or []) if x]
        if unresolved:
            summary_lines.append(
                "Alignment needs one more structured answer before generation "
                f"(topics: {', '.join(unresolved)})."
            )
        elif "RULE_INSUFFICIENT_GOAL_CONTEXT" in rc:
            summary_lines.append(
                "Goal context is incomplete relative to the stated training intent."
            )
        concerns.append("Required intake or alignment information is still missing.")
        nxt = (
            "Ask for the missing alignment or intake detail, then re-run assessment "
            "before generating."
        )

    elif status == STATUS_NEEDS_DECISION:
        sub3_run_day_risk = rc & {
            "RULE_SUB3_THREE_DAYS_HIGH_RISK",
            "RULE_SUB3_FOUR_DAYS_WEAK_BASELINE",
        }
        perf_risk = rc & {
            "RULE_PERFORMANCE_LARGE_GAP_EASY_VS_GOAL_PACE",
            "RULE_PERFORMANCE_NO_SUSTAINED_PACE_NEAR_GOAL",
        }
        if sub3_run_day_risk:
            tt = str(plan_request.get("target_time") or "").strip() or "this"
            n_run = len(plan_request.get("training_days") or [])
            summary_lines.append(
                f"A **{tt}** marathon goal with only **{n_run}** running day(s) per week is very ambitious."
            )
            summary_lines.append(
                "Most runners targeting this kind of time train more often to build weekly mileage "
                "and the endurance a fast marathon requires."
            )
            concerns.append(
                "With only a few run days each week, hitting weekly volume for this goal will be harder "
                "than on a busier schedule—worth deciding how you want to approach it before we build the plan."
            )
            nxt = (
                "2–4 short sentences: lead with goal + run days, then why it matters in plain running terms. "
                "End with: you can pick an option below (or change details in chat). "
                "Do not offer **Create my plan** until they choose. "
                "Avoid the words: tradeoff, path, tension, commitment, coherence."
            )
        elif "RULE_ACTIVITIES_FOUND_ZERO" in rc:
            summary_lines.append(
                "No recent running activities were found in the lookback window—"
                "baseline signals are thin."
            )
            concerns.append(
                "Proceeding will rely heavily on intake answers rather than logged volume."
            )
            nxt = (
                "Say we have little recent run data to size the plan; keep it short. "
                "They can still pick an option or adjust intake. "
                "Avoid: tradeoff, path, tension, commitment, coherence."
            )
        elif "RULE_INSUFFICIENT_GOAL_CONTEXT" in rc:
            summary_lines.append(
                "Goal context is incomplete relative to the stated training intent."
            )
            concerns.append(
                "Clarify the goal or key intake details so recommendations stay grounded."
            )
            nxt = (
                "Ask a short clarifying question; keep tone supportive. "
                "Avoid: tradeoff, path, tension, commitment, coherence."
            )
        elif "RULE_TENSION_AFTER_ALIGNMENT" in rc:
            summary_lines.append(
                f"Stated goal and recent volume read as **{stance.replace('_', ' ').lower()}** "
                f"(baseline band: {ag.get('baseline_band')})."
                if stance
                else "Stated goal and recent volume look misaligned for a comfortable build."
            )
            concerns.append(
                "The goal and recent weekly mileage don’t line up neatly—you’ll want to adjust expectations "
                "or training volume before locking in a plan."
            )
            nxt = (
                "Explain mismatch in simple terms; point them to the options or intake edits. "
                "Avoid: tradeoff, path, tension, commitment, coherence."
            )
        elif rc & {
            "RULE_MARATHON_TIME_TARGET_THIN_BASELINE",
            "RULE_SUB3_BASELINE_NOT_ESTABLISHED",
            "RULE_SUB3_VERY_LOW_MILEAGE_AND_SHORT_LONG_RUN",
        }:
            summary_lines.append(
                f"Recent weekly mileage (~{avg_mi:.1f} mi/wk) is thin relative to goal demand."
            )
            concerns.append(
                "Building safely toward an aggressive goal usually needs more steady weekly volume "
                "than we’re seeing in the window."
            )
            nxt = (
                "Name the gap briefly; suggest options below or adjusting goal/days. "
                "Avoid: tradeoff, path, tension, commitment, coherence."
            )
        elif rc & {
            "RULE_SUB3_SHORT_TIMELINE",
            "RULE_MARATHON_TIME_TARGET_SHORT_TIMELINE",
            "RULE_COMPLETION_MARATHON_SHORT_RAMP",
            "RULE_COMPLETION_MARATHON_TIMELINE_CRITICAL",
        }:
            summary_lines.append(
                "Timeline to race looks tight relative to the goal and recent training signals."
            )
            concerns.append(
                "You may need more runway, a softer goal, or a heavier training focus than the calendar allows."
            )
            nxt = (
                "Explain the time constraint briefly; offer timeline or goal adjustments. "
                "Avoid: tradeoff, path, tension, commitment, coherence."
            )
        elif perf_risk:
            summary_lines.append(
                "Recent easy and sustained paces look far from marathon goal pace for this target."
            )
            concerns.append(
                "Closing that gap safely usually takes time and different training emphasis than a short ramp."
            )
            nxt = (
                "Keep it factual and short; steer toward goal adjustment or building base first. "
                "Avoid: tradeoff, path, tension, commitment, coherence."
            )
        else:
            summary_lines.append(
                "Goal and recent signals suggest pausing for a clear choice before generating."
            )
            concerns.append(
                "Either tweak goal or schedule, or confirm you’re okay proceeding as entered."
            )
            nxt = (
                "Keep it direct and short; use chips or chat to resolve—no vague asks to “accept” anything. "
                "Avoid: tradeoff, path, tension, commitment, coherence."
            )

    else:
        summary_lines.append(
            f"Goal **{primary_goal}** with recent training context (~{avg_mi:.1f} mi/wk avg in window)."
        )
        summary_lines.append(
            "Training story and goal look workable enough to move ahead if the athlete confirms."
        )
        nxt = (
            "Offer a short recap (race, goal, schedule) and ask for explicit confirmation "
            "before calling generate_training_plan."
        )

    summary_lines = summary_lines[:4]
    concerns = concerns[:2]
    return summary_lines, concerns, nxt


@dataclass(frozen=True)
class PreGenerationRunnerReviewV1:
    schema_version: str
    computed_at: str
    assessment_status: str
    summary_lines: List[str]
    concerns: List[str]
    recommended_next_step: str
    allowed_user_actions: List[str]

    def as_api_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "computed_at": self.computed_at,
            "assessment_status": self.assessment_status,
            "summary_lines": list(self.summary_lines),
            "concerns": list(self.concerns),
            "recommended_next_step": self.recommended_next_step,
            "allowed_user_actions": list(self.allowed_user_actions),
        }


def build_pre_generation_runner_review_v1(
    *,
    assessment_api: Dict[str, Any],
    plan_request: Dict[str, Any],
    plan_generation_readiness: Optional[Dict[str, Any]] = None,
) -> PreGenerationRunnerReviewV1:
    """Deterministic review brief; status mirrors ``plan_generation_readiness``."""
    readiness = plan_generation_readiness
    if readiness is None:
        readiness = evaluate_plan_generation_readiness(
            plan_request=plan_request,
            assessment_api=assessment_api,
        )
    status = assessment_status_from_readiness(readiness)
    summary_lines, concerns, nxt = _copy_lines_for_v1(
        status=status,
        assessment_api=assessment_api,
        plan_request=plan_request,
        plan_generation_readiness=readiness,
    )
    return PreGenerationRunnerReviewV1(
        schema_version=SCHEMA_VERSION,
        computed_at=datetime.now(timezone.utc).isoformat(),
        assessment_status=status,
        summary_lines=summary_lines,
        concerns=concerns,
        recommended_next_step=nxt,
        allowed_user_actions=_allowed_actions_for_status(status),
    )


def pre_generation_runner_review_system_section(review_api: Dict[str, Any]) -> str:
    """Orchestrator system-section text: instruct LLM to ground prose in review only."""
    if not isinstance(review_api, dict) or not review_api:
        return ""
    status = str(review_api.get("assessment_status") or "")
    lines = [
        str(x) for x in list(review_api.get("summary_lines") or []) if str(x).strip()
    ]
    concerns = [
        str(x) for x in list(review_api.get("concerns") or []) if str(x).strip()
    ]
    nxt = str(review_api.get("recommended_next_step") or "").strip()
    readiness = (
        review_api.get("plan_generation_readiness")
        if isinstance(review_api.get("plan_generation_readiness"), dict)
        else {}
    )
    bullets = "\n".join(f"- {s}" for s in lines[:4])
    concern_blk = "\n".join(f"- {c}" for c in concerns[:2])
    parts = [
        "## Pre-generation runner review (v1 — narrative hints; UI is authoritative)",
        f"- **assessment_status:** `{status}`",
        "**Legacy summary_lines / concerns (optional tone only; if they conflict with `coach_analysis_for_llm`, ignore them):**",
        bullets,
    ]
    if concern_blk:
        parts.extend(["**Legacy concerns:**", concern_blk])
    if readiness:
        coach = readiness.get("coach_analysis_for_llm")
        coach = coach if isinstance(coach, dict) else {}
        if coach:
            parts.extend(
                [
                    "**coach_analysis_for_llm (AUTHORITATIVE — facts, concerns, path, actions; mobile renders this in Runner Analysis. Paraphrase only with empathy; never add facts or categories beyond it):**",
                    "```json",
                    json.dumps(coach, ensure_ascii=False, indent=2),
                    "```",
                ]
            )
        rp = readiness.get("recommended_path")
        rp = rp if isinstance(rp, dict) else {}
        parts.extend(
            [
                "**Plan generation readiness (deterministic; do not override):**",
                f"- goal_profile: `{readiness.get('goal_profile')}`",
                f"- decision: `{readiness.get('decision')}`",
                f"- readiness_level: `{readiness.get('readiness_level')}`",
                f"- allowed_user_actions: `{', '.join(str(x) for x in list(readiness.get('allowed_user_actions') or []))}`",
                f"- recommended_path: `{rp.get('type')}` — {rp.get('message') or ''}",
            ]
        )
        cats = readiness.get("category_assessments")
        if isinstance(cats, list) and cats:
            applicable_cats = [
                row
                for row in cats
                if isinstance(row, dict) and row.get("applies_to_goal") is True
            ]
            if applicable_cats:
                parts.append(
                    "**Category assessments (ok / warn / bad — applicable to this goal only; facts below supplement `coach_analysis_for_llm`):**"
                )
                for row in applicable_cats:
                    cid = row.get("category_id")
                    st = row.get("status")
                    rcs = row.get("reason_codes") or []
                    facts = row.get("facts_used")
                    if isinstance(facts, dict) and facts:
                        fk = ", ".join(
                            f"{k}={facts.get(k)}"
                            for k in sorted(facts.keys(), key=lambda x: str(x))[:10]
                        )
                    else:
                        fk = ""
                    rc_s = ", ".join(str(x) for x in rcs) if rcs else ""
                    line = f"- `{cid}`: **{st}**"
                    if rc_s:
                        line += f"; rules: {rc_s}"
                    if fk:
                        line += f"; facts: {fk}"
                    parts.append(line)
                parts.append(
                    "- No HR drift, Z2 pace, or other physiology unless a fact key above explicitly includes it in `facts_used`."
                )
    if nxt:
        parts.append(
            f"**Legacy recommended_next_step (optional; optional warmth only):** {nxt}"
        )
    parts.extend(
        [
            "- The **Runner Analysis card in the app** is built from `coach_analysis_for_llm`; do **not** "
            "recreate that content in long prose.",
            "- Optional only: up to **two short sentences** of warmth; same facts and actions as the card.",
            "- If `decision` is `defer` or `block`, do **not** imply the athlete is ready to generate a plan.",
            "- Do **not** invent numbers or labels not present in `coach_analysis_for_llm` or applicable category "
            "`facts_used` above.",
            "- In user-facing wording, avoid: **tradeoff**, **path**, **tension**, **commitment**, "
            "**coherence** (use plain running-coach language instead).",
        ]
    )
    return "\n".join(parts).strip()

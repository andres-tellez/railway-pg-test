"""
Pre-generation runner review (v1) — thin narrative + routing hints for coach chat.

Built **only** from ``pre_generation_runner_assessment`` (API dict) and
``plan_request``. No persistence, no weekly insights, no scoring engine.

See docs/coaching-intelligence/PRE_GENERATION_RUNNER_REVIEW_V1.md for semantics,
limitations, and v2 backlog.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

SCHEMA_VERSION = "pre_generation_runner_review.v1"

STATUS_READY = "ready_to_generate"
STATUS_NEEDS_DECISION = "needs_user_decision"
STATUS_NEEDS_INFO = "needs_more_info"


def runner_review_feature_enabled() -> bool:
    raw = (
        (os.getenv("SMARTCOACH_PRE_GENERATION_RUNNER_REVIEW_V1") or "1").strip().lower()
    )
    return raw not in ("0", "false", "no", "off")


def classify_assessment_status_v1(
    *,
    assessment_api: Dict[str, Any],
    plan_request: Dict[str, Any],
) -> str:
    """
    Map assessment + plan_request to exactly one of three statuses.

    Rules (v1):
    - needs_more_info: required alignment answers missing (unresolved_flags),
      or ambition reports insufficient goal context.
    - needs_user_decision: no recent activity (activities_found == 0), goal/volume
      tension (HIGH_TENSION / MANAGEABLE_TENSION), thin baseline signal from
      ambition_gap, thin volume for Target Time when alignment block omitted,
      or alignment not generation_ready without unresolved_flags (tradeoff path).

    **Important:** ``activities_found == 0`` maps to **needs_user_decision** (runner
    may still proceed on intake alone), **not** needs_more_info.
    """
    act = assessment_api.get("activity_summary") or {}
    activities_found = int(act.get("activities_found") or 0)
    ag = assessment_api.get("ambition_gap")
    ial = assessment_api.get("intake_alignment_state")

    if isinstance(ag, dict) and ag.get("stance") == "INSUFFICIENT_GOAL_CONTEXT":
        return STATUS_NEEDS_INFO

    if isinstance(ial, dict):
        unresolved = [str(x) for x in list(ial.get("unresolved_flags") or []) if x]
        if not ial.get("generation_ready") and unresolved:
            return STATUS_NEEDS_INFO
        if not ial.get("generation_ready"):
            return STATUS_NEEDS_DECISION

    if activities_found == 0:
        return STATUS_NEEDS_DECISION

    if isinstance(ag, dict):
        stance = str(ag.get("stance") or "")
        if stance in ("HIGH_TENSION", "MANAGEABLE_TENSION"):
            return STATUS_NEEDS_DECISION
        if ag.get("thin_baseline_data"):
            return STATUS_NEEDS_DECISION

    # Alignment off: approximate tension using plan goal + volume proxy only.
    if ag is None:
        pg = str(plan_request.get("primary_goal") or "").strip().lower()
        avg = float(act.get("avg_miles_per_week_approx") or 0.0)
        if pg == "target time" and avg < 15.0:
            return STATUS_NEEDS_DECISION

    return STATUS_READY


def _allowed_actions_for_status(status: str) -> List[str]:
    if status == STATUS_NEEDS_INFO:
        return ["provide_alignment_answers", "adjust_intake_via_update_plan_intake"]
    if status == STATUS_NEEDS_DECISION:
        return [
            "acknowledge_tradeoff_and_proceed",
            "adjust_goal_or_schedule_via_update_plan_intake",
            "confirm_generate_when_ready",
        ]
    return ["confirm_generate_when_ready"]


def _copy_lines_for_v1(
    *,
    status: str,
    assessment_api: Dict[str, Any],
    plan_request: Dict[str, Any],
) -> tuple[List[str], List[str], str]:
    """summary_lines, concerns, recommended_next_step."""
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
        elif ag.get("stance") == "INSUFFICIENT_GOAL_CONTEXT":
            summary_lines.append(
                "Goal context is incomplete relative to the stated training intent."
            )
        concerns.append("Required intake or alignment information is still missing.")
        nxt = (
            "Ask for the missing alignment or intake detail, then re-run assessment "
            "before generating."
        )

    elif status == STATUS_NEEDS_DECISION:
        if activities_found == 0:
            summary_lines.append(
                "No recent running activities were found in the lookback window—"
                "baseline signals are thin."
            )
            concerns.append(
                "Proceeding will rely heavily on intake answers rather than logged volume."
            )
        elif stance in ("HIGH_TENSION", "MANAGEABLE_TENSION"):
            summary_lines.append(
                f"Stated goal and recent volume read as **{stance.replace('_', ' ').lower()}** "
                f"(baseline band: {ag.get('baseline_band')})."
            )
            concerns.append(
                "There is a tradeoff between goal ambition and current training structure/volume."
            )
        elif ag.get("thin_baseline_data"):
            summary_lines.append(
                f"Recent weekly mileage (~{avg_mi:.1f} mi/wk) is thin relative to goal demand."
            )
            concerns.append("Volume signal may not match aggressive pace goals.")
        else:
            summary_lines.append(
                "Goal and baseline signals warrant an explicit athlete decision before generating."
            )
            concerns.append(
                "Acknowledge tradeoffs or adjust goal/schedule before proceeding."
            )
        nxt = (
            "Give a concise coach opinion on tradeoffs; ask the athlete to confirm they "
            "accept the path or adjust goal/days—then offer yes/no to generate when aligned."
        )

    else:
        summary_lines.append(
            f"Goal **{primary_goal}** with recent training context (~{avg_mi:.1f} mi/wk avg in window)."
        )
        summary_lines.append(
            "Signals are coherent enough to proceed if the athlete confirms."
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
) -> PreGenerationRunnerReviewV1:
    """Deterministic review brief from assessment snapshot + validated plan_request only."""
    status = classify_assessment_status_v1(
        assessment_api=assessment_api,
        plan_request=plan_request,
    )
    summary_lines, concerns, nxt = _copy_lines_for_v1(
        status=status,
        assessment_api=assessment_api,
        plan_request=plan_request,
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
    bullets = "\n".join(f"- {s}" for s in lines[:4])
    concern_blk = "\n".join(f"- {c}" for c in concerns[:2])
    parts = [
        "## Pre-generation runner review (v1 — ground coach opinion here)",
        f"- **assessment_status:** `{status}`",
        "**Summary (do not contradict; translate into natural coach language):**",
        bullets,
    ]
    if concern_blk:
        parts.extend(["**Concerns (address plainly):**", concern_blk])
    if nxt:
        parts.append(f"**Recommended next step for your prose:** {nxt}")
    parts.extend(
        [
            "- Write **one holistic assessment** before asking for final generate confirmation "
            "when appropriate.",
            "- Do **not** invent weekly mileage or stance labels not supported by tool/assessment data.",
        ]
    )
    return "\n".join(parts).strip()

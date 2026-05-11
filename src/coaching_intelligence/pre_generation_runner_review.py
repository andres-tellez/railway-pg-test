"""
Pre-generation runner review (v1) — thin narrative + routing hints for coach chat.

Built **only** from ``pre_generation_runner_assessment`` (API dict) and
``plan_request``. No persistence, no weekly insights, no scoring engine.

See docs/coaching-intelligence/PRE_GENERATION_RUNNER_REVIEW_V1.md for semantics,
limitations, and v2 backlog.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "pre_generation_runner_review.v1"

STATUS_READY = "ready_to_generate"
STATUS_NEEDS_DECISION = "needs_user_decision"
STATUS_NEEDS_INFO = "needs_more_info"

_SHORT_TIMELINE_WEEKS = 16


def _full_marathon_distance(plan_request: Dict[str, Any]) -> bool:
    rd = str(plan_request.get("race_distance") or "").strip().lower()
    if "half" in rd:
        return False
    return "marathon" in rd


def _parse_clock_seconds(tt: Optional[str]) -> Optional[float]:
    if not tt or not str(tt).strip():
        return None
    s = str(tt).strip()
    m = re.match(
        r"^\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*$",
        s,
    )
    if not m:
        return None
    try:
        if m.group(3) is not None:
            h = int(m.group(1))
            mn = int(m.group(2))
            sec = int(m.group(3))
            return h * 3600 + mn * 60 + sec
        mn = int(m.group(1))
        sec = int(m.group(2))
        return mn * 60 + sec
    except (TypeError, ValueError):
        return None


def _weeks_until_race(plan_request: Dict[str, Any]) -> Optional[float]:
    raw = plan_request.get("race_date")
    if raw is None:
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        d = raw
    elif isinstance(raw, datetime):
        d = raw.date()
    else:
        try:
            d = datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    today = date.today()
    if d <= today:
        return 0.0
    return (d - today).days / 7.0


def _marathon_fast_goal_three_or_fewer_run_days(plan_request: Dict[str, Any]) -> bool:
    """Same structural pairing as the first branch of `_thin_goal_realism_needs_user_decision`."""
    pg = str(plan_request.get("primary_goal") or "").strip().lower()
    if pg != "target time":
        return False
    secs = _parse_clock_seconds(str(plan_request.get("target_time") or ""))
    td = plan_request.get("training_days")
    n_days = len(td) if isinstance(td, list) else 0
    marathon = _full_marathon_distance(plan_request)
    sub_three = secs is not None and secs <= 3 * 3600
    return bool(marathon and sub_three and n_days <= 3)


def _thin_goal_realism_needs_user_decision(
    *,
    plan_request: Dict[str, Any],
    assessment_api: Dict[str, Any],
) -> bool:
    """Minimal deterministic checks — no scoring engine."""
    pg = str(plan_request.get("primary_goal") or "").strip().lower()
    if pg != "target time":
        return False
    secs = _parse_clock_seconds(str(plan_request.get("target_time") or ""))
    td = plan_request.get("training_days")
    n_days = len(td) if isinstance(td, list) else 0
    act = assessment_api.get("activity_summary") or {}
    ag = assessment_api.get("ambition_gap")
    agd = ag if isinstance(ag, dict) else {}

    marathon = _full_marathon_distance(plan_request)
    # Include exactly 3:00:00 as sub-3-level / very high demand for review routing.
    sub_three = secs is not None and secs <= 3 * 3600
    established = str(agd.get("baseline_band") or "") == "ESTABLISHED"
    goal_demand = str(agd.get("goal_demand") or "")
    baseline_band = str(agd.get("baseline_band") or "")

    if marathon and sub_three and n_days <= 3:
        return True
    if marathon and sub_three and n_days == 4 and not established:
        return True
    if marathon and goal_demand == "TIME_TARGET" and baseline_band == "THIN":
        return True
    wk = _weeks_until_race(plan_request)
    if (
        marathon
        and pg == "target time"
        and wk is not None
        and wk < _SHORT_TIMELINE_WEEKS
    ):
        return True
    return False


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

    if _thin_goal_realism_needs_user_decision(
        plan_request=plan_request,
        assessment_api=assessment_api,
    ):
        return STATUS_NEEDS_DECISION

    if isinstance(ial, dict) and not ial.get("generation_ready"):
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
        if _marathon_fast_goal_three_or_fewer_run_days(plan_request):
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
        elif activities_found == 0:
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
        elif stance in ("HIGH_TENSION", "MANAGEABLE_TENSION"):
            summary_lines.append(
                f"Stated goal and recent volume read as **{stance.replace('_', ' ').lower()}** "
                f"(baseline band: {ag.get('baseline_band')})."
            )
            concerns.append(
                "The goal and recent weekly mileage don’t line up neatly—you’ll want to adjust expectations "
                "or training volume before locking in a plan."
            )
            nxt = (
                "Explain mismatch in simple terms; point them to the options or intake edits. "
                "Avoid: tradeoff, path, tension, commitment, coherence."
            )
        elif ag.get("thin_baseline_data"):
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
    readiness = (
        review_api.get("plan_generation_readiness")
        if isinstance(review_api.get("plan_generation_readiness"), dict)
        else {}
    )
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
    if readiness:
        rp = readiness.get("recommended_path")
        rp = rp if isinstance(rp, dict) else {}
        parts.extend(
            [
                "**Plan generation readiness (deterministic; do not override):**",
                f"- decision: `{readiness.get('decision')}`",
                f"- readiness_level: `{readiness.get('readiness_level')}`",
                f"- allowed_user_actions: `{', '.join(str(x) for x in list(readiness.get('allowed_user_actions') or []))}`",
                f"- recommended_path: `{rp.get('type')}` — {rp.get('message') or ''}",
            ]
        )
    if nxt:
        parts.append(f"**Recommended next step for your prose:** {nxt}")
    parts.extend(
        [
            "- Write **one short assessment** before asking for final generate confirmation when appropriate.",
            "- The LLM may explain readiness in plain language, but must not override `decision` or offer actions absent from `allowed_user_actions`.",
            "- Do **not** invent weekly mileage or stance labels not supported by tool/assessment data.",
            "- In user-facing wording, avoid: **tradeoff**, **path**, **tension**, **commitment**, "
            "**coherence** (use plain running-coach language instead).",
        ]
    )
    return "\n".join(parts).strip()

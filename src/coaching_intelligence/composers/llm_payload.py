"""Deterministic coach/LLM analysis blob (Phase 5)."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from src.coaching_intelligence.readiness_constants import (
    CATEGORY_TRAINING_AVAILABILITY,
    STATUS_BAD,
    STATUS_WARN,
)
from src.coaching_intelligence.readiness_json import _json_safe_facts

COACH_ANALYSIS_FOR_LLM_SCHEMA = "coach_analysis_for_llm.v1.1"


def _main_concern_lines(
    plan_generation_readiness: Dict[str, Any],
    applicable_rows: List[Dict[str, Any]],
) -> List[str]:
    """Concern bullets from existing readiness only (no new policy)."""
    out: List[str] = []
    seen_lower: set[str] = set()

    def add(text: str) -> None:
        t = str(text).strip()
        if not t:
            return
        key = t.lower()
        if key in seen_lower:
            return
        seen_lower.add(key)
        out.append(t)

    for kf in plan_generation_readiness.get("key_findings") or []:
        add(str(kf))
    for lf in plan_generation_readiness.get("limiting_factors") or []:
        add(str(lf))
    for row in applicable_rows:
        st = str(row.get("status") or "")
        if st not in (STATUS_WARN, STATUS_BAD):
            continue
        cid = str(row.get("category_id") or "").replace("_", " ")
        codes = row.get("reason_codes") or []
        code_str = ", ".join(str(c) for c in codes if str(c).strip())
        line = f"{cid}: {st}"
        if code_str:
            line += f" ({code_str})"
        add(line)
    return out[:24]


def build_coach_analysis_for_llm(
    plan_generation_readiness: Dict[str, Any],
) -> Dict[str, Any]:
    """Deterministic UI + LLM-tone summary; derived only from readiness."""
    if not isinstance(plan_generation_readiness, dict):
        return {
            "schema_version": COACH_ANALYSIS_FOR_LLM_SCHEMA,
            "error": "invalid_readiness",
        }
    digest = plan_generation_readiness.get("inputs_digest") or {}
    rp_raw = plan_generation_readiness.get("recommended_path")
    rp = rp_raw if isinstance(rp_raw, dict) else {}
    decision = str(plan_generation_readiness.get("decision") or "").strip()
    goal_profile = str(plan_generation_readiness.get("goal_profile") or "").strip()

    facts_reviewed: List[Dict[str, str]] = []

    goal_parts: List[str] = []
    rd = digest.get("race_distance")
    if rd:
        goal_parts.append(str(rd))
    pg = digest.get("primary_goal")
    if pg:
        goal_parts.append(str(pg))
    tt = digest.get("target_time")
    if tt:
        goal_parts.append(f"target {tt}")
    if goal_parts:
        facts_reviewed.append({"label": "Goal", "value": " — ".join(goal_parts)})

    if goal_profile:
        facts_reviewed.append({"label": "Goal profile", "value": goal_profile})

    for row in plan_generation_readiness.get("category_assessments") or []:
        if row.get("category_id") != CATEGORY_TRAINING_AVAILABILITY:
            continue
        fu = row.get("facts_used") if isinstance(row.get("facts_used"), dict) else {}
        n = fu.get("training_day_count")
        days = fu.get("training_days")
        if n is not None or (isinstance(days, list) and len(days) > 0):
            parts: List[str] = []
            if n is not None:
                parts.append(f"{n} running day(s)/week")
            if isinstance(days, list) and days:
                day_names = [
                    str(d).strip().capitalize() for d in days if str(d).strip()
                ]
                if day_names:
                    parts.append(", ".join(day_names))
            if parts:
                facts_reviewed.append(
                    {"label": "Training schedule", "value": " — ".join(parts)}
                )
        break

    avg = digest.get("avg_miles_per_week_approx")
    if avg is None:
        avg = digest.get("avg_weekly_mileage_last_42d_mi")
    if avg is not None and str(avg).strip():
        facts_reviewed.append(
            {"label": "Recent mileage (approx)", "value": f"{avg} mi/week"}
        )

    longest = digest.get("longest_run_miles")
    if longest is None:
        longest = digest.get("longest_run_last_56d_mi")
    if longest is not None and str(longest).strip():
        facts_reviewed.append(
            {"label": "Longest recent run (approx)", "value": f"{longest} mi"}
        )

    weeks = digest.get("weeks_to_race")
    if weeks is not None and str(weeks).strip():
        facts_reviewed.append(
            {"label": "Timeline", "value": f"{weeks} week(s) to race"}
        )

    activities = digest.get("activities_found")
    if activities is None:
        activities = digest.get("activities_found_last_42d")
    lookback = digest.get("lookback_weeks")
    active = digest.get("active_weeks")
    ccw = digest.get("completed_calendar_weeks_count")
    coverage_bits: List[str] = []
    if activities is not None and str(activities).strip():
        coverage_bits.append(
            f"{activities} logged activities in sync lookback (coverage only, not fitness)"
        )
    if active is not None and lookback is not None and str(lookback).strip():
        coverage_bits.append(f"{active} active week(s) in ~{lookback} lookback week(s)")
    elif ccw is not None and str(ccw).strip():
        coverage_bits.append(f"{ccw} calendar week(s) with completed mileage data")
    if coverage_bits:
        facts_reviewed.append(
            {"label": "Data confidence (coverage)", "value": " — ".join(coverage_bits)}
        )

    applicable = [
        row
        for row in (plan_generation_readiness.get("category_assessments") or [])
        if isinstance(row, dict) and row.get("applies_to_goal") is True
    ]
    cat_lines: List[str] = []
    for row in applicable:
        cid = str(row.get("category_id") or "")
        status = str(row.get("status") or "")
        codes = row.get("reason_codes") or []
        code_str = ", ".join(str(c) for c in codes if str(c).strip())
        cat_lines.append(f"{cid}: {status}" + (f" ({code_str})" if code_str else ""))

    headline = str(rp.get("message") or "").strip()
    coach_read = headline
    if decision:
        coach_read = f"Decision: {decision}. {headline}".strip()

    rec_path_ui = _json_safe_facts(
        {
            "type": rp.get("type"),
            "message": rp.get("message"),
            "suggested_next_step": rp.get("suggested_next_step"),
        }
    )

    required_changes = [
        str(x)
        for x in (plan_generation_readiness.get("required_changes") or [])
        if str(x).strip()
    ]
    limiting_factors = [
        str(x)
        for x in (plan_generation_readiness.get("limiting_factors") or [])
        if str(x).strip()
    ]

    return {
        "schema_version": COACH_ANALYSIS_FOR_LLM_SCHEMA,
        "goal_profile": goal_profile,
        "decision": decision,
        "readiness_level": str(
            plan_generation_readiness.get("readiness_level") or ""
        ).strip(),
        "headline": headline,
        "coach_read": coach_read,
        "recommended_path": rec_path_ui,
        "required_changes": required_changes,
        "limiting_factors": limiting_factors,
        "key_findings": list(plan_generation_readiness.get("key_findings") or [])[:5],
        "main_concerns": _main_concern_lines(plan_generation_readiness, applicable),
        "facts_reviewed": facts_reviewed,
        "applicable_category_summaries": cat_lines[:24],
        "recommended_actions": list(
            plan_generation_readiness.get("allowed_user_actions") or []
        ),
        "enforcement_codes": list(plan_generation_readiness.get("reason_codes") or []),
    }

"""Post-generation payload and coach-brief formatting helpers."""

# pylint: disable=too-many-locals,too-many-branches,too-many-statements,missing-function-docstring,line-too-long,duplicate-code

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _ordinal_day(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _format_friendly_week_one_start(date_str: str) -> str:
    raw = str(date_str or "").strip()[:10]
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return raw
    weekdays = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    months = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
    return f"{weekdays[dt.weekday()]}., {months[dt.month - 1]} {_ordinal_day(dt.day)}"


def _format_weekday_only(date_str: str) -> str:
    raw = str(date_str or "").strip()[:10]
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return raw[:3] if len(raw) >= 3 else raw
    return ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[dt.weekday()]


def _phase_block_week_count(block: Dict[str, Any]) -> Optional[int]:
    sw = _safe_int(block.get("start_week"))
    ew = _safe_int(block.get("end_week"))
    if sw is not None and ew is not None:
        return max(1, ew - sw + 1)
    if sw is not None or ew is not None:
        return 1
    return None


def _extract_plan_weeks(validation_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    validated_plan = validation_result.get("validated_plan")
    if isinstance(validated_plan, dict) and isinstance(
        validated_plan.get("weeks"), list
    ):
        return [w for w in validated_plan.get("weeks", []) if isinstance(w, dict)]
    draft = validation_result.get("draft")
    if isinstance(draft, dict) and isinstance(draft.get("weeks"), list):
        return [w for w in draft.get("weeks", []) if isinstance(w, dict)]
    return []


def plan_overview_from_validation(
    validation_result: Dict[str, Any],
    plan_request: Dict[str, Any],
    saved_plan: Dict[str, Any],
) -> Dict[str, Any]:
    weeks = _extract_plan_weeks(validation_result)
    phase_sequence: List[str] = []
    phase_blocks: List[Dict[str, Any]] = []
    phase_idx: Dict[str, int] = {}
    peak_weekly_miles: Optional[float] = None
    peak_long_run_miles: Optional[float] = None

    for w in weeks:
        phase = str(w.get("phase") or "").strip()
        if phase and phase not in phase_sequence:
            phase_sequence.append(phase)
        week_num = _safe_int(w.get("week_number"))
        weekly = _safe_float(w.get("weekly_mileage"))
        if weekly is not None:
            peak_weekly_miles = (
                weekly if peak_weekly_miles is None else max(peak_weekly_miles, weekly)
            )
        if phase:
            if phase not in phase_idx:
                phase_idx[phase] = len(phase_blocks)
                phase_blocks.append(
                    {
                        "phase": phase,
                        "start_week": week_num,
                        "end_week": week_num,
                        "peak_weekly_miles": weekly,
                    }
                )
            else:
                block = phase_blocks[phase_idx[phase]]
                if week_num is not None:
                    start_week = _safe_int(block.get("start_week"))
                    end_week = _safe_int(block.get("end_week"))
                    if start_week is None or week_num < start_week:
                        block["start_week"] = week_num
                    if end_week is None or week_num > end_week:
                        block["end_week"] = week_num
                if weekly is not None:
                    prev_peak = _safe_float(block.get("peak_weekly_miles"))
                    block["peak_weekly_miles"] = (
                        weekly if prev_peak is None else max(prev_peak, weekly)
                    )
        long_run = _safe_float(w.get("long_run_miles"))
        if long_run is not None:
            peak_long_run_miles = (
                long_run
                if peak_long_run_miles is None
                else max(peak_long_run_miles, long_run)
            )

    start_date: Optional[str] = None
    validated_plan = validation_result.get("validated_plan")
    if isinstance(validated_plan, dict):
        raw = validated_plan.get("start_date")
        if isinstance(raw, str) and raw.strip():
            start_date = raw.strip()[:10]
    if not start_date:
        draft = validation_result.get("draft")
        if isinstance(draft, dict):
            raw = draft.get("start_date")
            if isinstance(raw, str) and raw.strip():
                start_date = raw.strip()[:10]
    if not start_date:
        workouts = saved_plan.get("workouts")
        if isinstance(workouts, list):
            dates = sorted(
                {
                    str(w.get("date"))[:10]
                    for w in workouts
                    if isinstance(w, dict) and str(w.get("date") or "").strip()
                }
            )
            if dates:
                start_date = dates[0]

    peak_week_number: Optional[int] = None
    for w in weeks:
        if isinstance(w, dict) and w.get("is_peak_week") is True:
            peak_week_number = _safe_int(w.get("week_number"))
            break

    return {
        "plan_start_date": start_date,
        "race_date": saved_plan.get("race_date"),
        "race_distance": saved_plan.get("race_distance"),
        "total_weeks": len(weeks) if weeks else None,
        "phase_sequence": phase_sequence,
        "peak_week_number": peak_week_number,
        "phase_intent_note": (
            "Phases reflect training intent: **Peak** is the last few pre-taper weeks at your "
            "highest long-run load (fixed block by plan length), not extra base-building."
        ),
        "phase_blocks": [
            {
                "phase": str(block.get("phase") or "").strip(),
                "start_week": _safe_int(block.get("start_week")),
                "end_week": _safe_int(block.get("end_week")),
                "peak_weekly_miles": (
                    round(float(block["peak_weekly_miles"]), 1)
                    if _safe_float(block.get("peak_weekly_miles")) is not None
                    else None
                ),
            }
            for block in phase_blocks
            if str(block.get("phase") or "").strip()
        ],
        "peak_weekly_miles": (
            round(float(peak_weekly_miles), 1)
            if peak_weekly_miles is not None
            else None
        ),
        "peak_long_run_miles": (
            round(float(peak_long_run_miles), 1)
            if peak_long_run_miles is not None
            else None
        ),
        "training_days": plan_request.get("training_days") or [],
        "long_run_day": plan_request.get("long_run_day"),
    }


def plan_baseline_from_validation(
    validation_result: Dict[str, Any], *, activity_weeks: int
) -> Dict[str, Any]:
    rationale = validation_result.get("pass1_rationale")
    if not isinstance(rationale, dict):
        rationale = {}
    base_mpw = _safe_float(rationale.get("base_mpw"))
    longest_recent = _safe_float(rationale.get("longest_recent"))
    start_lr = _safe_float(rationale.get("start_lr"))
    try:
        recommended_weeks = int(rationale.get("recommended_weeks"))
    except (TypeError, ValueError):
        recommended_weeks = None
    return {
        "source": "materialized_view",
        "lookback_weeks_requested": int(activity_weeks),
        "avg_weekly_miles": round(base_mpw, 1) if base_mpw is not None else None,
        "longest_recent_run_miles": (
            round(longest_recent, 1) if longest_recent is not None else None
        ),
        "starting_long_run_miles": round(start_lr, 1) if start_lr is not None else None,
        "recommended_weeks": recommended_weeks,
    }


def build_plan_generation_brief(
    race_distance: str,
    race_date: str,
    payload: Dict[str, Any],
) -> str:
    overview = payload.get("overview") if isinstance(payload, dict) else {}
    baseline = payload.get("baseline") if isinstance(payload, dict) else {}
    this_week = payload.get("this_week") if isinstance(payload, dict) else {}

    race_label = (race_distance or "race").strip() or "race"
    race_day = (race_date or "").strip() or "TBD"
    start_raw = (
        overview.get("plan_start_date") if isinstance(overview, dict) else None
    ) or "TBD"
    start_friendly = (
        _format_friendly_week_one_start(str(start_raw))
        if start_raw != "TBD" and len(str(start_raw).strip()) >= 10
        else str(start_raw)
    )
    lines: List[str] = [
        f"Your {race_label} plan is saved for {race_day}.",
        "",
        f"**Week 1 starts:** {start_friendly}",
    ]

    if isinstance(baseline, dict):
        avg_mpw = baseline.get("avg_weekly_miles")
        long_run = baseline.get("longest_recent_run_miles")
        lookback = baseline.get("lookback_weeks_requested")
        has_metrics = avg_mpw is not None or long_run is not None
        lines.append("")
        if has_metrics:
            if isinstance(lookback, int) and lookback > 0:
                lines.append(
                    f"To create the plan, I used your running data from the last **{lookback}** weeks."
                )
            else:
                lines.append(
                    "To create the plan, I used your recent running data from synced activities."
                )
            lines.append("")
            lines.append(
                f"- **Weekly miles:** {avg_mpw:.1f} mi/week"
                if avg_mpw is not None
                else "- **Weekly miles:** —"
            )
            lines.append(
                f"- **Longest run:** {long_run:.1f} mi"
                if long_run is not None
                else "- **Longest run:** —"
            )
        else:
            lines.append(
                "There wasn’t enough recent running history to personalize this plan from your "
                "mileage yet, so the schedule follows a solid built-in progression. "
                "Keep syncing runs so future plans can reflect your fitness."
            )

    if isinstance(overview, dict):
        total_weeks = overview.get("total_weeks")
        peak_lr = overview.get("peak_long_run_miles")
        phase_blocks = overview.get("phase_blocks")
        lines.append("")
        lines.append(
            f"**Plan overview** ({total_weeks} weeks)"
            if isinstance(total_weeks, int) and total_weeks > 0
            else "**Plan overview**"
        )
        if isinstance(phase_blocks, list) and phase_blocks:
            lines.extend(["", "| Phase | Weeks |", "| --- | --- |"])
            for block in phase_blocks:
                if not isinstance(block, dict):
                    continue
                phase_name = str(block.get("phase") or "").strip() or "Phase"
                week_count = _phase_block_week_count(block)
                week_label = str(week_count) if week_count is not None else "—"
                lines.append(f"| {phase_name} | {week_label} |")
        else:
            phase_sequence = overview.get("phase_sequence")
            if isinstance(phase_sequence, list):
                named = [str(p).strip() for p in phase_sequence if str(p).strip()]
                if named:
                    lines.extend(["", f"Phases: {' → '.join(named)}"])
        if peak_lr is not None:
            lines.append(f"- **Peak long run (plan):** {float(peak_lr):.1f} mi")
        pwn = overview.get("peak_week_number")
        if isinstance(pwn, int) and pwn > 0:
            lines.append(
                f"- **Peak long run week:** week {pwn} (highest planned long run before taper)."
            )
        pin = overview.get("phase_intent_note")
        if isinstance(pin, str) and pin.strip():
            lines.extend(["", pin.strip()])

    if isinstance(this_week, dict):
        workouts = this_week.get("workouts")
        if isinstance(workouts, list) and workouts:
            lines.extend(
                [
                    "",
                    "**Week 1 Preview**",
                    "",
                    "| Day | Run Type | Miles |",
                    "| --- | --- | --- |",
                ]
            )
            for w in workouts[:6]:
                if not isinstance(w, dict):
                    continue
                d = _format_weekday_only(str(w.get("date") or ""))
                wt_raw = str(w.get("workout_type") or "run").replace("_", " ").strip()
                wt = wt_raw.title() if wt_raw else "Run"
                miles = _safe_float(w.get("miles"))
                lines.append(
                    f"| {d} | {wt} | {miles:.1f} |"
                    if miles is not None
                    else f"| {d} | {wt} | — |"
                )
        else:
            lines.append(
                "Week-by-week workouts are ready in Plan. Open that tab for the full schedule."
            )

    lines.extend(
        [
            "",
            "**View your Plan:** click on Plan ![Plan tab](smartcoach-tab-icon://plan) to see full details and upcoming phases.",
            "",
            "**Questions** - Any questions?",
        ]
    )
    return "\n".join(lines)

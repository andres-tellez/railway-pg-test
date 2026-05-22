"""Deterministic split-table prose for splits-only turns."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.smartcoach_mobile_coach.coach_response.context import CoachRunContext


def _split_rows_from_context(ctx: CoachRunContext) -> List[Dict[str, Any]]:
    payload = ctx.splits
    if not isinstance(payload, dict):
        return []
    rows = payload.get("splits")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def render_deterministic_splits_block(ctx: CoachRunContext) -> Optional[str]:
    rows = _split_rows_from_context(ctx)
    if not rows:
        return None
    payload = ctx.splits if isinstance(ctx.splits, dict) else {}
    lines: List[str] = ["Here are your splits for the run:", ""]
    for index, row in enumerate(rows, start=1):
        label = str(row.get("segment_label") or "").strip()
        if not label:
            lap_index = row.get("lap_index")
            label = f"lap {lap_index}" if lap_index is not None else f"segment {index}"
        lines.append(f"{index}. {label}:")
        lines.append(f"   - **Distance:** {row.get('distance_display') or '—'}")
        lines.append(f"   - **Moving Time:** {row.get('moving_time_display') or '—'}")
        pace = row.get("avg_pace_display")
        if isinstance(pace, str) and pace.strip() and pace.strip() != "—":
            lines.append(f"   - **Average Pace:** {pace.strip()}")
        lines.append(
            f"   - **Average Heart Rate:** {row.get('avg_heart_rate_display') or '—'}"
        )
        lines.append("")
    truncated = bool(ctx.splits_truncated or payload.get("splits_truncated"))
    if truncated:
        total = int(payload.get("splits_total_count") or ctx.splits_count or len(rows))
        shown = len(rows)
        omitted = max(0, total - shown)
        lines.append(
            f"*Showing {shown} of {total} laps (first and last in lap order). "
            f"{omitted} middle lap(s) omitted from this list—do not infer their stats.*"
        )
        lines.append("")
    return "\n".join(lines).strip()


def compose_splits_turn_content(deterministic_block: str, coaching_prose: str) -> str:
    block = (deterministic_block or "").strip()
    coaching = (coaching_prose or "").strip()
    if not block:
        return coaching
    if not coaching:
        return block
    return f"{block}\n\n{coaching}"

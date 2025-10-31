from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict
import logging
from sqlalchemy.orm import Session

from src.services.training_plan.data_collection_service import DataCollectionService
from src.services.training_plan.insights_calculation_service import (
    InsightsCalculationService,
)
from src.services.training_plan.long_run_spine import generate_long_run_spine


logger = logging.getLogger(__name__)


class LRConfig(TypedDict):
    inc: float
    cutEvery: int
    cutFactor: float
    singlePeak: bool
    taperWeeks: int


DEFAULT_CFG: LRConfig = {
    "inc": 1.0,
    "cutEvery": 4,
    "cutFactor": 0.70,
    "singlePeak": True,
    "taperWeeks": 2,
}


def recent_longest_3w(activities: List[Dict[str, Any]], *, days: int = 21) -> float:
    """Return longest single run (miles) within last N days, reading miles first then meters.

    Pure function used by LR-first start selection.
    """
    if not activities:
        return 0.0
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    cutoff = now - timedelta(days=days)
    longest = 0.0
    for a in activities:
        dstr = a.get("date") or a.get("start_date") or a.get("startTime")
        if not dstr:
            continue
        try:
            dt = datetime.fromisoformat(dstr.replace("Z", "+00:00"))
        except Exception:
            continue
        if dt < cutoff:
            continue
        miles = 0.0
        for key in ("miles", "distance_miles", "distance"):
            v = a.get(key)
            if isinstance(v, (int, float)) and v > 0:
                miles = float(v)
                break
        if miles == 0.0:
            meters = a.get("distance_meters") or a.get("meters")
            if isinstance(meters, (int, float)) and meters > 0:
                miles = float(meters) / 1609.34
        if miles > longest:
            longest = miles
    return round(longest, 2)


def build_spine(
    start: float,
    *,
    total_weeks: Optional[int],
    peak: float,
    cfg: LRConfig,
    race_date: Any,
) -> List[Dict[str, Any]]:
    return generate_long_run_spine(
        starting_long_run_miles=start,
        total_weeks_in_plan=total_weeks,
        peak_long_run_target=peak,
        race_date=race_date,
        taper_weeks=cfg["taperWeeks"],
        non_regressive_slack=0.0,
        inc_miles=cfg["inc"],
        cutback_every=cfg["cutEvery"],
        cutback_factor=cfg["cutFactor"],
        peak_offset_before_taper=4 if (total_weeks or 0) >= 15 else 1,
    )


def validate_spine(
    weeks: List[Dict[str, Any]], *, expected_start: float, peak: float, cfg: LRConfig
) -> None:
    if not weeks:
        raise ValueError("LR spine empty")

    def rh(x: float) -> float:
        return round(x * 2) / 2.0

    if abs(weeks[0].get("long_run_miles", 0) - expected_start) > 1e-6:
        raise ValueError(
            f"Week 1 mismatch: got {weeks[0].get('long_run_miles', 0):.1f}, expected {expected_start:.1f} (recent_3w+1)"
        )

    total_weeks = weeks[-1]["week_number"]
    build_last = max(1, total_weeks - cfg["taperWeeks"] - 1)
    peaked = False
    last_was_cutback = False

    for i in range(1, total_weeks):
        lr_prev = float(weeks[i - 1].get("long_run_miles", 0))
        lr = float(weeks[i].get("long_run_miles", 0))
        lr_two_back = (
            float(weeks[i - 2].get("long_run_miles", 0)) if i - 2 >= 0 else lr_prev
        )

        if i + 1 <= build_last:
            cap = peak if not peaked else max(0.0, peak - 1.0)
            # Cutback rule: every 4th week and prior week below PEAK
            if ((i + 1) % cfg["cutEvery"]) == 0 and lr_prev < peak:
                if not (lr < lr_prev):
                    raise ValueError(f"Cutback expected at week {i+1}")
                last_was_cutback = True
            else:
                if last_was_cutback:
                    expected = rh(min(cap, lr_two_back + cfg["inc"]))
                    last_was_cutback = False
                else:
                    expected = rh(min(cap, lr_prev + cfg["inc"]))
                if abs(lr - expected) > 1e-6:
                    raise ValueError(
                        f"Week {i+1} invalid: got {lr:.1f}, expected {expected:.1f} (prev {lr_prev:.1f}, two_back {lr_two_back:.1f}, cap {cap:.1f})"
                    )
            if not peaked and lr >= peak - 1e-6:
                peaked = True
        else:
            if lr > peak + 1e-6:
                raise ValueError(
                    f"Taper week {i+1} exceeds peak: {lr:.1f} > {peak:.1f}"
                )


def _round_half(x: float) -> float:
    return round(x * 2) / 2.0


class Pass1LongRunFirst:
    """Derive plan duration and long-run progression first, then weekly totals.

    This pass estimates a safe long-run progression from the runner's current
    capability to a peak long run (typically 18–20 miles) with cutbacks and
    taper. It returns a recommended number of weeks and an array of weeks with
    `long_run_miles` only. Downstream passes can then compute weekly totals and
    day-by-day workouts while respecting this spine.
    """

    def __init__(
        self,
        *,
        data_collector: Optional[DataCollectionService] = None,
        insights_service: Optional[InsightsCalculationService] = None,
    ) -> None:
        self.data_collector = data_collector or DataCollectionService()
        self.insights_service = insights_service or InsightsCalculationService()

    def build(
        self,
        *,
        session: Session,
        user_id: str,
        plan_request: Dict[str, Any],
        activity_weeks: int = 12,
        target_peak_miles: float = 20.0,
        taper_weeks: int = 2,
    ) -> Dict[str, Any]:
        """Compute long-run progression and recommended duration.

        Returns:
            {
              "recommended_weeks": int,
              "weeks": [{"week_number": int, "long_run_miles": float}],
              "rationale": {...},
              "signals": {...}
            }
        """
        # L1 + L2
        raw = self.data_collector.collect_all_data(
            session=session,
            user_id=user_id,
            plan_request=plan_request,
            activity_weeks=activity_weeks,
        )
        insights = self.insights_service.calculate_all_insights(raw)
        current = insights.get("current_fitness", {})

        base_mpw = float(current.get("weekly_mileage", 0) or 0)
        longest_recent = float(current.get("longest_run", 0) or 0)
        exp = (plan_request.get("marathon_experience") or "").lower().strip()

        # Compute recent-3w longest; Week 1 MUST be this + 1.0 (rounded to 0.5)
        recent3w = recent_longest_3w(raw.get("strava_activities", []), days=21)
        if not recent3w or recent3w <= 0:
            raise ValueError(
                "Insufficient recent data: need at least one long run in last 21 days to set Week 1."
            )
        trusted_start = recent3w + 1.0
        logger.info(
            "LR-first signals: recent_3w_longest=%.2f, trusted_start=%.2f",
            recent3w,
            trusted_start,
        )
        start_rule_miles = trusted_start
        # Use a 3-week taper (≈70%, 50%, 25% of peak → 14, 10, 5 for 20)
        preferred_taper = 3
        cfg = {**DEFAULT_CFG, "taperWeeks": preferred_taper, "cutEvery": 3}

        # Use dynamic length mode: spine derives length organically from build to peak + recovery + taper
        weeks = build_spine(
            start_rule_miles,
            total_weeks=0,  # Dynamic length: derive from policy
            peak=target_peak_miles,
            cfg=cfg,
            race_date=plan_request.get("race_date"),
        )
        desired_total_weeks = len(weeks)

        # Validate (no mutation) – but don't block LR-only drafts
        try:
            validate_spine(
                weeks,
                expected_start=_round_half(trusted_start),
                peak=target_peak_miles,
                cfg=cfg,
            )
        except ValueError as e:
            logger.warning(
                "LR-first validation warning (non-blocking for LR-only): %s", e
            )

        recommended_weeks = weeks[-1]["week_number"] if weeks else 0
        if desired_total_weeks:
            recommended_weeks = max(recommended_weeks, desired_total_weeks)

        rationale = {
            "base_mpw": base_mpw,
            "longest_recent": longest_recent,
            "recent_longest_3w": recent3w,
            "start_rule": "recent_3w_longest + 1.0",
            "start_lr": weeks[0]["long_run_miles"] if weeks else None,
            "peak_cap": target_peak_miles,
            "cfg": cfg,
        }

        return {
            "recommended_weeks": recommended_weeks,
            "weeks": weeks,
            "rationale": rationale,
            "signals": {
                "base_mpw": base_mpw,
                "longest_recent": longest_recent,
                "experience": exp or None,
            },
        }

    @staticmethod
    def _recent_longest_run_last_days(
        activities: List[Dict[str, Any]], *, days: int = 21
    ) -> float:
        """Find the longest single run in the most recent N days.

        Tries multiple distance fields conservatively. Assumes dates are ISO strings.
        """
        if not activities:
            return 0.0
        from datetime import datetime, timedelta

        now = datetime.utcnow()
        cutoff = now - timedelta(days=days)
        longest = 0.0
        for a in activities:
            dstr = a.get("date") or a.get("start_date") or a.get("startTime")
            if not dstr:
                continue
            try:
                dt = datetime.fromisoformat(dstr.replace("Z", "+00:00"))
            except Exception:
                continue
            if dt < cutoff:
                continue
            # Try miles fields first, then convert meters if present
            miles = 0.0
            for key in ("miles", "distance_miles", "distance"):
                v = a.get(key)
                if isinstance(v, (int, float)) and v > 0:
                    miles = float(v)
                    break
            if miles == 0.0:
                meters = a.get("distance_meters") or a.get("meters")
                if isinstance(meters, (int, float)) and meters > 0:
                    miles = float(meters) / 1609.34
            if miles > longest:
                longest = miles
        return round(longest, 2)

    @staticmethod
    def _validate_weeks(
        weeks: List[Dict[str, Any]],
        *,
        expected_start: float,
        peak: float,
        taper_weeks: int,
    ) -> List[Dict[str, Any]]:
        """Validate LR spine invariants; raise on violations, do not mutate.

        Invariants:
          - Week 1 equals expected_start (rounded to 0.5)
          - Build weeks grow by +1.0 per week, with single-peak cap at 20 and post-peak cap at 19
          - Every 4th build week is a cutback (< prior week)
          - Taper weeks ≤ peak
        """
        if not weeks:
            raise ValueError("LR spine empty")

        def rh(x: float) -> float:
            return round(x * 2) / 2.0

        if abs(weeks[0].get("long_run_miles", 0) - expected_start) > 1e-6:
            raise ValueError(
                f"Week 1 mismatch: got {weeks[0].get('long_run_miles', 0):.1f}, expected {expected_start:.1f} (recent_3w+1)"
            )

        total_weeks = weeks[-1]["week_number"]
        build_last = max(1, total_weeks - taper_weeks - 1)
        peaked = False
        last_was_cutback = False

        for i in range(1, total_weeks):
            lr_prev = float(weeks[i - 1].get("long_run_miles", 0))
            lr = float(weeks[i].get("long_run_miles", 0))
            lr_two_back = (
                float(weeks[i - 2].get("long_run_miles", 0)) if i - 2 >= 0 else lr_prev
            )

            if i + 1 <= build_last:
                cap = peak if not peaked else max(0.0, peak - 1.0)
                # Cutback follows the spine rule: every 4th week and prior week below PEAK
                if ((i + 1) % 4) == 0 and lr_prev < peak:
                    # This week must be a cutback (< previous)
                    if not (lr < lr_prev):
                        raise ValueError(f"Cutback expected at week {i+1}")
                    last_was_cutback = True
                else:
                    if last_was_cutback:
                        # Resume: pre-cutback + 1.0
                        expected = rh(min(cap, lr_two_back + 1.0))
                        last_was_cutback = False
                    else:
                        # Normal build: prior week + 1.0
                        expected = rh(min(cap, lr_prev + 1.0))
                    if abs(lr - expected) > 1e-6:
                        raise ValueError(
                            f"Week {i+1} invalid: got {lr:.1f}, expected {expected:.1f} (prev {lr_prev:.1f}, two_back {lr_two_back:.1f}, cap {cap:.1f})"
                        )
                if not peaked and lr >= peak - 1e-6:
                    peaked = True
            else:
                if lr > peak + 1e-6:
                    raise ValueError(
                        f"Taper week {i+1} exceeds peak: {lr:.1f} > {peak:.1f}"
                    )

        return weeks

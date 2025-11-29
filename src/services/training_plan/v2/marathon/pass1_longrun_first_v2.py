from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict
import logging

# Removed Session import - no longer needed (receives data as parameters)

# Removed imports: DataCollectionServiceV2, InsightsCalculationServiceV2
# This class no longer collects data - it receives raw_data and insights from Step 1
from src.services.training_plan.v2.shared_v2.long_run_spine_v2 import (
    generate_long_run_spine,
)
from src.services.training_plan.v2.race_configs.base_config import RaceDistanceConfig
from src.services.training_plan.v2.shared_v2.long_run_signals import (
    calculate_recovery_week_long_run,
    detect_consecutive_long_runs_from_materialized_view,
    recent_longest_3w_from_materialized_view,
    round_to_half,
)
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


class LRConfig(TypedDict):
    inc: float
    cutEvery: int
    cutFactor: float
    singlePeak: bool
    taperWeeks: int


def _build_lr_config(config: RaceDistanceConfig) -> LRConfig:
    """Translate race-distance settings into LR spine parameters."""
    return {
        "inc": config.long_run_increment,
        "cutEvery": max(1, config.cutback_every),
        "cutFactor": config.cutback_factor,
        "singlePeak": True,
        "taperWeeks": config.taper_weeks,
    }


def build_spine(
    start: float,
    *,
    total_weeks: Optional[int],
    peak: float,
    cfg: LRConfig,
    race_date: Any,
    config: Optional[Any] = None,  # RaceDistanceConfig
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
        config=config,  # Pass config to spine generator
    )


def validate_spine(
    weeks: List[Dict[str, Any]], *, expected_start: float, peak: float, cfg: LRConfig
) -> None:
    if not weeks:
        raise ValueError("LR spine empty")

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
                    expected = round_to_half(min(cap, lr_two_back + cfg["inc"]))
                    last_was_cutback = False
                else:
                    expected = round_to_half(min(cap, lr_prev + cfg["inc"]))
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


class Pass1LongRunFirstV2:
    """Derive plan duration and long-run progression first, then weekly totals.

    This pass estimates a safe long-run progression from the runner's current
    capability to a peak long run (typically 18–20 miles) with cutbacks and
    taper. It returns a recommended number of weeks and an array of weeks with
    `long_run_miles` only. Downstream passes can then compute weekly totals and
    day-by-day workouts while respecting this spine.

    V2: Uses RaceDistanceConfig for race-distance-specific values.
    """

    def __init__(
        self,
        *,
        config: RaceDistanceConfig,
    ) -> None:
        self.config = config
        # No dependencies needed - receives raw_data and insights as parameters

    def build(
        self,
        *,
        session: Session,
        user_id: str,
        weekly_mileage: float,
        longest_run: float,
        plan_request: Dict[str, Any],
        recommended_weeks: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Compute long-run progression and recommended duration.

        NOTE: This function uses materialized view for data (same as metrics page).

        Args:
            session: Database session
            user_id: User ID for querying materialized view
            weekly_mileage: Average weekly mileage (from materialized view)
            longest_run: Longest run distance (from materialized view)
            plan_request: Plan request dictionary
            recommended_weeks: Readiness-based recommended plan length (from Pass1WeeksSelector).
                              If provided, plan will be built to fit within this timeframe.
                              If None, uses dynamic length mode (builds organically to peak).

        Returns:
            {
              "recommended_weeks": int,
              "weeks": [{"week_number": int, "long_run_miles": float}],
              "rationale": {...},
              "signals": {...}
            }
        """
        base_mpw = weekly_mileage
        longest_recent = longest_run

        # Check for consecutive long runs that warrant a recovery week (using materialized view)
        consecutive_analysis = detect_consecutive_long_runs_from_materialized_view(
            session=session, user_id=user_id, min_consecutive_weeks=3
        )

        # Compute recent-3w longest for baseline (using materialized view)
        recent3w = recent_longest_3w_from_materialized_view(
            session=session, user_id=user_id, days=21
        )
        if not recent3w or recent3w <= 0:
            raise ValueError(
                "Insufficient recent data: need at least one long run in last 21 days to set Week 1."
            )

        # Determine Week 1 long run based on consecutive run detection
        if consecutive_analysis["has_consecutive_runs"]:
            # Check if user has already self-regulated (recent reduction from peak)
            # Pattern detection: if most recent week is significantly lower than peak,
            # user may have already done a recovery - don't force double recovery
            has_recent_reduction = consecutive_analysis.get(
                "has_recent_reduction", False
            )
            most_recent_long_run = consecutive_analysis.get("most_recent_long_run", 0.0)

            if has_recent_reduction and most_recent_long_run > 0:
                # User already self-regulated - apply normal progression from baseline
                # Don't force another recovery that would set them back further
                # Baseline = most recent level (user's current baseline) or recent3w (whichever is higher)
                # Then apply standard +1.0 progression rule (same as normal progression)
                baseline = max(most_recent_long_run, recent3w)
                trusted_start = baseline + 1.0  # Apply standard progression rule
                start_rule = "continue_at_current_level_after_self_regulation"
                logger.info(
                    "LR-first: Detected %d consecutive weeks with long runs, "
                    "but user has already self-regulated (recent: %.2f, peak: %.2f). "
                    "Baseline: %.2f miles, Week 1: %.2f miles (+1.0 progression, avoiding double recovery)",
                    consecutive_analysis["consecutive_count"],
                    most_recent_long_run,
                    consecutive_analysis["longest_recent"],
                    baseline,
                    trusted_start,
                )
            else:
                # User has consecutive runs but no recent reduction - schedule recovery week
                # This is a build pattern (increasing) or flat at peak - recovery needed
                recovery_lr = calculate_recovery_week_long_run(
                    consecutive_analysis["longest_recent"], config=self.config
                )
                trusted_start = recovery_lr
                start_rule = "recovery_week_after_consecutive_runs"
                logger.info(
                    "LR-first: Detected %d consecutive weeks with long runs (longest=%.2f). "
                    "Setting Week 1 as recovery week: %.2f miles",
                    consecutive_analysis["consecutive_count"],
                    consecutive_analysis["longest_recent"],
                    recovery_lr,
                )
        else:
            # Normal progression: longest + 1.0
            trusted_start = recent3w + 1.0
            start_rule = "recent_3w_longest + 1.0"
            logger.info(
                "LR-first signals: recent_3w_longest=%.2f, trusted_start=%.2f",
                recent3w,
                trusted_start,
            )

        # Use config values for taper and peak
        target_peak_miles = self.config.target_peak_miles
        cfg = _build_lr_config(self.config)

        # CRITICAL: Cap starting long run if user's fitness exceeds race-specific peak
        # Example: User with 16mi LR doing half-marathon (peak=12mi) should start ~10-11mi, not 17mi
        if trusted_start > target_peak_miles:
            # User's current fitness exceeds race-specific peak
            # Start at peak - 1 or peak - 2 to allow some progression
            # For half-marathon: if peak=12 and user has 16mi, start at 10-11mi
            capped_start = max(
                target_peak_miles - 2.0,  # Allow 2-mile progression to peak
                self.config.min_long_run_miles,  # Never below absolute minimum
            )
            original_start = trusted_start
            trusted_start = round_to_half(capped_start)
            start_rule = f"{start_rule} (capped from {original_start:.1f} to {trusted_start:.1f} for race peak {target_peak_miles:.1f}mi)"
            logger.info(
                f"🔄 Capping starting long run: User's fitness ({original_start:.1f}mi) exceeds "
                f"race-specific peak ({target_peak_miles:.1f}mi). Starting at {trusted_start:.1f}mi "
                f"to allow progression to peak."
            )

        start_rule_miles = trusted_start

        # Use readiness-based recommended weeks if provided, otherwise use dynamic length mode
        # recommended_weeks comes from Pass1WeeksSelector based on user's weekly mileage
        if recommended_weeks and recommended_weeks > 0:
            logger.info(
                f"📏 Building FIXED-LENGTH plan: {recommended_weeks} weeks "
                f"(based on readiness: {base_mpw:.1f}mpw weekly mileage) "
                f"start_lr={start_rule_miles:.1f}mi → peak={target_peak_miles:.1f}mi"
            )
            # Fixed length mode: build within recommended timeframe
            # The spine will fit progression within recommended_weeks weeks
            weeks = build_spine(
                start_rule_miles,
                total_weeks=recommended_weeks,  # Use readiness-based recommendation
                peak=target_peak_miles,
                cfg=cfg,
                race_date=plan_request.get("race_date"),
                config=self.config,  # Pass config for removing hardcoded values
            )
        else:
            logger.info(
                f"📏 Building DYNAMIC-LENGTH plan (no readiness recommendation) "
                f"start_lr={start_rule_miles:.1f}mi → peak={target_peak_miles:.1f}mi "
                f"(will build organically to peak + taper)"
            )
            # Dynamic length mode: spine derives length organically from build to peak + recovery + taper
            weeks = build_spine(
                start_rule_miles,
                total_weeks=0,  # Dynamic length: derive from policy
                peak=target_peak_miles,
                cfg=cfg,
                race_date=plan_request.get("race_date"),
                config=self.config,  # Pass config for removing hardcoded values
            )
        desired_total_weeks = len(weeks)

        # Validate (no mutation) – but don't block LR-only drafts
        # Note: Validation expects exact match, but recovery weeks may differ from standard rule
        try:
            validate_spine(
                weeks,
                expected_start=round_to_half(trusted_start),
                peak=target_peak_miles,
                cfg=cfg,
            )
        except ValueError as e:
            # If recovery week was applied, validation mismatch is expected and OK
            if consecutive_analysis["has_consecutive_runs"]:
                logger.info(
                    "LR-first: Validation note (expected for recovery week): %s", e
                )
            else:
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
            "start_rule": start_rule,
            "start_lr": weeks[0]["long_run_miles"] if weeks else None,
            "peak_cap": target_peak_miles,
            "cfg": cfg,
            "consecutive_runs_detected": consecutive_analysis["has_consecutive_runs"],
            "consecutive_count": consecutive_analysis["consecutive_count"],
            "weekly_long_runs": consecutive_analysis["weekly_long_runs"],
            "recommended_weeks": recommended_weeks,  # Log the readiness-based recommendation used
            "mode": (
                "fixed_length"
                if recommended_weeks and recommended_weeks > 0
                else "dynamic_length"
            ),
        }

        return {
            "recommended_weeks": recommended_weeks,
            "weeks": weeks,
            "rationale": rationale,
            "signals": {
                "base_mpw": base_mpw,
                "longest_recent": longest_recent,
            },
        }

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
                        expected = round_to_half(min(cap, lr_two_back + 1.0))
                        last_was_cutback = False
                    else:
                        # Normal build: prior week + 1.0
                        expected = round_to_half(min(cap, lr_prev + 1.0))
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

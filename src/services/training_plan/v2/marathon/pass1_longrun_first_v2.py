from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict
import logging

# Removed Session import - no longer needed (receives data as parameters)

# Removed imports: DataCollectionServiceV2, InsightsCalculationServiceV2
# This class no longer collects data - it receives raw_data and insights from Step 1
from src.services.training_plan.v2.shared_v2.long_run_curve_validation import (
    validate_long_run_curve,
)
from src.services.training_plan.v2.shared_v2.long_run_spine_v2 import (
    build_long_run_spine_weeks,
    build_target_long_run_curve,
    compute_long_run_peak_week_metadata,
)
from src.services.training_plan.v2.race_configs.base_config import RaceDistanceConfig
from src.services.training_plan.v2.shared_v2.long_run_signals import (
    build_week1_long_run_explanation,
    calculate_recovery_week_long_run,
    compute_stable_week1_long_run_start,
    detect_consecutive_long_runs_from_materialized_view,
    fetch_recent_weekly_long_run_distances,
    pass1_use_recovery_week_after_consecutive,
    recent_longest_3w_from_materialized_view,
)
from src.services.training_plan.v2.shared_v2.rounding_utils import round_to_half_mile
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
    unit_system: str = "imperial",
) -> List[Dict[str, Any]]:
    return build_long_run_spine_weeks(
        starting_long_run_miles=start,
        total_weeks_in_plan=total_weeks,
        peak_long_run_target=peak,
        race_date=race_date,
        taper_weeks=cfg["taperWeeks"],
        non_regressive_slack=0.0,
        inc_miles=cfg["inc"],
        cutback_every=cfg["cutEvery"],
        cutback_factor=cfg["cutFactor"],
        # Keep peak closer to taper so Peak feels distinct from Build.
        peak_offset_before_taper=2 if (total_weeks or 0) >= 15 else 1,
        config=config,  # Pass config to spine generator
        unit_system=unit_system,
    )


def validate_spine(
    weeks: List[Dict[str, Any]],
    *,
    expected_start: float,
    peak: float,
    cfg: LRConfig,
    race_config: RaceDistanceConfig,
) -> None:
    """Validate LR spine week-to-week rules (delegates to central curve validation).

    DEPRECATED — replaced by ``validate_long_run_curve`` (Pass1 should call it
    directly with explicit flags). TODO Phase 3 Stage D: inline and delete this helper.
    See ``long_run_curve_validation`` module docstring (DEPRECATED COMPONENTS registry).
    """
    curve = [float(w.get("long_run_miles", 0) or 0) for w in weeks]
    issues = validate_long_run_curve(
        curve,
        race_config,
        spine_rows=weeks,
        expected_start_miles=float(expected_start),
        peak_target_miles=float(peak),
        taper_ratios_override=list(race_config.taper_ratios),
        cutback_every_override=int(race_config.cutback_every),
        taper_weeks_override=int(cfg["taperWeeks"]),
        include_structure_checks=False,
        include_peak_max_check=False,
        include_pass1_progression=True,
        include_phase_quality=False,
    )
    err = next((i for i in issues if i["severity"] == "error"), None)
    if err:
        raise ValueError(err["message"])


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
        unit_system: str = "imperial",
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

        # Last 4–6 weekly longest-run anchors (most recent first); 21d max as fallback
        weekly_series = fetch_recent_weekly_long_run_distances(
            session=session, user_id=user_id, max_weeks=6
        )
        recent3w = recent_longest_3w_from_materialized_view(
            session=session, user_id=user_id, days=21
        )

        effective_weekly_series = list(weekly_series)
        if not effective_weekly_series:
            if recent3w and recent3w > 0:
                effective_weekly_series = [recent3w]
            elif longest_recent and longest_recent > 0:
                effective_weekly_series = [float(longest_recent)]
            else:
                raise ValueError(
                    "Insufficient recent data: need weekly long-run history or a recent "
                    "longest-run value to set Week 1."
                )

        start_meta: Dict[str, Any] = {}
        week1_source = "stable_logic"
        week1_branch_flags: Optional[Dict[str, Any]] = None

        # Determine Week 1 long run based on consecutive run detection
        if consecutive_analysis["has_consecutive_runs"]:
            use_recovery, branch_flags = pass1_use_recovery_week_after_consecutive(
                effective_weekly_series, consecutive_analysis
            )
            week1_branch_flags = branch_flags
            most_recent_long_run = consecutive_analysis.get("most_recent_long_run", 0.0)
            has_recent_reduction = consecutive_analysis.get(
                "has_recent_reduction", False
            )

            if use_recovery:
                recovery_lr = calculate_recovery_week_long_run(
                    consecutive_analysis["longest_recent"],
                    config=self.config,
                    unit_system=unit_system,
                )
                trusted_start = recovery_lr
                week1_source = "recovery_path"
                start_rule = "recovery_week_after_consecutive_runs"
                start_meta = {
                    "rule": start_rule,
                    "recovery_lr": recovery_lr,
                    "longest_recent": consecutive_analysis["longest_recent"],
                    "branch_flags": branch_flags,
                }
                logger.info(
                    "LR-first: Consecutive long-run block; sustained downward trend "
                    "(flags=%s). Recovery week-1: %.2f mi (longest_recent=%.2f, count=%d)",
                    branch_flags,
                    recovery_lr,
                    consecutive_analysis["longest_recent"],
                    consecutive_analysis["consecutive_count"],
                )
            else:
                trusted_start, start_meta = compute_stable_week1_long_run_start(
                    effective_weekly_series,
                    long_run_increment=self.config.long_run_increment,
                    min_long_run_mi=self.config.min_long_run_miles,
                )
                start_meta = dict(start_meta)
                start_meta["branch_flags"] = branch_flags
                if has_recent_reduction and most_recent_long_run > 0:
                    start_rule = (
                        f"{start_meta.get('rule', 'stable')}_after_self_regulation"
                    )
                    logger.info(
                        "LR-first: Consecutive long-run block; stable week-1 "
                        "(self-regulated, flags=%s). recent=%.2f peak=%.2f meta=%s → %.2f mi",
                        branch_flags,
                        most_recent_long_run,
                        consecutive_analysis["longest_recent"],
                        start_meta,
                        trusted_start,
                    )
                else:
                    start_rule = str(start_meta.get("rule", "stable_week1"))
                    logger.info(
                        "LR-first: Consecutive long-run block; stable week-1 "
                        "(no recovery: flags=%s). series=%s meta=%s → %.2f mi",
                        branch_flags,
                        effective_weekly_series,
                        start_meta,
                        trusted_start,
                    )
        else:
            trusted_start, start_meta = compute_stable_week1_long_run_start(
                effective_weekly_series,
                long_run_increment=self.config.long_run_increment,
                min_long_run_mi=self.config.min_long_run_miles,
            )
            start_rule = str(start_meta.get("rule", "stable_week1"))
            logger.info(
                "LR-first stable week-1: series=%s recent_3w_single_run=%.2f meta=%s → start=%.2f",
                effective_weekly_series,
                float(recent3w or 0.0),
                start_meta,
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
            trusted_start = round_to_half_mile(capped_start)
            week1_source = "capped_start"
            start_rule = f"{start_rule} (capped from {original_start:.1f} to {trusted_start:.1f} for race peak {target_peak_miles:.1f}mi)"
            logger.info(
                f"🔄 Capping starting long run: User's fitness ({original_start:.1f}mi) exceeds "
                f"race-specific peak ({target_peak_miles:.1f}mi). Starting at {trusted_start:.1f}mi "
                f"to allow progression to peak."
            )

        start_rule_miles = trusted_start
        logger.info(
            "WEEK1_SOURCE = %s, value = %.2f",
            week1_source,
            float(trusted_start),
        )

        # Keep caller intent before `recommended_weeks` is overwritten with output length.
        fixed_length_requested = bool(recommended_weeks and recommended_weeks > 0)

        # Use readiness-based recommended weeks if provided, otherwise use dynamic length mode
        # recommended_weeks comes from Pass1WeeksSelector based on user's weekly mileage
        curve_total_weeks = (
            int(recommended_weeks)
            if (recommended_weeks and recommended_weeks > 0)
            else 0
        )
        peak_offset_before_taper = 2 if curve_total_weeks >= 15 else 1

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
                unit_system=unit_system,
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
                unit_system=unit_system,
            )
        desired_total_weeks = len(weeks)

        # Stage A: shadow target curve (same inputs as build_spine); spine path unchanged.
        target_long_run_curve_miles = build_target_long_run_curve(
            start_rule_miles,
            curve_total_weeks,
            target_peak_miles,
            race_date=plan_request.get("race_date"),
            taper_weeks=cfg["taperWeeks"],
            non_regressive_slack=0.0,
            inc_miles=cfg["inc"],
            cutback_every=cfg["cutEvery"],
            cutback_factor=cfg["cutFactor"],
            peak_offset_before_taper=peak_offset_before_taper,
            config=self.config,
            unit_system=unit_system,
        )
        spine_long_run_miles = [float(w.get("long_run_miles") or 0.0) for w in weeks]
        if target_long_run_curve_miles != spine_long_run_miles:
            logger.error(
                "LR curve Stage A parity mismatch: build_target_long_run_curve != build_spine "
                "(curve_len=%s spine_len=%s)",
                len(target_long_run_curve_miles),
                len(spine_long_run_miles),
            )

        # Validate (no mutation) – but don't block LR-only drafts
        # Note: Validation expects exact match, but recovery weeks may differ from standard rule
        # DEPRECATED path: validate_spine → validate_long_run_curve (TODO Stage D).
        try:
            validate_spine(
                weeks,
                expected_start=round_to_half_mile(trusted_start),
                peak=target_peak_miles,
                cfg=cfg,
                race_config=self.config,
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

        w0_lr = float(weeks[0]["long_run_miles"]) if weeks else 0.0
        peak_week_meta = compute_long_run_peak_week_metadata(
            weeks, taper_weeks=int(self.config.taper_weeks)
        )
        rationale = {
            "base_mpw": base_mpw,
            "longest_recent": longest_recent,
            "recent_longest_3w": recent3w,
            "weekly_long_run_series_for_week1": effective_weekly_series,
            "stable_week1_meta": start_meta,
            "start_rule": start_rule,
            "start_lr": weeks[0]["long_run_miles"] if weeks else None,
            "week1_long_run_explanation": build_week1_long_run_explanation(
                weekly_series=effective_weekly_series,
                start_lr_miles=w0_lr,
                start_meta=start_meta if isinstance(start_meta, dict) else {},
                start_rule=start_rule,
            ),
            "peak_cap": target_peak_miles,
            "cfg": cfg,
            "consecutive_runs_detected": consecutive_analysis["has_consecutive_runs"],
            "consecutive_count": consecutive_analysis["consecutive_count"],
            "weekly_long_runs": consecutive_analysis["weekly_long_runs"],
            "week1_consecutive_branch_flags": week1_branch_flags,
            "recommended_weeks": recommended_weeks,  # Log the readiness-based recommendation used
            "mode": "fixed_length" if fixed_length_requested else "dynamic_length",
            "target_long_run_curve_miles": target_long_run_curve_miles,
            "target_long_run_curve_stage_a_parity_ok": (
                target_long_run_curve_miles == spine_long_run_miles
            ),
            **peak_week_meta,
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
        cutback_every: int = 4,
    ) -> List[Dict[str, Any]]:
        """Validate LR spine invariants; raise on violations, do not mutate.

        Invariants:
          - Week 1 equals expected_start (rounded to 0.5)
          - Build weeks grow by +1.0 per week, with single-peak cap at 20 and post-peak cap at 19
          - Periodic cutback weeks (< prior week), cadence from ``cutback_every``
          - Taper weeks ≤ peak
        """
        if not weeks:
            raise ValueError("LR spine empty")

        if abs(weeks[0].get("long_run_miles", 0) - expected_start) > 1e-6:
            raise ValueError(
                f"Week 1 mismatch: got {weeks[0].get('long_run_miles', 0):.1f}, expected {expected_start:.1f} (stable week-1 rule)"
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
                if i % cutback_every == 0 and i >= cutback_every and lr_prev < peak:
                    if not (lr < lr_prev):
                        raise ValueError(f"Cutback expected at week {i+1}")
                    last_was_cutback = True
                else:
                    if last_was_cutback:
                        expected = round_to_half_mile(min(cap, lr_two_back + 1.0))
                        last_was_cutback = False
                    else:
                        expected = round_to_half_mile(min(cap, lr_prev + 1.0))
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

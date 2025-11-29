"""
Half Marathon Race Distance Configuration

Half-marathon-specific configuration values based on expert coaching methodologies.
"""

from typing import Any, Dict, Tuple, List
from .base_config import RaceDistanceConfig


class HalfMarathonConfig(RaceDistanceConfig):
    """Half-marathon-specific configuration."""

    # Long Run Progression
    @property
    def long_run_increment(self) -> float:
        """Default +1 mile build step during Base/Build."""
        return 1.0

    @property
    def cutback_every(self) -> int:
        """Run a cutback every 3 build weeks (more frequent than marathon)."""
        return 3

    @property
    def cutback_factor(self) -> float:
        """Reduce volume ~25% on cutback weeks."""
        return 0.75

    @property
    def target_peak_miles(self) -> float:
        """Peak long run distance for half-marathon (12 miles)."""
        return 12.0

    @property
    def taper_weeks(self) -> int:
        """Shorter taper for half-marathon (2 weeks)."""
        return 2

    @property
    def taper_ratios(self) -> List[float]:
        """Taper ratios for 2-week taper: 70%, 40% of peak."""
        return [0.70, 0.40]

    @property
    def recovery_long_run_floor(self) -> float:
        """Minimum long run used when scheduling a recovery week."""
        return 6.0

    @property
    def recovery_reduction_ratio(self) -> float:
        """Percentage of the longest recent run to target for recovery."""
        return 0.70

    # Post-Peak Configuration
    @property
    def post_peak_recovery_ratio(self) -> float:
        """75% of peak for immediate post-peak recovery week."""
        return 0.75

    @property
    def maintenance_reduction(self) -> float:
        """Reduce 1.5 miles from peak for maintenance weeks."""
        return 1.5

    @property
    def pre_taper_cap_weeks(self) -> int:
        """Cap long runs in last 4 weeks before taper."""
        return 4

    @property
    def pre_taper_cap_miles(self) -> float:
        """Cap at 10 miles in pre-taper weeks (below 12-mile peak)."""
        return 10.0

    @property
    def min_long_run_miles(self) -> float:
        """Absolute minimum long run distance (5 miles)."""
        return 5.0

    @property
    def resume_week_increment(self) -> float:
        """Add 1.5 miles after cutback during resume week."""
        return 1.5

    # Weekly Totals
    @property
    def long_run_percentage_ranges(self) -> Dict[int, Tuple[float, float]]:
        """
        Long run percentage of weekly total by runs_per_week.

        Half-marathon uses slightly lower percentages than marathon:
        - 3 days: 35-45% (target 40%)
        - 4 days: 30-40% (target 35%)
        - 5 days: 25-35% (target 30%)
        """
        return {
            3: (0.35, 0.45),
            4: (0.30, 0.40),
            5: (0.25, 0.35),
        }

    @property
    def peak_caps(self) -> Dict[int, int]:
        """
        Peak weekly mileage caps by runs_per_week.

        Half-marathon uses lower caps than marathon:
        - 3 days: 32 mi peak
        - 4 days: 38 mi peak
        - 5 days: 42 mi peak
        """
        return {
            3: 32,
            4: 38,
            5: 42,
        }

    @property
    def weekly_increase_cap(self) -> float:
        """Maximum weekly mileage increase (8%)."""
        return 0.08

    @property
    def phase_delta_caps(self) -> Dict[str, float]:
        """Maximum allowed week-over-week change per training phase."""
        return {
            "Base": 0.10,
            "Build": 0.10,
            "Peak": 0.05,
            "Taper": -0.10,
        }

    @property
    def max_long_run_share_by_phase(self) -> Dict[str, float]:
        """Maximum long run share of weekly mileage per phase."""
        return {
            "Base": 0.40,
            "Build": 0.40,
            "Peak": 0.40,
            "Taper": 0.50,
        }

    @property
    def final_taper_long_run_range(self) -> Tuple[float, float]:
        """Acceptable ratio (current / previous) for final taper long run."""
        return (0.40, 0.60)

    # Workout Distribution
    @property
    def non_long_shares(self) -> Dict[int, List[float]]:
        """
        Non-long run mileage distribution shares by runs_per_week.

        Same structure as marathon, but will be used with different total mileage:
        - 3 days: [0.55, 0.45] (ENDURANCE, EASY)
        - 4 days: [0.40, 0.30, 0.30] (ENDURANCE, STEADY, EASY)
        - 5 days: [0.32, 0.25, 0.23, 0.20] (ENDURANCE, STEADY, STEADY, EASY)
        """
        return {
            3: [0.55, 0.45],
            4: [0.40, 0.30, 0.30],
            5: [0.32, 0.25, 0.23, 0.20],
        }

    @property
    def min_non_long_day(self) -> float:
        """Minimum miles per non-long run day."""
        return 3.0

    # Validation Thresholds
    @property
    def high_long_run_threshold(self) -> float:
        """Threshold for 'high long run' warnings (11.0 miles)."""
        return 11.0

    @property
    def sustained_high_threshold(self) -> float:
        """Threshold for sustained high long runs (11.5 miles)."""
        return 11.5

    @property
    def race_distance_miles(self) -> float:
        """Half-marathon distance in miles."""
        return 13.1

    # Race Date Validation Thresholds
    @property
    def min_training_weeks(self) -> int:
        """Absolute minimum training weeks required for half-marathon (8 weeks)."""
        return 8

    @property
    def strong_base_exception_weeks(self) -> int:
        """Weeks allowed with strong base for half-marathon (7 weeks)."""
        return 7

    @property
    def strong_base_weekly_mileage(self) -> float:
        """Minimum weekly mileage to qualify as strong base (25.0 mpw)."""
        return 25.0

    @property
    def strong_base_long_run(self) -> float:
        """Minimum long run to qualify as strong base (8.0 miles)."""
        return 8.0

    @property
    def absolute_min_weekly_mileage(self) -> float:
        """Absolute minimum weekly mileage required (12.0 mpw)."""
        return 12.0

    @property
    def absolute_min_long_run(self) -> float:
        """Absolute minimum long run required (5.0 miles)."""
        return 5.0

    @property
    def fitness_requirements_by_weeks(self) -> Dict[str, Dict[str, Any]]:
        """
        Fitness requirements by week range for half-marathon training.

        Based on established methodologies:
        - 8-10 weeks: Need strong base (25+ mpw, 8+ mi LR)
        - 10-12 weeks: Need moderate base (20+ mpw, 6+ mi LR)
        - 12-14 weeks: Need minimum base (15+ mpw, 5+ mi LR)
        - 14+ weeks: More flexible (15+ mpw, 5+ mi LR acceptable)
        """
        return {
            "8_10": {
                "min_weekly_mileage": 25.0,
                "min_long_run": 8.0,
                "warn_weekly_mileage": 28.0,
                "warn_long_run": 9.0,
            },
            "10_12": {
                "min_weekly_mileage": 20.0,
                "min_long_run": 6.0,
            },
            "12_14": {
                "min_weekly_mileage": 15.0,
                "min_long_run": 5.0,
            },
            "14_plus": {
                "min_weekly_mileage": 15.0,
                "min_long_run": 5.0,
            },
        }

    def race_week_template(self) -> Dict[str, Any]:
        """Canonical half-marathon race week layout."""
        return {
            "weekly_mileage": 6
            + self.race_distance_miles,  # Include race distance in total
            "long_run_miles": 0.0,
            "workouts": [
                {
                    "day": "Mon",
                    "miles": 3.0,
                    "note": "Keep it conversational",
                    "kind": "easy",
                },
                {
                    "day": "Wed",
                    "miles": 3.0,
                    "note": "Include 4×20s relaxed strides",
                    "kind": "easy",
                },
                {
                    "day": "Thu",
                    "miles": 2.0,
                    "note": "Stay loose, no pushing",
                    "kind": "easy",
                },
                {
                    "day": "Sun",
                    "miles": self.race_distance_miles,
                    "note": "Half Marathon – trust your training and enjoy the experience!",
                    "kind": "race",
                    "label": "Race Day",
                },
            ],
        }

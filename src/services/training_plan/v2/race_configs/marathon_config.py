"""
Marathon Race Distance Configuration

Marathon-specific configuration values extracted from existing hardcoded values.
"""

from typing import Any, Dict, Tuple, List
from .base_config import RaceDistanceConfig


class MarathonConfig(RaceDistanceConfig):
    """Marathon-specific configuration."""

    # Long Run Progression
    @property
    def long_run_increment(self) -> float:
        """Default +1 mile build step during Base/Build."""
        return 1.0

    @property
    def cutback_every(self) -> int:
        """Run a cutback every 4 build weeks."""
        return 4

    @property
    def cutback_factor(self) -> float:
        """Reduce volume ~25% on cutback weeks."""
        return 0.75

    @property
    def target_peak_miles(self) -> float:
        return 20.0

    @property
    def taper_weeks(self) -> int:
        return 3

    @property
    def taper_ratios(self) -> List[float]:
        return [0.70, 0.50, 0.25]  # 70%, 50%, 25% of peak

    @property
    def recovery_long_run_floor(self) -> float:
        """Minimum long run used when scheduling a recovery week."""
        return 8.0

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
        """Reduce 2 miles from peak for maintenance weeks."""
        return 2.0

    @property
    def pre_taper_cap_weeks(self) -> int:
        """Cap long runs in last 5 weeks before taper."""
        return 5

    @property
    def pre_taper_cap_miles(self) -> float:
        """Cap at 16 miles in pre-taper weeks (below 20-mile peak)."""
        return 16.0

    @property
    def min_long_run_miles(self) -> float:
        """Absolute minimum long run distance (5 miles)."""
        return 5.0

    @property
    def resume_week_increment(self) -> float:
        """Add 2 miles after cutback during resume week."""
        return 2.0

    # Weekly Totals
    @property
    def long_run_percentage_ranges(self) -> Dict[int, Tuple[float, float]]:
        """
        Long run percentage of weekly total by runs_per_week.

        From weekly_total_calculator.py:
        - 3 days: 40-50% (target 45%)
        - 4 days: 35-45% (target 40%)
        - 5 days: 30-40% (target 33%)
        """
        return {
            3: (0.40, 0.50),
            4: (0.35, 0.45),
            5: (0.30, 0.40),
        }

    @property
    def peak_caps(self) -> Dict[int, int]:
        """
        Peak weekly mileage caps by runs_per_week.

        From weekly_total_calculator.py:
        - 3 days: 42 mi peak
        - 4 days: 46 mi peak
        - 5 days: 50 mi peak
        """
        return {
            3: 42,
            4: 46,
            5: 50,
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
            "Taper": 0.55,
        }

    @property
    def final_taper_long_run_range(self) -> Tuple[float, float]:
        """Acceptable ratio (current / previous) for final taper long run."""
        return (0.45, 0.65)

    # Workout Distribution
    @property
    def non_long_shares(self) -> Dict[int, List[float]]:
        """
        Non-long run mileage distribution shares by runs_per_week.

        From workout_types.py:
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
        """Threshold for 'high long run' warnings (18.0 miles)."""
        return 18.0

    @property
    def sustained_high_threshold(self) -> float:
        """Threshold for sustained high long runs (19.0 miles)."""
        return 19.0

    @property
    def race_distance_miles(self) -> float:
        """Marathon distance in miles."""
        return 26.2

    # Race Date Validation Thresholds
    @property
    def min_training_weeks(self) -> int:
        """Absolute minimum training weeks required for marathon (12 weeks)."""
        return 12

    @property
    def strong_base_exception_weeks(self) -> int:
        """Weeks allowed with strong base for marathon (11 weeks)."""
        return 11

    @property
    def strong_base_weekly_mileage(self) -> float:
        """Minimum weekly mileage to qualify as strong base (30.0 mpw)."""
        return 30.0

    @property
    def strong_base_long_run(self) -> float:
        """Minimum long run to qualify as strong base (10.0 miles)."""
        return 10.0

    @property
    def very_strong_base_exception_weeks(self) -> int:
        """Weeks allowed with very strong base for marathon (10 weeks)."""
        return 10

    @property
    def very_strong_base_weekly_mileage(self) -> float:
        """Minimum weekly mileage to qualify for 10-week plan (35.0 mpw)."""
        return 35.0

    @property
    def very_strong_base_long_run(self) -> float:
        """Minimum long run to qualify for 10-week plan (12.0 miles)."""
        return 12.0

    @property
    def absolute_min_weekly_mileage(self) -> float:
        """Absolute minimum weekly mileage required (15.0 mpw)."""
        return 15.0

    @property
    def absolute_min_long_run(self) -> float:
        """Absolute minimum long run required (5.0 miles)."""
        return 5.0

    @property
    def fitness_requirements_by_weeks(self) -> Dict[str, Dict[str, Any]]:
        """
        Fitness requirements by week range for marathon training.

        Based on established methodologies:
        - 12-14 weeks: Need strong base (30+ mpw, 10+ mi LR)
        - 14-16 weeks: Need moderate base (25+ mpw, 8+ mi LR)
        - 16-18 weeks: Need minimum base (20+ mpw, 6+ mi LR)
        - 18+ weeks: More flexible (20+ mpw, 6+ mi LR acceptable)
        """
        return {
            "12_14": {
                "min_weekly_mileage": 30.0,
                "min_long_run": 10.0,
                "warn_weekly_mileage": 35.0,
                "warn_long_run": 12.0,
            },
            "14_16": {
                "min_weekly_mileage": 25.0,
                "min_long_run": 8.0,
            },
            "16_18": {
                "min_weekly_mileage": 20.0,
                "min_long_run": 6.0,
            },
            "18_plus": {
                "min_weekly_mileage": 20.0,
                "min_long_run": 6.0,
            },
        }

    def race_week_template(self) -> Dict[str, Any]:
        """Canonical marathon race week layout."""
        return {
            "weekly_mileage": 8
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
                    "day": "Fri",
                    "miles": 2.0,
                    "note": "Optional shakeout; skip if tired",
                    "kind": "easy",
                    "shakeout": True,
                },
                {
                    "day": "Sun",
                    "miles": self.race_distance_miles,
                    "note": "Marathon – trust your training and enjoy the experience!",
                    "kind": "race",
                    "label": "Race Day",
                },
            ],
        }

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
        """Reduce volume ~30% on cutback weeks."""
        return 0.70

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

    def race_week_template(self) -> Dict[str, Any]:
        """Canonical marathon race week layout."""
        return {
            "weekly_mileage": 8,
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

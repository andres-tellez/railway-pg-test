"""
Base Race Distance Configuration

Abstract base class for race-distance-specific configurations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Tuple, List, Any


class RaceDistanceConfig(ABC):
    """Base class for race-distance-specific configuration."""

    # Long Run Progression
    @property
    @abstractmethod
    def target_peak_miles(self) -> float:
        """Target peak long run distance in miles."""
        pass

    @property
    @abstractmethod
    def taper_weeks(self) -> int:
        """Number of taper weeks."""
        pass

    @property
    @abstractmethod
    def taper_ratios(self) -> List[float]:
        """Taper ratios (e.g., [0.70, 0.50, 0.25] for 3-week taper)."""
        pass

    # Long Run Progression tuning
    @property
    @abstractmethod
    def long_run_increment(self) -> float:
        """Default growth per build week (e.g., +1 mile)."""
        pass

    @property
    @abstractmethod
    def cutback_every(self) -> int:
        """Frequency (in weeks) between cutbacks during build."""
        pass

    @property
    @abstractmethod
    def cutback_factor(self) -> float:
        """Multiplier applied during cutback weeks (e.g., 0.70)."""
        pass

    @property
    @abstractmethod
    def recovery_long_run_floor(self) -> float:
        """Minimum allowable recovery long run distance."""
        pass

    @property
    @abstractmethod
    def recovery_reduction_ratio(self) -> float:
        """Percent of longest recent run used for recovery weeks."""
        pass

    # Post-Peak Configuration
    @property
    @abstractmethod
    def post_peak_recovery_ratio(self) -> float:
        """Percentage of peak used for immediate post-peak recovery week (e.g., 0.75 for 75%)."""
        pass

    @property
    @abstractmethod
    def maintenance_reduction(self) -> float:
        """Miles to reduce from peak for maintenance weeks (e.g., 2.0 miles)."""
        pass

    @property
    @abstractmethod
    def pre_taper_cap_weeks(self) -> int:
        """Number of weeks before taper to cap long runs (e.g., 5 weeks)."""
        pass

    @property
    @abstractmethod
    def pre_taper_cap_miles(self) -> float:
        """Maximum long run miles in pre-taper weeks (e.g., 16.0). Should be < target_peak_miles."""
        pass

    @property
    @abstractmethod
    def min_long_run_miles(self) -> float:
        """Absolute minimum long run distance allowed (e.g., 5.0 miles)."""
        pass

    @property
    @abstractmethod
    def resume_week_increment(self) -> float:
        """Miles to add after cutback week during resume (e.g., 2.0 miles)."""
        pass

    # Weekly Totals
    @property
    @abstractmethod
    def long_run_percentage_ranges(self) -> Dict[int, Tuple[float, float]]:
        """
        Long run percentage of weekly total by runs_per_week.

        Returns:
            Dict mapping runs_per_week -> (min_pct, max_pct)
            Example: {3: (0.40, 0.50), 4: (0.35, 0.45), 5: (0.30, 0.40)}
        """
        pass

    @property
    @abstractmethod
    def peak_caps(self) -> Dict[int, int]:
        """
        Peak weekly mileage caps by runs_per_week.

        Returns:
            Dict mapping runs_per_week -> peak_cap_miles
            Example: {3: 42, 4: 46, 5: 50}
        """
        pass

    @property
    @abstractmethod
    def weekly_increase_cap(self) -> float:
        """Maximum weekly mileage increase percentage (e.g., 0.08 for 8%)."""
        pass

    # Workout Distribution
    @property
    @abstractmethod
    def non_long_shares(self) -> Dict[int, List[float]]:
        """
        Non-long run mileage distribution shares by runs_per_week.

        Returns:
            Dict mapping runs_per_week -> List[shares] (sums to 1.0)
            Example: {3: [0.55, 0.45], 4: [0.40, 0.30, 0.30], 5: [0.32, 0.25, 0.23, 0.20]}
        """
        pass

    @property
    @abstractmethod
    def min_non_long_day(self) -> float:
        """Minimum miles per non-long run day."""
        pass

    # Validation Thresholds
    @property
    @abstractmethod
    def high_long_run_threshold(self) -> float:
        """Threshold for 'high long run' warnings (miles)."""
        pass

    @property
    @abstractmethod
    def sustained_high_threshold(self) -> float:
        """Threshold for sustained high long runs (miles)."""
        pass

    @property
    @abstractmethod
    def race_distance_miles(self) -> float:
        """Race distance in miles (e.g., 26.2 for marathon, 13.1 for half)."""
        pass

    # Race Date Validation Thresholds
    @property
    @abstractmethod
    def min_training_weeks(self) -> int:
        """Absolute minimum training weeks required (e.g., 12 for marathon)."""
        pass

    @property
    @abstractmethod
    def strong_base_exception_weeks(self) -> int:
        """Weeks allowed with strong base (e.g., 11 for marathon, must be < min_training_weeks)."""
        pass

    @property
    @abstractmethod
    def strong_base_weekly_mileage(self) -> float:
        """Minimum weekly mileage to qualify as strong base (e.g., 30.0 for marathon)."""
        pass

    @property
    @abstractmethod
    def strong_base_long_run(self) -> float:
        """Minimum long run to qualify as strong base (e.g., 10.0 for marathon)."""
        pass

    @property
    @abstractmethod
    def absolute_min_weekly_mileage(self) -> float:
        """Absolute minimum weekly mileage required (e.g., 15.0 for marathon)."""
        pass

    @property
    @abstractmethod
    def absolute_min_long_run(self) -> float:
        """Absolute minimum long run required (e.g., 5.0 for marathon)."""
        pass

    @property
    @abstractmethod
    def fitness_requirements_by_weeks(self) -> Dict[str, Dict[str, Any]]:
        """
        Fitness requirements by week range.
        
        Returns:
            Dict mapping week range keys to requirement dicts.
            Example:
            {
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
                ...
            }
        """
        pass

    @property
    @abstractmethod
    def phase_delta_caps(self) -> Dict[str, float]:
        """
        Maximum allowed week-over-week change (as decimal) per training phase.

        Example:
            {
                "Base": 0.10,   # allow up to +10%
                "Build": 0.10,
                "Peak": 0.05,
                "Taper": -0.10  # taper weeks should not exceed 90% of prior week
            }
        """
        pass

    @property
    @abstractmethod
    def max_long_run_share_by_phase(self) -> Dict[str, float]:
        """
        Maximum allowed long run share of weekly mileage per phase.

        Values are expressed as decimals (e.g., 0.40 = 40% of weekly mileage).
        """
        pass

    @property
    @abstractmethod
    def final_taper_long_run_range(self) -> Tuple[float, float]:
        """
        Acceptable ratio (current / previous week) for the final taper long run.

        Returns:
            (min_ratio, max_ratio) expressed as decimals (e.g., (0.45, 0.65)).
        """
        pass

    @abstractmethod
    def race_week_template(self) -> Dict[str, Any]:
        """Return canonical race-week structure used by the orchestrator."""
        pass

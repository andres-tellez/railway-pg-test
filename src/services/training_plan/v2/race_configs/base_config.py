"""
Base Race Distance Configuration

Abstract base class for race-distance-specific configurations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Tuple, List


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

"""
Pace Calculation Strategies

Strategy pattern implementation for different pace calculation methods.
Allows easy extension with new calculation approaches.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.orm import Session

from .models import PaceSeed
from .config import PaceConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)


class PaceCalculationStrategy(ABC):
    """
    Abstract base class for pace calculation strategies.

    Each strategy implements a different method for calculating pace zones:
    - Performance-based (from recent run data)
    - Calibration (conservative defaults)
    - Future: HR-based, VDOT-based, etc.
    """

    def __init__(self, config: PaceConfig = None):
        """
        Initialize strategy with configuration.

        Args:
            config: PaceConfig instance (defaults to DEFAULT_CONFIG)
        """
        self.config = config or DEFAULT_CONFIG

    @abstractmethod
    def calculate(
        self,
        session: Session,
        user_id: str,
        week1_long: float = None,
        lookback_weeks: int = None,
    ) -> Optional[PaceSeed]:
        """
        Calculate pace zones using this strategy.

        Args:
            session: Database session
            user_id: User UUID string
            week1_long: Planned long run distance for week 1
            lookback_weeks: Weeks of history to analyze

        Returns:
            PaceSeed if calculation succeeds, None if strategy cannot calculate
            (e.g., insufficient data)

        Raises:
            ValueError: If input parameters are invalid
            RuntimeError: If calculation fails unexpectedly
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return strategy name for logging/identification."""
        pass


class PerformanceBasedStrategy(PaceCalculationStrategy):
    """
    Calculate pace zones from recent run performance.

    Uses SQL-based median easy pace calculation.
    """

    def __init__(self, config: PaceConfig = None):
        super().__init__(config)
        # Import here to avoid circular dependencies
        from .performance_calculator import calculate_paces_from_performance

        self._calculate_fn = calculate_paces_from_performance

    def calculate(
        self,
        session: Session,
        user_id: str,
        week1_long: float = None,
        lookback_weeks: int = None,
    ) -> Optional[PaceSeed]:
        """
        Calculate paces from performance data.

        Returns None if insufficient data (< 6 runs).
        """
        logger.debug(
            f"[{self.name}] Calculating paces for user {user_id} "
            f"(lookback_weeks={lookback_weeks or self.config.LOOKBACK_WEEKS})"
        )

        try:
            return self._calculate_fn(
                session=session,
                user_id=user_id,
                lookback_weeks=lookback_weeks or self.config.LOOKBACK_WEEKS,
                min_distance_miles=self.config.MIN_DISTANCE_MILES,
                config=self.config,  # Pass config to function
            )
        except Exception as e:
            logger.warning(f"[{self.name}] Calculation failed for user {user_id}: {e}")
            return None

    @property
    def name(self) -> str:
        return "Performance-Based"


class CalibrationStrategy(PaceCalculationStrategy):
    """
    Calculate pace zones using conservative calibration defaults.

    Fallback strategy when performance data is insufficient.
    """

    def __init__(self, config: PaceConfig = None):
        super().__init__(config)
        # Import here to avoid circular dependencies
        from .calibration import get_calibration_pace_seed

        self._calculate_fn = get_calibration_pace_seed

    def calculate(
        self,
        session: Session,
        user_id: str,
        week1_long: float = None,
        lookback_weeks: int = None,
    ) -> Optional[PaceSeed]:
        """
        Calculate paces using calibration defaults.

        Always succeeds (never returns None).
        """
        logger.debug(
            f"[{self.name}] Calculating calibration paces "
            f"(week1_long={week1_long or self.config.MIN_WEEK1_LONG_CAP})"
        )

        try:
            return self._calculate_fn(
                week1_long=week1_long or self.config.MIN_WEEK1_LONG_CAP,
                config=self.config,  # Pass config to function
            )
        except Exception as e:
            logger.error(f"[{self.name}] Calibration failed: {e}")
            raise RuntimeError(f"Calibration strategy failed: {e}") from e

    @property
    def name(self) -> str:
        return "Calibration"


# Default strategy chain (ordered by preference)
DEFAULT_STRATEGIES = [
    PerformanceBasedStrategy(),
    CalibrationStrategy(),  # Always succeeds as fallback
]

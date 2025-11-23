"""
Plan Constraints Service

Single responsibility: Calculate and enforce plan constraints.

This service centralizes all logic related to:
- Calculating available weeks from race date
- Calculating optimal start date
- Constraining plan length (fitness-based vs race date)
- Validating plan fits within constraints
- Trimming plans that exceed constraints

This makes race date a first-class constraint and ensures consistency
across all plan generation components.
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
import logging

from src.utils.date_helpers import get_week_start_for_date, get_next_monday

logger = logging.getLogger(__name__)


class PlanConstraints:
    """Data class for plan constraints."""

    def __init__(
        self,
        target_weeks: int,
        available_weeks: Optional[int] = None,
        recommended_weeks: Optional[int] = None,
        min_start_date: Optional[date] = None,
        race_date: Optional[date] = None,
    ):
        self.target_weeks = target_weeks
        self.available_weeks = available_weeks
        self.recommended_weeks = recommended_weeks
        self.min_start_date = min_start_date
        self.race_date = race_date

    def __repr__(self) -> str:
        return (
            f"PlanConstraints(target={self.target_weeks}, "
            f"available={self.available_weeks}, recommended={self.recommended_weeks})"
        )


class PlanConstraintsService:
    """
    Service for calculating and enforcing plan constraints.

    Responsibilities:
    - Calculate available weeks from race date
    - Calculate optimal start date
    - Constrain plan length (fitness-based vs race date)
    - Validate plan fits within constraints
    - Trim plans that exceed constraints
    """

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        """Parse various date formats to date object."""
        if not value:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        try:
            return datetime.fromisoformat(str(value).split("T")[0]).date()
        except Exception:
            return None

    def calculate_plan_constraints(
        self,
        *,
        race_date: Any,
        recommended_weeks: int,
        min_start_date: Optional[date] = None,
    ) -> PlanConstraints:
        """
        Calculate final plan constraints considering both fitness and race date.

        Args:
            race_date: Race date (any format)
            recommended_weeks: Fitness-based recommended plan length
            min_start_date: Minimum start date (if None, calculates from today)

        Returns:
            PlanConstraints with target_weeks constrained by race date
        """
        if min_start_date is None:
            today = datetime.now().date()
            min_start_date = get_next_monday(today, include_today=False)

        target_weeks = recommended_weeks  # Start with fitness-based recommendation
        available_weeks = None
        race_d = None

        if race_date:
            race_d = self._parse_date(race_date)
            if race_d:
                race_week_start = get_week_start_for_date(race_d)
                days_to_race = (race_week_start - min_start_date).days
                available_weeks = max(1, int(days_to_race / 7))

                # Constrain: Use minimum of fitness-based recommendation and available weeks
                target_weeks = min(recommended_weeks, available_weeks)

                logger.info(
                    f"📅 Race date constraint: {recommended_weeks} weeks recommended (fitness), "
                    f"{available_weeks} weeks available (race date: {race_d.isoformat()}), "
                    f"using {target_weeks} weeks"
                )

        return PlanConstraints(
            target_weeks=target_weeks,
            available_weeks=available_weeks,
            recommended_weeks=recommended_weeks,
            min_start_date=min_start_date,
            race_date=race_d,
        )

    def calculate_start_date(
        self,
        *,
        race_date: Any,
        plan_length_weeks: int,
        min_start_date: Optional[date] = None,
        fallback_start: Any = None,
    ) -> Optional[date]:
        """
        Calculate optimal start date, ensuring it's not in the past.

        Priority:
        1. If race_date provided: Calculate backwards from race date (for alignment)
        2. Ensure minimum start is the week AFTER current week (no past dates)
        3. Fallback to provided start_date if available
        4. Default to next Monday if all else fails

        Args:
            race_date: Race date (any format)
            plan_length_weeks: Number of weeks in the plan
            min_start_date: Minimum start date (if None, calculates from today)
            fallback_start: Fallback start date if race_date not provided

        Returns:
            Calculated start date, or None if invalid
        """
        if plan_length_weeks <= 0:
            return self._parse_date(fallback_start)

        if min_start_date is None:
            today = datetime.now().date()
            min_start_date = get_next_monday(today, include_today=False)

        calculated_start = None

        if race_date:
            race_d = self._parse_date(race_date)
            if race_d:
                try:
                    race_week_start = get_week_start_for_date(race_d)
                    offset_weeks = max(0, plan_length_weeks - 1)
                    calculated_start = race_week_start - timedelta(weeks=offset_weeks)
                    logger.info(
                        f"Calculated start from race date: {calculated_start} "
                        f"(race_week_start={race_week_start}, plan_length={plan_length_weeks})"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to align start date from race_date={race_date}: {e}"
                    )

        # Use calculated start if available, otherwise try fallback
        if calculated_start:
            start_date = calculated_start
        else:
            parsed_fallback = self._parse_date(fallback_start)
            if parsed_fallback:
                start_date = parsed_fallback
            else:
                # Default to next Monday
                start_date = min_start_date

        # CRITICAL: Ensure start date is never in the past
        # Use the later of: calculated/fallback start OR minimum (next Monday)
        if start_date < min_start_date:
            logger.warning(
                f"Start date {start_date} is in the past. "
                f"Adjusting to minimum start date: {min_start_date} (week after current week)"
            )
            start_date = min_start_date

        logger.info(
            f"Final aligned start date: {start_date} "
            f"(min_start={min_start_date}, calculated={calculated_start})"
        )
        return start_date

    def trim_plan_to_constraints(
        self,
        weeks: List[Dict[str, Any]],
        race_date: Any,
        start_date: date,
    ) -> Tuple[List[Dict[str, Any]], date]:
        """
        Trim plan if it exceeds race date constraint.

        Preserves the race week (last week) and as many weeks before it as possible.

        Args:
            weeks: List of week dictionaries
            race_date: Race date (any format)
            start_date: Current start date

        Returns:
            Tuple of (trimmed_weeks, updated_start_date)
        """
        race_d = self._parse_date(race_date)
        if not race_d or not weeks:
            return weeks, start_date

        race_week_start = get_week_start_for_date(race_d)
        # Calculate maximum weeks that fit before race date
        days_to_race = (race_week_start - start_date).days
        max_weeks = max(1, int(days_to_race / 7) + 1)  # +1 to include race week

        if len(weeks) <= max_weeks:
            return weeks, start_date

        logger.warning(
            f"Plan has {len(weeks)} weeks but only {max_weeks} weeks until race. "
            f"Trimming {len(weeks) - max_weeks} weeks to fit race date constraint."
        )

        # Keep the last N weeks (including race week)
        weeks_to_keep = min(max_weeks, len(weeks))
        trimmed_weeks = weeks[-weeks_to_keep:]

        # Renumber weeks
        for i, week in enumerate(trimmed_weeks):
            week["week_number"] = i + 1

        # Recalculate start date with trimmed plan
        updated_start_date = self.calculate_start_date(
            race_date=race_date,
            plan_length_weeks=len(trimmed_weeks),
            min_start_date=start_date,
        )

        return trimmed_weeks, updated_start_date or start_date

    def get_min_start_date(self) -> date:
        """
        Get the minimum start date (week AFTER current week).

        This is the earliest date a plan can start, ensuring it's never in the past.

        Returns:
            Date object representing the Monday of the week after current week
        """
        today = datetime.now().date()
        return get_next_monday(today, include_today=False)

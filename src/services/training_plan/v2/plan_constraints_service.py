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
        generation_weeks: Optional[int] = None,
        fitness_recommended_weeks: Optional[int] = None,
    ):
        self.target_weeks = target_weeks
        self.available_weeks = available_weeks
        self.recommended_weeks = recommended_weeks
        self.min_start_date = min_start_date
        self.race_date = race_date
        self.generation_weeks = generation_weeks
        self.fitness_recommended_weeks = fitness_recommended_weeks

    def __repr__(self) -> str:
        return (
            f"PlanConstraints(target={self.target_weeks}, "
            f"available={self.available_weeks}, recommended={self.recommended_weeks}, "
            f"fitness={self.fitness_recommended_weeks})"
        )

    @property
    def structural_weeks(self) -> Optional[int]:
        """
        Single source of truth for plan generation length.

        Order of precedence:
        1. generation_weeks (explicitly calculated)
        2. target_weeks (final constrained length)
        3. recommended_weeks (fitness-based fallback)
        """
        return self.generation_weeks or self.target_weeks or self.recommended_weeks


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

    MIN_START_POLICY_CURRENT_WEEK = "current_week"
    MIN_START_POLICY_NEXT_WEEK = "next_week"

    def __init__(self, min_start_policy: str = MIN_START_POLICY_CURRENT_WEEK):
        """
        Initialize constraints service with a single configurable min-start policy.

        Args:
            min_start_policy:
                - "current_week": Monday starting the Mon–Sun week that contains "today" (default)
                - "next_week": Monday of the following calendar week (legacy behavior)
        """
        self.min_start_policy = min_start_policy

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

    def _resolve_min_start_date(
        self,
        reference_date: Optional[date] = None,
        user_timezone: Optional[str] = None,
    ) -> date:
        """Resolve min start date from configured policy."""
        if reference_date is not None:
            today = reference_date
        elif user_timezone:
            from src.utils.timezone_helpers import get_today_date_in_timezone

            today = get_today_date_in_timezone(user_timezone)
        else:
            today = datetime.now().date()

        if self.min_start_policy == self.MIN_START_POLICY_CURRENT_WEEK:
            return get_week_start_for_date(today)

        if self.min_start_policy == self.MIN_START_POLICY_NEXT_WEEK:
            return get_next_monday(today, include_today=False)

        raise ValueError(
            f"Unknown min_start_policy='{self.min_start_policy}'. "
            f"Supported: {self.MIN_START_POLICY_CURRENT_WEEK}, "
            f"{self.MIN_START_POLICY_NEXT_WEEK}"
        )

    def calculate_available_weeks(
        self,
        *,
        race_date: Any,
        min_start_date: Optional[date] = None,
    ) -> Optional[int]:
        """
        Calculate available training weeks from race date.

        This is used BEFORE the selector makes its recommendation, so the selector
        can consider available time when making its decision.

        Args:
            race_date: Race date (any format)
            min_start_date: Minimum start date (if None, calculates from today)

        Returns:
            Available training weeks (None if no race_date), or None if race_date invalid
        """
        if min_start_date is None:
            min_start_date = self.get_min_start_date()

        if not race_date:
            return None

        race_d = self._parse_date(race_date)
        if not race_d:
            return None

        race_week_start = get_week_start_for_date(race_d)
        days_to_race = (race_week_start - min_start_date).days

        # Calculate available training weeks (race week is added separately later)
        # Use integer division: days_to_race // 7 gives training weeks
        available_weeks = max(1, days_to_race // 7)

        logger.info(
            f"📅 Available weeks calculation: {available_weeks} weeks "
            f"(race_date={race_d.isoformat()}, min_start={min_start_date.isoformat()}, "
            f"days_to_race={days_to_race})"
        )

        return available_weeks

    def calculate_plan_constraints(
        self,
        *,
        race_date: Any,
        recommended_weeks: int,
        min_start_date: Optional[date] = None,
    ) -> PlanConstraints:
        """
        Calculate plan constraints for validation and date alignment.

        NOTE: Plan length is chosen upstream by the orchestrator (calendar + fitness).
        This method primarily validates and stores values for date alignment.

        Args:
            race_date: Race date (any format)
            recommended_weeks: Time-aware recommended plan length (from selector)
            min_start_date: Minimum start date (if None, calculates from today)

        Returns:
            PlanConstraints with validated constraints
        """
        if min_start_date is None:
            min_start_date = self.get_min_start_date()

        # recommended_weeks already includes time-aware adjustment from selector
        target_weeks = recommended_weeks
        generation_weeks = recommended_weeks
        available_weeks = None
        race_d = None

        if race_date:
            race_d = self._parse_date(race_date)
            if race_d:
                # Calculate available_weeks for validation (should match selector's calculation)
                available_weeks = self.calculate_available_weeks(
                    race_date=race_date,
                    min_start_date=min_start_date,
                )

                # Validate that recommended_weeks doesn't exceed available_weeks
                if available_weeks is not None and recommended_weeks > available_weeks:
                    logger.warning(
                        f"⚠️ Recommended weeks ({recommended_weeks}) exceeds available weeks "
                        f"({available_weeks}). This should not happen if selector logic is correct. "
                        f"Using available_weeks as constraint."
                    )
                    target_weeks = available_weeks
                    generation_weeks = available_weeks
                else:
                    # recommended_weeks is valid (<= available_weeks or no constraint)
                    target_weeks = recommended_weeks
                    generation_weeks = recommended_weeks

        # Store recommended_weeks as-is (selector already made the decision)
        # fitness_recommended_weeks is stored separately in orchestrator
        return PlanConstraints(
            target_weeks=target_weeks,
            available_weeks=available_weeks,
            recommended_weeks=recommended_weeks,
            min_start_date=min_start_date,
            race_date=race_d,
            generation_weeks=generation_weeks,
            fitness_recommended_weeks=recommended_weeks,  # Will be overridden by orchestrator if needed
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
        2. Enforce configured minimum start policy (current-week or next-week Monday)
        3. Fallback to provided start_date if available
        4. Default to minimum start policy if all else fails

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
            min_start_date = self.get_min_start_date()

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

        # Priority: Start as soon as allowed by min-start policy when there's enough time
        # Strategy: Use min_start_date when there's enough time, then adjust dates forward to align race week
        if calculated_start:
            race_week_start = get_week_start_for_date(race_d) if race_d else None
            if race_week_start:
                # Calculate where the race week would be if we start on min_start_date
                plan_end_from_min_start = min_start_date + timedelta(
                    weeks=plan_length_weeks - 1
                )

                logger.info(
                    f"Date check: min_start={min_start_date}, plan_length={plan_length_weeks}, "
                    f"plan_end_from_min_start={plan_end_from_min_start}, race_week_start={race_week_start}"
                )

                # If starting on min_start_date would end before or on the race week, use min_start_date
                # The date adjustment code will align the race week later
                if plan_end_from_min_start <= race_week_start:
                    # Starting on minimum start date fits - use it (start as soon as possible)
                    start_date = min_start_date
                    logger.info(
                        f"✅ Using minimum start date {min_start_date} - "
                        f"plan fits before race week {race_week_start} "
                        f"(plan would end on {plan_end_from_min_start}, race week starts {race_week_start}). "
                        f"Dates will be adjusted forward to align race week."
                    )
                else:
                    # Plan wouldn't fit - must use calculated start to align with race
                    start_date = max(calculated_start, min_start_date)
                    logger.info(
                        f"⚠️ Using calculated start {calculated_start} to ensure plan fits before race. "
                        f"Adjusted to {start_date} (max of calculated and min_start). "
                        f"Reason: plan_end_from_min_start ({plan_end_from_min_start}) > race_week_start ({race_week_start})"
                    )
            else:
                # No race date - use calculated start if available, otherwise min_start
                start_date = (
                    max(calculated_start, min_start_date)
                    if calculated_start
                    else min_start_date
                )
        else:
            parsed_fallback = self._parse_date(fallback_start)
            if parsed_fallback:
                start_date = parsed_fallback
            else:
                # Default to minimum start date policy
                start_date = min_start_date

        # CRITICAL: Ensure start date is never in the past
        if start_date < min_start_date:
            logger.warning(
                f"Start date {start_date} is in the past. "
                f"Adjusting to minimum start date: {min_start_date}"
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

    def align_weeks_with_dates(
        self,
        weeks: List[Dict[str, Any]],
        *,
        race_date: Any,
        min_start_date: date,
        fallback_start: Any = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[date]]:
        """
        Centralized date alignment workflow:
        1. Calculate start date using actual plan length
        2. Trim weeks if they exceed race date constraints
        3. Assign sequential week_start_date/week_label values
        4. Adjust all weeks so the final week aligns with the race week
        """
        if not weeks:
            return weeks, None

        actual_plan_length = len(weeks)
        aligned_start_date = self.calculate_start_date(
            race_date=race_date,
            plan_length_weeks=actual_plan_length,
            min_start_date=min_start_date,
            fallback_start=fallback_start,
        )

        if not aligned_start_date:
            return weeks, None

        weeks_aligned, aligned_start_date = self.trim_plan_to_constraints(
            weeks=weeks,
            race_date=race_date,
            start_date=aligned_start_date,
        )

        current = aligned_start_date
        for week in weeks_aligned:
            week["week_start_date"] = current.isoformat()
            week["week_label"] = current.strftime("%Y-%m-%d")
            current += timedelta(days=7)

        if race_date:
            race_d = self._parse_date(race_date)
            if race_d:
                race_week_start = get_week_start_for_date(race_d)
                last_week_start = weeks_aligned[-1].get("week_start_date")
                if last_week_start:
                    last_week_date = datetime.fromisoformat(last_week_start).date()
                    if last_week_date != race_week_start:
                        date_offset = (race_week_start - last_week_date).days
                        logger.info(
                            f"Adjusting plan dates by {date_offset} days to align race week "
                            f"({last_week_date}) with race date week ({race_week_start})"
                        )
                        for week in weeks_aligned:
                            current_date = datetime.fromisoformat(
                                week["week_start_date"]
                            ).date()
                            adjusted_date = current_date + timedelta(days=date_offset)
                            week["week_start_date"] = adjusted_date.isoformat()
                            week["week_label"] = adjusted_date.strftime("%Y-%m-%d")

                        aligned_start_date = datetime.fromisoformat(
                            weeks_aligned[0]["week_start_date"]
                        ).date()

        return weeks_aligned, aligned_start_date

    def get_min_start_date(
        self,
        reference_date: Optional[date] = None,
        user_timezone: Optional[str] = None,
    ) -> date:
        """
        Get the minimum start date from configured policy.

        This is the earliest date a plan can start based on current policy.

        Args:
            reference_date: Optional fixed calendar date (tests / deterministic callers).
            user_timezone: Optional IANA timezone; when set (and reference_date is None),
                "today" is resolved in that zone for current-week policy.

        Returns:
            Date object representing policy-selected Monday boundary
        """
        return self._resolve_min_start_date(
            reference_date=reference_date, user_timezone=user_timezone
        )

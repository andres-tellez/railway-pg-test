"""
Race Date Validation Service

Validates if a user has sufficient time and base fitness to safely prepare
for a marathon by a given race date.

Based on established running methodologies:
- Pfitzinger, Hanson, Higdon, BAA, McMillan
- Research-backed baseline fitness requirements
- Safe progression rules (10% weekly increase, cutbacks every 3-4 weeks)
"""

from typing import Dict, Any, Optional
from datetime import date, datetime, timedelta
import logging

from .race_configs.base_config import RaceDistanceConfig

logger = logging.getLogger(__name__)


class RaceDateValidationService:
    """Validates race date readiness based on user's current fitness and available time."""

    def __init__(self, config: RaceDistanceConfig):
        """
        Initialize validation service with race distance configuration.
        
        Args:
            config: Race distance configuration containing validation thresholds
        """
        self.config = config

    def validate(
        self,
        race_date: Any,
        plan_start_date: Any,
        current_weekly_mileage: float,
        current_long_run: float,
    ) -> Dict[str, Any]:
        """
        Validate if user has sufficient time and base fitness for marathon training.

        Args:
            race_date: Target race date (str ISO, date, or datetime)
            plan_start_date: Plan start date (str ISO, date, or datetime, or None to calculate)
            current_weekly_mileage: User's current average weekly mileage
            current_long_run: User's current longest run distance (miles)

        Returns:
            {
                "status": "approve" | "reject" | "warn",
                "message": str,  # User-friendly message
                "available_weeks": int,
                "required_weeks": int,
                "ready_date": Optional[date],  # When they'll actually be ready
                "can_proceed": bool,  # Can still create plan?
                "recommendation": str,
                "fitness_summary": {
                    "current_weekly_mileage": float,
                    "current_long_run": float,
                },
                "timeline_gap_weeks": Optional[int],  # Negative if late, positive if early
            }
        """
        # Parse dates
        race_d = self._parse_date(race_date)
        if not race_d:
            return self._error_result("Invalid race date provided")

        # Calculate required weeks first (needed for start_date calculation)
        calculated_required_weeks = self._estimate_weeks_to_peak(current_long_run)

        # Calculate start_date: align with race_date by working backwards
        # This matches the orchestrator's logic for consistency
        start_d = self._parse_date(plan_start_date)
        if not start_d:
            # Calculate start_date aligned with race_date (same logic as orchestrator)
            from src.utils.date_helpers import get_week_start_for_date, get_next_monday

            today = datetime.now().date()
            min_start_date = get_next_monday(
                today, include_today=False
            )  # Week after current week

            # Calculate backwards from race_date
            race_week_start = get_week_start_for_date(race_d)
            # Use calculated_required_weeks to estimate plan length
            offset_weeks = max(0, calculated_required_weeks - 1)
            calculated_start = race_week_start - timedelta(weeks=offset_weeks)

            # Ensure start_date is not in the past (use later of calculated or minimum)
            start_d = (
                max(calculated_start, min_start_date)
                if calculated_start
                else min_start_date
            )

        # Calculate available weeks (now using aligned start_date)
        available_weeks = self._calculate_available_weeks(race_d, start_d)

        if available_weeks <= 0:
            return self._error_result(
                f"Race date ({race_d.isoformat()}) is before or same as plan start date ({start_d.isoformat()})"
            )

        # If available_weeks < min_training_weeks, use min_training_weeks as the absolute minimum
        # (calculated_required_weeks already calculated above)
        # This ensures consistency in messaging - when rejecting due to <min_training_weeks,
        # we should say "need {min_training_weeks} weeks" everywhere, not the calculated value
        min_weeks = self.config.min_training_weeks
        if available_weeks < min_weeks:
            required_weeks = min_weeks  # Absolute minimum for training
            # Recalculate start_date to align with race_date using min_training_weeks
            # This ensures ready_date matches what we're telling the user
            from src.utils.date_helpers import get_week_start_for_date

            race_week_start = get_week_start_for_date(race_d)
            offset_weeks = max(0, min_weeks - 1)
            recalculated_start = race_week_start - timedelta(weeks=offset_weeks)
            # Ensure not in the past
            from src.utils.date_helpers import get_next_monday

            today = datetime.now().date()
            min_start_date = get_next_monday(today, include_today=False)
            start_d = (
                max(recalculated_start, min_start_date)
                if recalculated_start
                else min_start_date
            )
            # Recalculate available_weeks with new start_date
            available_weeks = self._calculate_available_weeks(race_d, start_d)
        else:
            required_weeks = calculated_required_weeks  # Use calculated value

        # Calculate ready date (required_weeks already includes taper, so no need to add more)
        ready_date = start_d + timedelta(weeks=required_weeks)
        timeline_gap_weeks = available_weeks - required_weeks

        # Special case: If available_weeks == strong_base_exception_weeks with strong base, user can proceed
        # In this case, ready_date should be the race_date (they'll be ready by race day)
        # We need to cap it BEFORE building the message so the message shows the correct date
        strong_base = (
            current_weekly_mileage >= self.config.strong_base_weekly_mileage
            and current_long_run >= self.config.strong_base_long_run
        )
        exception_weeks = self.config.strong_base_exception_weeks
        if available_weeks == exception_weeks and strong_base and ready_date > race_d:
            ready_date = race_d

        # Validate (values are already rounded from get_weekly_fitness_from_materialized_view)
        validation_result = self._validate_against_requirements(
            available_weeks=available_weeks,
            required_weeks=required_weeks,
            current_weekly_mileage=current_weekly_mileage,
            current_long_run=current_long_run,
            race_date=race_d,
            plan_start_date=start_d,
            optimal_ready_date=ready_date,  # Now this will be race_d for 11-week case
        )

        # Also cap for other can_proceed=True cases (defensive check)
        if validation_result.get('can_proceed', False) and ready_date > race_d:
            ready_date = race_d

        # Build result (use values as-is - already rounded from helper function)
        result = {
            **validation_result,
            "available_weeks": available_weeks,
            "required_weeks": required_weeks,
            "ready_date": ready_date.isoformat() if ready_date else None,
            "fitness_summary": {
                "current_weekly_mileage": current_weekly_mileage,
                "current_long_run": current_long_run,
            },
            "timeline_gap_weeks": timeline_gap_weeks,
            "race_date": race_d.isoformat(),
            "plan_start_date": start_d.isoformat(),
        }

        return result

    def _parse_date(self, date_input: Any) -> Optional[date]:
        """Parse various date formats to date object."""
        if date_input is None:
            return None

        if isinstance(date_input, date):
            return date_input
        if isinstance(date_input, datetime):
            return date_input.date()

        if isinstance(date_input, str):
            try:
                # Try ISO format first
                if "T" in date_input:
                    return datetime.fromisoformat(date_input).date()
                return datetime.fromisoformat(date_input).date()
            except ValueError:
                try:
                    # Try common formats
                    return datetime.strptime(date_input, "%Y-%m-%d").date()
                except ValueError:
                    pass

        return None

    def _calculate_available_weeks(self, race_date: date, start_date: date) -> int:
        """Calculate available weeks until race date."""
        delta = race_date - start_date
        weeks = delta.days / 7.0
        # Use round() instead of int() to avoid truncation issues
        # e.g., 11.86 weeks should round to 12, not truncate to 11
        return max(0, round(weeks))

    def _estimate_weeks_to_peak(
        self, current_long_run: float, target_peak: float = 20.0
    ) -> int:
        """
        Estimate weeks needed to reach peak long run (20 miles).

        Based on safe progression:
        - +1 mile/week progression
        - Cutback every 4th week (25% reduction)
        - Resume after cutback (+2 miles from cutback)
        - Starting point: current_long_run + 1.0 mile (Week 1)

        Example (starting at 16 miles):
        - Week 1: 16 -> 17 (+1)
        - Week 2: 17 -> 18 (+1)
        - Week 3: 18 -> 19 (+1)
        - Week 4: Cutback ~14.25 (19 * 0.75)
        - Week 5: Resume ~16 (+2 from 14.25)
        - Week 6: 16 -> 17 (+1)
        - Week 7: 17 -> 18 (+1)
        - Week 8: Cutback ~13.5 (18 * 0.75)
        ... continues

        Conservative estimate accounting for cutbacks:
        - Effective progression: ~0.75 miles per week (accounting for cutbacks)
        - Distance to cover: 20 - (current_long_run + 1)
        """
        if current_long_run >= 19.0:
            # Already close to peak, just need taper
            return 2

        start_lr = current_long_run + 1.0  # Week 1 long run
        distance_to_cover = target_peak - start_lr

        if distance_to_cover <= 0:
            # Already at or above target
            return 2

        # Conservative estimate: account for cutbacks every 4 weeks
        # Effective progression: ~0.6-0.75 miles/week due to cutback losses
        # Add 3 weeks for taper
        effective_weekly_progress = 0.7  # Conservative estimate
        build_weeks = max(6, int(distance_to_cover / effective_weekly_progress))
        taper_weeks = 3

        return build_weeks + taper_weeks

    def _validate_against_requirements(
        self,
        available_weeks: int,
        required_weeks: int,
        current_weekly_mileage: float,
        current_long_run: float,
        race_date: date,
        plan_start_date: date,
        optimal_ready_date: date,
    ) -> Dict[str, Any]:
        """
        Validate against research-based requirements from config.

        Thresholds are defined in RaceDistanceConfig.fitness_requirements_by_weeks
        and other validation properties. This makes the validation race-distance-aware.
        """
        # Absolute minimums
        # If available_weeks < min_training_weeks, use min_training_weeks as the required_weeks
        # However, for runners with strong bases, allow strong_base_exception_weeks with warning
        # This makes the validation fitness-aware rather than strictly calendar-based
        min_weeks = self.config.min_training_weeks
        if available_weeks < min_weeks:
            # Check if runner has strong enough base to safely do exception_weeks
            strong_base = (
                current_weekly_mileage >= self.config.strong_base_weekly_mileage
                and current_long_run >= self.config.strong_base_long_run
            )
            exception_weeks = self.config.strong_base_exception_weeks

            if available_weeks == exception_weeks and strong_base:
                # Strong runners can safely do exception_weeks - warn but allow
                message = self._build_message_with_structure(
                    status="warn",
                    available_weeks=available_weeks,
                    required_weeks=min_weeks,  # Still recommend min_weeks, but allow exception_weeks
                    current_weekly_mileage=current_weekly_mileage,
                    current_long_run=current_long_run,
                    race_date=race_date,
                    plan_start_date=plan_start_date,
                    optimal_ready_date=optimal_ready_date,
                    reason="strong_base_11_weeks_allowed",
                )
                return self._warn_result(message, can_proceed=True)
            else:
                # Weak base or <exception_weeks: hard minimum of min_training_weeks
                absolute_minimum_weeks = min_weeks
                message = self._build_message_with_structure(
                    status="reject",
                    available_weeks=available_weeks,
                    required_weeks=absolute_minimum_weeks,  # Use min_weeks, not calculated value
                    current_weekly_mileage=current_weekly_mileage,
                    current_long_run=current_long_run,
                    race_date=race_date,
                    plan_start_date=plan_start_date,
                    optimal_ready_date=optimal_ready_date,
                )
                return self._reject_result(message, can_proceed=False)

        if current_weekly_mileage < self.config.absolute_min_weekly_mileage:
            message = self._build_message_with_structure(
                status="reject",
                available_weeks=available_weeks,
                required_weeks=required_weeks,
                current_weekly_mileage=current_weekly_mileage,
                current_long_run=current_long_run,
                race_date=race_date,
                plan_start_date=plan_start_date,
                optimal_ready_date=optimal_ready_date,
                reason="insufficient_weekly_mileage",
            )
            return self._reject_result(message, can_proceed=False)

        if current_long_run < self.config.absolute_min_long_run:
            message = self._build_message_with_structure(
                status="reject",
                available_weeks=available_weeks,
                required_weeks=required_weeks,
                current_weekly_mileage=current_weekly_mileage,
                current_long_run=current_long_run,
                race_date=race_date,
                plan_start_date=plan_start_date,
                optimal_ready_date=optimal_ready_date,
                reason="insufficient_long_run",
            )
            return self._reject_result(message, can_proceed=False)

        # Check week range requirements from config
        reqs = self.config.fitness_requirements_by_weeks
        min_weeks = self.config.min_training_weeks

        # 12-14 weeks: Need strong base
        if min_weeks <= available_weeks < 14:
            range_reqs = reqs.get("12_14", {})
            min_mpw = range_reqs.get("min_weekly_mileage", 30.0)
            min_lr = range_reqs.get("min_long_run", 10.0)
            warn_mpw = range_reqs.get("warn_weekly_mileage")
            warn_lr = range_reqs.get("warn_long_run")

            if current_weekly_mileage < min_mpw or current_long_run < min_lr:
                message = self._build_message_with_structure(
                    status="reject",
                    available_weeks=available_weeks,
                    required_weeks=required_weeks,
                    current_weekly_mileage=current_weekly_mileage,
                    current_long_run=current_long_run,
                    race_date=race_date,
                    plan_start_date=plan_start_date,
                    optimal_ready_date=optimal_ready_date,
                )
                return self._reject_result(message, can_proceed=True)
            elif warn_mpw and warn_lr and (current_weekly_mileage < warn_mpw or current_long_run < warn_lr):
                message = self._build_message_with_structure(
                    status="warn",
                    available_weeks=available_weeks,
                    required_weeks=required_weeks,
                    current_weekly_mileage=current_weekly_mileage,
                    current_long_run=current_long_run,
                    race_date=race_date,
                    plan_start_date=plan_start_date,
                    optimal_ready_date=optimal_ready_date,
                )
                return self._warn_result(message, can_proceed=True)

        # 14-16 weeks: Need moderate base
        if 14 <= available_weeks < 16:
            range_reqs = reqs.get("14_16", {})
            min_mpw = range_reqs.get("min_weekly_mileage", 25.0)
            min_lr = range_reqs.get("min_long_run", 8.0)

            if current_weekly_mileage < min_mpw or current_long_run < min_lr:
                message = self._build_message_with_structure(
                    status="reject",
                    available_weeks=available_weeks,
                    required_weeks=required_weeks,
                    current_weekly_mileage=current_weekly_mileage,
                    current_long_run=current_long_run,
                    race_date=race_date,
                    plan_start_date=plan_start_date,
                    optimal_ready_date=optimal_ready_date,
                )
                return self._reject_result(message, can_proceed=True)

        # 16-18 weeks: Need minimum base
        if 16 <= available_weeks < 18:
            range_reqs = reqs.get("16_18", {})
            min_mpw = range_reqs.get("min_weekly_mileage", 20.0)
            min_lr = range_reqs.get("min_long_run", 6.0)

            if current_weekly_mileage < min_mpw or current_long_run < min_lr:
                message = self._build_message_with_structure(
                    status="warn",
                    available_weeks=available_weeks,
                    required_weeks=required_weeks,
                    current_weekly_mileage=current_weekly_mileage,
                    current_long_run=current_long_run,
                    race_date=race_date,
                    plan_start_date=plan_start_date,
                    optimal_ready_date=optimal_ready_date,
                )
                return self._warn_result(message, can_proceed=True)

        # 18+ weeks: More flexible
        if available_weeks >= 18:
            range_reqs = reqs.get("18_plus", {})
            min_mpw = range_reqs.get("min_weekly_mileage", 20.0)
            min_lr = range_reqs.get("min_long_run", 6.0)

            if current_weekly_mileage < min_mpw or current_long_run < min_lr:
                message = self._build_message_with_structure(
                    status="warn",
                    available_weeks=available_weeks,
                    required_weeks=required_weeks,
                    current_weekly_mileage=current_weekly_mileage,
                    current_long_run=current_long_run,
                    race_date=race_date,
                    plan_start_date=plan_start_date,
                    optimal_ready_date=optimal_ready_date,
                )
                return self._warn_result(message, can_proceed=True)

        # All checks passed - APPROVE
        message = self._build_message_with_structure(
            status="approve",
            available_weeks=available_weeks,
            required_weeks=required_weeks,
            current_weekly_mileage=current_weekly_mileage,
            current_long_run=current_long_run,
            race_date=race_date,
            plan_start_date=plan_start_date,
            optimal_ready_date=optimal_ready_date,
        )
        return self._approve_result(message)

    def _approve_result(self, message: str) -> Dict[str, Any]:
        """Build approve result."""
        return {
            "status": "approve",
            "message": message,
            "can_proceed": True,
            "recommendation": "Proceed with plan generation",
        }

    def _warn_result(self, message: str, can_proceed: bool = True) -> Dict[str, Any]:
        """Build warn result."""
        return {
            "status": "warn",
            "message": message,
            "can_proceed": can_proceed,
            "recommendation": "Proceed with caution or adjust race date",
        }

    def _reject_result(self, message: str, can_proceed: bool = False) -> Dict[str, Any]:
        """Build reject result."""
        return {
            "status": "reject",
            "message": message,
            "can_proceed": can_proceed,
            "recommendation": "Adjust race date or build base fitness first",
        }

    def _error_result(self, message: str) -> Dict[str, Any]:
        """Build error result."""
        return {
            "status": "error",
            "message": message,
            "can_proceed": False,
            "recommendation": "Fix the error and try again",
        }

    def _build_message_with_structure(
        self,
        status: str,
        available_weeks: int,
        required_weeks: int,
        current_weekly_mileage: float,
        current_long_run: float,
        race_date: date,
        plan_start_date: date,
        optimal_ready_date: date,
        reason: Optional[str] = None,
    ) -> str:
        """
        Build compact, focused message.
        Structure: Combined Status → When Ready → Brief Why → Options
        """
        # 1. COMBINED STATUS (includes key numbers in one line)
        status_line = self._build_combined_status(
            status,
            available_weeks,
            required_weeks,
            current_weekly_mileage,
            current_long_run,
            reason,
        )

        # 2. WHEN READY (prominent, this is what they really care about)
        when_ready = self._build_compact_when_ready(optimal_ready_date, plan_start_date)

        # 3. BRIEF WHY (only if rejecting/warning, max 1-2 lines)
        brief_why = self._build_brief_why(
            status, available_weeks, required_weeks, reason
        )

        # 4. OPTIONS (clear and concise, references ready date above)
        # Skip options for strong runners with 11 weeks or when user has adequate time - they can proceed safely
        options = self._build_compact_options(
            status, optimal_ready_date, reason, available_weeks, required_weeks
        )

        # Combine components
        components = [status_line, when_ready]
        if brief_why:
            components.append(brief_why)
        if options:  # Only add options if they exist
            components.append(options)

        return "\n\n".join(components)

    def _build_combined_status(
        self,
        status: str,
        available_weeks: int,
        required_weeks: int,
        weekly_mileage: float,
        long_run: float,
        reason: Optional[str] = None,
    ) -> str:
        """One-line status followed by fitness section with bullets."""
        # If user has adequate time (available >= required), message should be positive
        # even if status is "warn" (warning might be about fitness, not time)
        if available_weeks >= required_weeks:
            # When user has adequate time, always show positive, confident message
            status_line = "✅ **You're all set!** — You have sufficient time and fitness for marathon training."
        elif status == "reject" or status == "warn":
            gap = abs(available_weeks - required_weeks)
            if available_weeks < required_weeks:
                if status == "warn" and reason == "strong_base_11_weeks_allowed":
                    # Special case: Strong runners allowed 11 weeks - positive message since they can proceed safely
                    status_line = f"✅ **You're ready to proceed** — You have {available_weeks} weeks (ideal is {required_weeks} weeks), and your strong base allows you to train safely."
                else:
                    status_line = f"⚠️ **Not enough time** — You have {available_weeks} weeks but need {required_weeks} weeks."
            else:
                status_line = f"⚠️ **Tight timeline** — You have {available_weeks} weeks, which is {gap} weeks more than the minimum."
        else:
            status_line = "✅ **You're all set!** — You have sufficient time and fitness for marathon training."

        fitness_section = f"""**Current Fitness:**
• Miles per week: {weekly_mileage:.1f}
• Long run: {long_run:.1f}"""

        return f"{status_line}\n\n{fitness_section}"

    def _build_compact_when_ready(
        self, optimal_ready_date: date, plan_start_date: date
    ) -> str:
        """When they'll be ready - the key question."""
        ready_date_str = optimal_ready_date.strftime("%B %d, %Y")

        return f"**📅 You'll be ready:** {ready_date_str}"

    def _build_brief_why(
        self,
        status: str,
        available_weeks: int,
        required_weeks: int,
        reason: Optional[str] = None,
    ) -> str:
        """Brief explanation - only if rejecting/warning, max 1-2 lines."""
        if status == "approve":
            return ""

        if reason == "insufficient_weekly_mileage":
            min_mpw = self.config.absolute_min_weekly_mileage
            return f"**Why:** Your body needs a base of {min_mpw:.0f}+ mpw to safely handle marathon training volume and reduce injury risk."

        if reason == "insufficient_long_run":
            min_lr = self.config.absolute_min_long_run
            return f"**Why:** A {min_lr:.0f}+ mile long run base ensures your muscles and body are ready for the progression ahead."

        if reason == "strong_base_11_weeks_allowed":
            # Skip "Why" section - the status line already explains this clearly
            return ""

        min_weeks = self.config.min_training_weeks
        if available_weeks < min_weeks:
            return f"**Why:** {min_weeks} weeks is the minimum because your body needs time for bone/tendon strengthening, cardiovascular adaptation, safe long run progression, and taper."

        if available_weeks < required_weeks:
            return f"**Why:** Building from your current fitness to marathon-ready requires {required_weeks} weeks, including gradual progression, recovery weeks, and taper."

        return ""

    def _build_compact_options(
        self,
        status: str,
        optimal_ready_date: date,
        reason: Optional[str] = None,
        available_weeks: Optional[int] = None,
        required_weeks: Optional[int] = None,
    ) -> str:
        """Clear, concise options."""
        if status == "approve":
            return "**Next:** Your training plan is ready to review!"

        # For strong runners with 11 weeks, skip options - they can proceed safely
        if reason == "strong_base_11_weeks_allowed":
            return "**Next:** Your training plan is ready to review!"

        # If user has adequate time (available >= required), they can proceed - no options needed
        if available_weeks is not None and required_weeks is not None:
            if available_weeks >= required_weeks:
                return "**Next:** Your training plan is ready to review!"

        ready_date_str = optimal_ready_date.strftime("%B %d, %Y")
        return f"""**Your Options:**
• Create plan anyway (will show when you'll actually be ready)
• Adjust race date to {ready_date_str} or later
• Build your base first, then regenerate your plan"""

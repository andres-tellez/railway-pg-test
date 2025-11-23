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

logger = logging.getLogger(__name__)


class RaceDateValidationService:
    """Validates race date readiness based on user's current fitness and available time."""

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

        # If available_weeks < 12, use 12 as the absolute minimum (research-backed)
        # (calculated_required_weeks already calculated above)
        # This ensures consistency in messaging - when rejecting due to <12 weeks,
        # we should say "need 12 weeks" everywhere, not the calculated value
        if available_weeks < 12:
            required_weeks = 12  # Absolute minimum for any marathon training
            # Recalculate start_date to align with race_date using 12 weeks
            # This ensures ready_date matches what we're telling the user
            from src.utils.date_helpers import get_week_start_for_date

            race_week_start = get_week_start_for_date(race_d)
            offset_weeks = max(0, required_weeks - 1)
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

        # Validate (values are already rounded from get_weekly_fitness_from_materialized_view)
        validation_result = self._validate_against_requirements(
            available_weeks=available_weeks,
            required_weeks=required_weeks,
            current_weekly_mileage=current_weekly_mileage,
            current_long_run=current_long_run,
            race_date=race_d,
            plan_start_date=start_d,
            optimal_ready_date=ready_date,
        )

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
        return max(0, int(weeks))

    def _estimate_weeks_to_peak(
        self, current_long_run: float, target_peak: float = 20.0
    ) -> int:
        """
        Estimate weeks needed to reach peak long run (20 miles).

        Based on safe progression:
        - +1 mile/week progression
        - Cutback every 4th week (30% reduction)
        - Resume after cutback (+2 miles from cutback)
        - Starting point: current_long_run + 1.0 mile (Week 1)

        Example (starting at 16 miles):
        - Week 1: 16 -> 17 (+1)
        - Week 2: 17 -> 18 (+1)
        - Week 3: 18 -> 19 (+1)
        - Week 4: Cutback ~13.3 (19 * 0.70)
        - Week 5: Resume ~15 (+2 from 13.3)
        - Week 6: 15 -> 16 (+1)
        - Week 7: 16 -> 17 (+1)
        - Week 8: Cutback ~11.9 (17 * 0.70)
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
        Validate against research-based requirements.

        Based on established methodologies:
        - <12 weeks: Not enough time (REJECT)
        - 12-14 weeks: Need 30+ mpw, 10+ mi LR (WARN/REJECT if lower)
        - 14-16 weeks: Need 25+ mpw, 8+ mi LR (REJECT if lower)
        - 16-18 weeks: Need 20+ mpw, 6+ mi LR (WARN if lower)
        - 18+ weeks: 15+ mpw, 5+ mi LR acceptable (WARN if lower)
        """
        # Absolute minimums
        # If available_weeks < 12, use 12 as the required_weeks (research-backed absolute minimum)
        # However, for runners with strong bases (30+ mpw, 10+ mi LR), allow 11 weeks with warning
        # This makes the validation fitness-aware rather than strictly calendar-based
        if available_weeks < 12:
            # Check if runner has strong enough base to safely do 11 weeks
            strong_base = current_weekly_mileage >= 30 and current_long_run >= 10

            if available_weeks == 11 and strong_base:
                # Strong runners can safely do 11 weeks - warn but allow
                message = self._build_message_with_structure(
                    status="warn",
                    available_weeks=available_weeks,
                    required_weeks=12,  # Still recommend 12, but allow 11
                    current_weekly_mileage=current_weekly_mileage,
                    current_long_run=current_long_run,
                    race_date=race_date,
                    plan_start_date=plan_start_date,
                    optimal_ready_date=optimal_ready_date,
                    reason="strong_base_11_weeks_allowed",
                )
                return self._warn_result(message, can_proceed=True)
            else:
                # Weak base or <11 weeks: hard minimum of 12 weeks
                absolute_minimum_weeks = 12
                message = self._build_message_with_structure(
                    status="reject",
                    available_weeks=available_weeks,
                    required_weeks=absolute_minimum_weeks,  # Use 12, not calculated value
                    current_weekly_mileage=current_weekly_mileage,
                    current_long_run=current_long_run,
                    race_date=race_date,
                    plan_start_date=plan_start_date,
                    optimal_ready_date=optimal_ready_date,
                )
                return self._reject_result(message, can_proceed=False)

        if current_weekly_mileage < 15:
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

        if current_long_run < 5:
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

        # 12-14 weeks: Need strong base
        if 12 <= available_weeks < 14:
            if current_weekly_mileage < 30 or current_long_run < 10:
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
            elif current_weekly_mileage < 35 or current_long_run < 12:
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
            if current_weekly_mileage < 25 or current_long_run < 8:
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
            if current_weekly_mileage < 20 or current_long_run < 6:
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
            if current_weekly_mileage < 20 or current_long_run < 6:
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
        # Skip options for strong runners with 11 weeks - they can proceed safely
        options = self._build_compact_options(status, optimal_ready_date, reason)

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
        if status == "reject" or status == "warn":
            gap = abs(available_weeks - required_weeks)
            if available_weeks < required_weeks:
                if status == "warn" and reason == "strong_base_11_weeks_allowed":
                    # Special case: Strong runners allowed 11 weeks with warning
                    status_line = f"⚠️ **Tight timeline** — You have {available_weeks} weeks (ideal is {required_weeks} weeks), but your strong base allows you to proceed safely."
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
            return "**Why:** Your body needs a base of 15+ mpw to safely handle marathon training volume and reduce injury risk."

        if reason == "insufficient_long_run":
            return "**Why:** A 5+ mile long run base ensures your muscles and body are ready for the progression ahead."

        if reason == "strong_base_11_weeks_allowed":
            return "**Why:** While 12 weeks is ideal, your strong base (30+ mpw, 10+ mi long run) allows you to safely proceed with 11 weeks. Still, be extra mindful of recovery and listen to your body."

        if available_weeks < 12:
            return "**Why:** 12 weeks is the minimum because your body needs time for bone/tendon strengthening, cardiovascular adaptation, safe long run progression, and taper."

        if available_weeks < required_weeks:
            return f"**Why:** Building from your current fitness to marathon-ready requires {required_weeks} weeks, including gradual progression, recovery weeks, and taper."

        return ""

    def _build_compact_options(
        self, status: str, optimal_ready_date: date, reason: Optional[str] = None
    ) -> str:
        """Clear, concise options."""
        if status == "approve":
            return "**Next:** Your training plan is ready to review!"

        # For strong runners with 11 weeks, skip options - they can proceed safely
        if reason == "strong_base_11_weeks_allowed":
            return "**Next:** Your training plan is ready to review!"

        ready_date_str = optimal_ready_date.strftime("%B %d, %Y")
        return f"""**Your Options:**
• Create plan anyway (will show when you'll actually be ready)
• Adjust race date to {ready_date_str} or later
• Build your base first, then regenerate your plan"""

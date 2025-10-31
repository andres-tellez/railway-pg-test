"""
Layer 3: Prompt Builder Service

Purpose:
    Convert calculated insights into an optimized GPT prompt.
    Keep prompt lightweight (~800-1,000 words / ~1,200 tokens) using structured format.

Responsibilities:
    - Build system role definition
    - Structure insights into clean, readable format
    - Add conditional warnings based on risk factors
    - Specify JSON output schema for GPT

Dependencies:
    - Insights from Layer 2 (InsightsCalculationService)
    - User profile data
    - Plan request data

Testing:
    See tests/services/training_plan/test_prompt_builder_service.py

Author: SmartCoach Development Team
Last Updated: October 28, 2025
"""

import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)


class PromptBuilderService:
    """Service for building optimized GPT prompts from calculated insights."""

    @staticmethod
    def build_complete_prompt(
        insights: Dict[str, Any],
        user_profile: Dict[str, Any],
        plan_request: Dict[str, Any],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build complete prompt for GPT training plan generation.

        Args:
            insights: Output from Layer 2 InsightsCalculationService
            user_profile: User demographic and preference data
            plan_request: Plan creation request (race details, goals, etc.)

        Returns:
            Dictionary with GPT API request structure:
                {
                    "messages": [
                        {"role": "system", "content": "..."},
                        {"role": "user", "content": "..."}
                    ],
                    "config": {
                        "model": "gpt-4",
                        "response_format": {"type": "json_object"},
                        "temperature": 0.7
                    },
                    "metadata": {
                        "prompt_version": "v1.0",
                        "created_at": "2025-10-28T..."
                    }
                }
        """
        logger.info("Building GPT prompt for training plan generation")

        # Build system message (GPT's role and capabilities)
        system_message = PromptBuilderService._build_system_message()

        # Build user message (runner's data and request)
        user_message = PromptBuilderService._build_user_message(
            insights, user_profile, plan_request
        )

        # Resolve configuration with optional overrides and env fallbacks
        resolved_model = model or os.getenv("TRAINING_PLAN_GPT_MODEL") or "gpt-4"
        resolved_temperature = (
            temperature
            if temperature is not None
            else float(os.getenv("TRAINING_PLAN_GPT_TEMPERATURE", "0.7"))
        )
        resolved_response_format = response_format or {"type": "json_object"}

        # Assemble complete prompt
        return {
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            "config": {
                "model": resolved_model,
                "response_format": resolved_response_format,
                "temperature": resolved_temperature,
            },
            "metadata": {
                "prompt_version": "v1.0",
                "created_at": datetime.now().isoformat(),
                "data_quality": insights.get("metadata", {}).get(
                    "data_quality", "unknown"
                ),
            },
        }

    @staticmethod
    def _build_system_message() -> str:
        """
        Build the system message defining GPT's role as a running coach.

        Returns:
            System prompt string with role definition and guidelines
        """
        return """You are an elite marathon running coach that follows Jack Daniels methodology with 20+ years of experience helping runners finish a marathon safely."""

    @staticmethod
    def _build_user_message(
        insights: Dict[str, Any],
        user_profile: Dict[str, Any],
        plan_request: Dict[str, Any],
    ) -> str:
        """
        Build the user message with runner's data and training request.

        Args:
            insights: Layer 2 insights (fitness, recommendations)
            user_profile: User demographics
            plan_request: Race details and goals

        Returns:
            Formatted user prompt string
        """
        # Extract data
        current_fitness = insights.get("current_fitness", {})
        recommendations = insights.get("recommendations", {})
        metadata = insights.get("metadata", {})

        # Calculate weeks until race
        race_date_str = plan_request.get("race_date")
        weeks_until_race = PromptBuilderService._calculate_weeks_until_race(
            race_date_str
        )

        # Build prompt sections
        sections = []

        # Runner Profile Section
        sections.append(
            PromptBuilderService._build_runner_profile_section(
                user_profile, plan_request
            )
        )

        # Race Goal Section
        sections.append(
            PromptBuilderService._build_race_goal_section(
                plan_request, weeks_until_race
            )
        )

        # Current Fitness Section
        sections.append(
            PromptBuilderService._build_current_fitness_section(current_fitness)
        )

        # Training Recommendations Section
        sections.append(
            PromptBuilderService._build_recommendations_section(recommendations)
        )

        # Schedule Constraints Section
        sections.append(PromptBuilderService._build_schedule_section(plan_request))

        # Simple Constraints Section (high-level)
        sections.append(PromptBuilderService._build_simple_constraints_section())

        # Task Instructions Section
        sections.append(
            PromptBuilderService._build_task_section(weeks_until_race, plan_request)
        )

        # Output Format Section
        sections.append(PromptBuilderService._build_output_format_section())

        # No special considerations block (kept minimal)

        return "\n\n".join(sections)

    @staticmethod
    def _build_runner_profile_section(
        user_profile: Dict[str, Any], plan_request: Dict[str, Any]
    ) -> str:
        """Build runner profile section."""
        age_group = user_profile.get("age_group", "Unknown")
        height_feet = user_profile.get("height_feet", 0)
        height_inches = user_profile.get("height_inches", 0)
        weight = user_profile.get("weight", 0)
        motivation = user_profile.get("motivation")
        experience = plan_request.get("marathon_experience", "Unknown")

        # Handle motivation (will be single value soon)
        motivation_str = (
            motivation[0]
            if isinstance(motivation, list) and motivation
            else motivation or "Not specified"
        )

        return f"""# RUNNER PROFILE

Age Group: {age_group}
Height: {height_feet}'{height_inches}"
Weight: {weight} lbs
Marathon Experience: {experience}
Primary Motivation: {motivation_str}"""

    @staticmethod
    def _build_race_goal_section(
        plan_request: Dict[str, Any], weeks_until_race: int
    ) -> str:
        """Build race goal section."""
        race_date = plan_request.get("race_date", "Not specified")
        # race_name and race_location intentionally omitted to reduce noise
        primary_goal = plan_request.get("primary_goal", "Not specified")
        target_time = plan_request.get("target_time")
        notes = plan_request.get("notes", "")

        section = f"""# RACE GOAL

Race Date: {race_date} ({weeks_until_race} weeks available)
Primary Goal: {primary_goal}"""

        if target_time:
            section += f"\nTarget Time: {target_time}"

        if notes:
            section += f"\nRunner's Notes: {notes}"

        return section

    @staticmethod
    def _build_current_fitness_section(current_fitness: Dict[str, Any]) -> str:
        """Build current fitness section."""
        return f"""# CURRENT FITNESS

Weekly Mileage: {current_fitness.get('weekly_mileage', 0)} miles (last complete week)
Longest Recent Run: {current_fitness.get('longest_run', 0)} miles (last 12 weeks)
Average Pace: {current_fitness.get('average_pace', 'Unknown')}
Fitness Trend: {current_fitness.get('fitness_trend', 'Unknown')}"""

    @staticmethod
    def _build_recommendations_section(recommendations: Dict[str, Any]) -> str:
        """Build recommendations section."""
        starting_mileage = recommendations.get("starting_mileage", {})
        long_run = recommendations.get("long_run_distance", {})

        return f"""# TRAINING RECOMMENDATIONS

Starting Weekly Mileage: {starting_mileage.get('weekly_mileage', 0)} miles
Starting Long Run Distance: {long_run.get('distance', 0)} miles
"""

    @staticmethod
    def _build_constraints_section(recommendations: Dict[str, Any]) -> str:
        """Deprecated: constraints handled elsewhere or by validator."""
        return ""

    @staticmethod
    def _build_training_principles_section(recommendations: Dict[str, Any]) -> str:
        """Build training principles section."""
        principles = recommendations.get("training_principles", [])
        safety_guidelines = recommendations.get("safety_guidelines", [])

        principles_str = (
            "\n".join(f"- {p}" for p in principles)
            if principles
            else "- Follow standard marathon training principles"
        )
        safety_str = (
            "\n".join(f"- {s}" for s in safety_guidelines)
            if safety_guidelines
            else "- Prioritize safety and injury prevention"
        )

        return f"""# TRAINING PRINCIPLES

{principles_str}

# SAFETY GUIDELINES

{safety_str}"""

    @staticmethod
    def _build_simple_constraints_section() -> str:
        """Add a concise constraints note referencing JD methodology."""
        return """# CONSTRAINTS

Follow safety training constraints specified in Jack Daniels methodology (use conservative progression, appropriate cutbacks, and safe tapering).

Additionally:
- Long runs should be ~25–35% of total weekly mileage
- Do not exceed 20 miles for any long run
- Do not exceed 40 miles for total weekly mileage"""

    @staticmethod
    def _build_schedule_section(plan_request: Dict[str, Any]) -> str:
        """Build schedule constraints section."""
        training_days = plan_request.get("training_days", [])
        days_str = ", ".join(training_days) if training_days else "Flexible"

        return f"""# SCHEDULE CONSTRAINTS

Preferred Training Days: {days_str}
Days per Week: {len(training_days) if training_days else 'Flexible'}"""

    @staticmethod
    def _build_task_section(weeks_until_race: int, plan_request: Dict[str, Any]) -> str:
        """Build task instructions section."""
        primary_goal = plan_request.get("primary_goal", "Just Finish")

        return f"""# YOUR TASK

Create a {weeks_until_race}-week marathon training plan for this runner.

Key Requirements:
- Goal: {primary_goal}
- Weekly mileage: Maximum 10% increase per week
- Long runs: Increase by 1 mile per week (standard progression)
- Cutback weeks: Every 3-4 weeks, reduce mileage by 20-30%
- Peak long run: 18-22 miles, 3 weeks before race
- Taper: Final 2-3 weeks, reduce volume while maintaining intensity
- 80/20 intensity distribution: 80% easy runs, 20% quality workouts
- Include rest days and cross-training as appropriate
- Provide specific workout descriptions for each training day"""

    @staticmethod
    def _build_output_format_section() -> str:
        """Build JSON output format specification."""
        return """# OUTPUT FORMAT

Return your training plan as valid JSON with this exact structure:

{
  "plan_name": "Descriptive name for the plan",
  "plan_summary": "Brief overview of the training approach (2-3 sentences)",
  "weeks": [
    {
      "week_number": 1,
      "phase": "Base Building|Build|Peak|Taper",
      "weekly_mileage": 30.0,
      "week_notes": "General guidance for this week",
      "workouts": [
        {
          "day": "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday",
          "workout_type": "Easy Run|Long Run|Tempo Run|Interval|Rest|Cross-Training",
          "distance_miles": 5.0,
          "pace_guidance": "Easy pace (conversational)|Tempo pace|etc.",
          "workout_description": "Detailed instructions for this workout"
        }
      ]
    }
  ],
  "race_week_strategy": "Specific guidance for race week preparation"
}

IMPORTANT:
- Return ONLY valid JSON, no additional text
- Include all weeks from week 1 through race week
- Ensure every workout has specific, actionable guidance
- Make pace guidance relative (easy, moderate, tempo) not absolute numbers"""

    @staticmethod
    # Special considerations removed to keep prompt minimal

    @staticmethod
    def _calculate_weeks_until_race(race_date_str: str) -> int:
        """
        Calculate weeks between now and race date.

        Args:
            race_date_str: Race date in ISO format (YYYY-MM-DD)

        Returns:
            Number of weeks until race (minimum 1)
        """
        if not race_date_str:
            return 16  # Default to 16 weeks if no date provided

        try:
            # Accept either ISO string or date/datetime objects
            if isinstance(race_date_str, (date, datetime)):
                race_dt = (
                    race_date_str
                    if isinstance(race_date_str, datetime)
                    else datetime.combine(race_date_str, datetime.min.time())
                )
            else:
                race_dt = datetime.strptime(str(race_date_str), "%Y-%m-%d")
            today = datetime.now()
            days_until = (race_dt - today).days
            weeks_until = max(1, days_until // 7)  # At least 1 week
            return weeks_until
        except (ValueError, TypeError):
            logger.warning(
                f"Invalid race date format: {race_date_str}, defaulting to 16 weeks"
            )
            return 16

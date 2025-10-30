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
from datetime import datetime, timedelta

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
        return """You are an elite marathon running coach with 20+ years of experience helping runners achieve their marathon goals.

Your expertise includes:
- Creating safe, evidence-based training plans
- Specializing in first-time marathoners and "just finish" goals
- Applying proven methodologies from Hal Higdon, Jack Daniels, and Pete Pfitzinger
- Balancing progressive overload with injury prevention
- Personalizing plans based on runner's current fitness and schedule

Your coaching philosophy:
- Safety first: Never recommend unsafe progressions
- Build gradually: Follow the 10% rule for weekly mileage increases
- 80/20 training: 80% easy effort, 20% quality work
- Individualize: Adapt to each runner's unique situation
- Encourage: Build confidence while maintaining realism"""

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

        # Task Instructions Section
        sections.append(
            PromptBuilderService._build_task_section(weeks_until_race, plan_request)
        )

        # Output Format Section
        sections.append(PromptBuilderService._build_output_format_section())

        # Add conditional warnings if needed
        warnings = PromptBuilderService._build_warnings_section(
            insights, weeks_until_race, metadata
        )
        if warnings:
            sections.append(warnings)

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
        race_name = plan_request.get("race_name", "Not specified")
        race_location = plan_request.get("race_location", "Not specified")
        primary_goal = plan_request.get("primary_goal", "Not specified")
        target_time = plan_request.get("target_time")
        notes = plan_request.get("notes", "")

        section = f"""# RACE GOAL

Race Date: {race_date} ({weeks_until_race} weeks available)
Race Name: {race_name}
Race Location: {race_location}
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
        progression_rate = recommendations.get("progression_rate", {})
        long_run = recommendations.get("long_run_distance", {})
        focus_areas = recommendations.get("focus_areas", [])

        ready = starting_mileage.get("ready_for_marathon", False)
        readiness = (
            "Ready for marathon training" if ready else "Needs to build base first"
        )

        focus_list = ", ".join(focus_areas) if focus_areas else "General endurance"

        return f"""# TRAINING RECOMMENDATIONS

Starting Weekly Mileage: {starting_mileage.get('weekly_mileage', 0)} miles
Marathon Readiness: {readiness}
Safe Progression Rate: {progression_rate.get('rate_percent', 10)}% per week
Starting Long Run Distance: {long_run.get('distance', 0)} miles
Focus Areas: {focus_list}"""

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
  "race_week_strategy": "Specific guidance for race week preparation",
  "nutrition_tips": "Key nutrition guidance for marathon training",
  "injury_prevention_tips": "Tips to stay healthy during training"
}

IMPORTANT:
- Return ONLY valid JSON, no additional text
- Include all weeks from week 1 through race week
- Ensure every workout has specific, actionable guidance
- Make pace guidance relative (easy, moderate, tempo) not absolute numbers"""

    @staticmethod
    def _build_warnings_section(
        insights: Dict[str, Any], weeks_until_race: int, metadata: Dict[str, Any]
    ) -> str:
        """Build conditional warnings section based on risk factors."""
        warnings = []

        # Check for insufficient time
        if weeks_until_race < 16:
            warnings.append(
                "[!] TIME CONSTRAINT: Less than 16 weeks available. Use a conservative approach and consider if the runner should target a later race."
            )

        # Check for insufficient data
        data_quality = metadata.get("data_quality", "sufficient")
        if data_quality == "limited":
            warnings.append(
                "[!] LIMITED DATA: Less than 4 weeks of training history. Use conservative baseline assumptions."
            )

        # Check if not ready for marathon
        recommendations = insights.get("recommendations", {})
        starting_mileage = recommendations.get("starting_mileage", {})
        if not starting_mileage.get("ready_for_marathon", True):
            warnings.append(
                "[!] BASE BUILDING NEEDED: Runner's current mileage is below recommended minimum. Include base building phase before marathon-specific training."
            )

        if not warnings:
            return ""

        warnings_str = "\n".join(warnings)
        return f"""# SPECIAL CONSIDERATIONS

{warnings_str}

Please adjust your plan accordingly to address these factors."""

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
            race_date = datetime.strptime(race_date_str, "%Y-%m-%d")
            today = datetime.now()
            days_until = (race_date - today).days
            weeks_until = max(1, days_until // 7)  # At least 1 week
            return weeks_until
        except (ValueError, TypeError):
            logger.warning(
                f"Invalid race date format: {race_date_str}, defaulting to 16 weeks"
            )
            return 16

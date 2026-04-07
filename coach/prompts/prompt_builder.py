"""
CoachPromptBuilder for Coach system.

Builds prompts from RunnerState and QuestionContext for the LLM.
"""

import json
from typing import Dict, List, Any, Optional

from coach.utils.error_handler import CoachErrorHandler, ErrorSeverity
from coach.utils.intent_classifier import Intent
from src.utils.hr_zone_constants import hr_calibration_reason_user_hint


# Base system prompt for the Coach
BASE_COACH_SYSTEM_PROMPT = """You are an expert running coach with access to comprehensive training data.

You will receive structured data including:
- Runner state (training phase, zones, patterns, safety indicators)
- Intent-specific context for the user's question
- Historical activity data (completed runs)
- Planned workout data (upcoming training)
- Weekly summaries and performance metrics

When answering questions:
1. Reference specific data points when relevant
2. Provide actionable insights based on the user's training patterns
3. Consider the user's race goals and timeline
4. Be encouraging and supportive while being honest about performance
5. Always prioritize safety - if safety flags are present, address them first

For vague questions (like "How am I doing?" or "Tell me about my running"):
- Acknowledge what data you have available
- Ask 2-3 specific clarifying questions with options
- Provide examples of what you can help with
- Be encouraging and helpful

If you don't have complete data for a question, acknowledge this and ask for clarification.

CRITICAL SAFETY GUIDELINES:
- If safety flags indicate medical red flags, ALWAYS recommend immediate medical consultation
- Never provide medical advice - refer to healthcare professionals
- If injury symptoms are present, prioritize rest and professional evaluation
- Never encourage training through pain

HR CALIBRATION GUIDELINES:
- If HR calibration is not ready, explain this clearly and positively ("we're still calibrating your HR profile").
- Use calibration fields when present: reason code, qualifying run count, runs still needed, and minimum duration.
- Tell users what kind of runs help calibration: include some harder efforts (tempo, threshold intervals, hills, or race efforts), not only easy runs.
- Mention run length guidance using the minimum duration field (10+ minutes qualifies; 20-40 minute sessions are typically most useful).
- If manual max HR appears unusable, suggest verifying watch/Strava max HR and updating profile settings.
"""


class CoachPromptBuilder:
    """
    Builds prompts for Coach LLM interactions.

    Takes RunnerState and QuestionContext and formats them into
    a structured prompt for the LLM.
    """

    def __init__(self):
        """Initialize CoachPromptBuilder."""
        pass

    def build(
        self,
        runner_state: Dict[str, Any],
        question_context: Dict[str, Any],
        user_question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        """
        Build complete prompt with system and user messages.

        Args:
            runner_state: RunnerState dict (from RunnerStateBuilder)
            question_context: QuestionContext dict (from QuestionContextBuilder)
            user_question: The user's raw question
            conversation_history: Optional list of previous messages

        Returns:
            List of message dicts with 'role' and 'content'
        """
        try:
            messages = []

            # Build system prompt
            system_prompt = self._build_system_prompt(question_context)
            messages.append({"role": "system", "content": system_prompt})

            # Build user message with context
            user_message = self._build_user_message(
                runner_state, question_context, user_question
            )
            messages.append({"role": "user", "content": user_message})

            # Add conversation history if provided (limit to last 10 messages)
            if conversation_history:
                for msg in conversation_history[-10:]:
                    messages.append(
                        {
                            "role": msg.get("role", "user"),
                            "content": msg.get("content", ""),
                        }
                    )

            # Add current user question again if we have history
            if conversation_history:
                messages.append({"role": "user", "content": user_question})

            return messages

        except Exception as e:
            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.HIGH,
                component="CoachPromptBuilder.build",
                metadata={
                    "has_runner_state": bool(runner_state),
                    "has_question_context": bool(question_context),
                },
            )
            # Return minimal fallback prompt
            return [
                {"role": "system", "content": BASE_COACH_SYSTEM_PROMPT},
                {"role": "user", "content": user_question},
            ]

    def _build_system_prompt(self, question_context: Dict[str, Any]) -> str:
        """
        Build system prompt, potentially customizing based on intent.

        Args:
            question_context: QuestionContext dict

        Returns:
            System prompt string
        """
        intent = question_context.get("question_context", {}).get(
            "intent", "general_education"
        )

        # Base prompt
        prompt = BASE_COACH_SYSTEM_PROMPT

        # Add intent-specific guidance
        if intent == Intent.INJURY_OR_SYMPTOM.value:
            prompt += "\n\nIMPORTANT: This question relates to injury or medical symptoms. Always prioritize safety and recommend professional medical evaluation. Never provide medical diagnosis or treatment advice."
        elif intent == Intent.WORKOUT_REVIEW.value:
            prompt += "\n\nFocus on providing specific, actionable feedback about the workout. Compare performance to plan targets if available."
        elif intent == Intent.THIS_WEEK_PLAN.value:
            prompt += "\n\nFor 'this week' questions, prioritize the planned workouts provided in the context. Be specific about what to do each day."
        elif intent == Intent.PROGRESS_REVIEW_LAST_WEEK.value:
            prompt += "\n\nFor 'last week' questions, provide a detailed review of the week's training. Include: (1) Quick takeaway summarizing the week, (2) Weekly overview with mileage, completion rate, and run details, (3) Analysis of what the data shows (pace, HR, consistency), (4) What it means for their training progression, (5) Action steps for improvement, and (6) Encouragement. Be specific and reference actual data from their runs."

        return prompt

    def _build_user_message(
        self,
        runner_state: Dict[str, Any],
        question_context: Dict[str, Any],
        user_question: str,
    ) -> str:
        """
        Build user message with structured context.

        Args:
            runner_state: RunnerState dict
            question_context: QuestionContext dict
            user_question: User's question

        Returns:
            Formatted user message string
        """
        parts = []

        # Add Runner State
        if runner_state and "runner_state" in runner_state:
            parts.append("# RUNNER STATE\n")
            parts.append(self._format_runner_state(runner_state["runner_state"]))
            parts.append("")

        # Add Question Context
        if question_context and "question_context" in question_context:
            parts.append("# QUESTION CONTEXT\n")
            parts.append(
                self._format_question_context(question_context["question_context"])
            )
            parts.append("")

        # Add user question
        parts.append(f"# USER QUESTION\n\n{user_question}")

        return "\n".join(parts)

    def _format_runner_state(self, runner_state: Dict[str, Any]) -> str:
        """
        Format RunnerState into readable text.

        Args:
            runner_state: RunnerState dict (inner, not wrapped)

        Returns:
            Formatted string
        """
        lines = []

        # Phase and week
        phase = runner_state.get("phase", "Unknown")
        week_of_block = runner_state.get("week_of_block", 0)
        lines.append(f"Training Phase: {phase}")
        lines.append(f"Week of Block: {week_of_block}")

        # Plan type
        if runner_state.get("plan_type"):
            lines.append(f"Plan Type: {runner_state['plan_type']}")

        # Race info
        if runner_state.get("race"):
            race = runner_state["race"]
            lines.append(f"\nRace:")
            lines.append(f"  Date: {race.get('date', 'Unknown')}")
            lines.append(f"  Distance: {race.get('distance', 'Unknown')}")
            lines.append(f"  Goal: {race.get('goal_type', 'Unknown')}")
            if race.get("target_time"):
                lines.append(f"  Target Time: {race['target_time']}")

        # Zones
        if runner_state.get("zones"):
            zones = runner_state["zones"]
            lines.append(f"\nTraining Zones:")

            if zones.get("hr"):
                lines.append("  Heart Rate Zones:")
                for zone_key, zone_value in zones["hr"].items():
                    lines.append(f"    {zone_key.upper()}: {zone_value}")

            if zones.get("pace"):
                lines.append("  Pace Zones:")
                for zone_key, zone_value in zones["pace"].items():
                    lines.append(f"    {zone_key.capitalize()}: {zone_value}")

            hr_calibration = zones.get("hr_calibration")
            if hr_calibration:
                lines.append("  HR Calibration:")
                status = hr_calibration.get("status", "unknown")
                lines.append(f"    Status: {status}")
                if status == "uncalibrated":
                    reason_code = hr_calibration.get("reason_code")
                    lines.append(f"    Reason: {reason_code or 'UNKNOWN'}")
                    hint = hr_calibration.get(
                        "user_hint"
                    ) or hr_calibration_reason_user_hint(
                        reason_code if isinstance(reason_code, str) else None
                    )
                    lines.append(f"    Coaching hint: {hint}")
                    lines.append(
                        "    Qualifying Runs: "
                        f"{hr_calibration.get('qualifying_activity_count', 0)}"
                    )
                    lines.append(
                        "    Runs Needed: "
                        f"{hr_calibration.get('activities_needed', 'unknown')}"
                    )
                    lines.append(
                        "    Minimum Duration: "
                        f"{hr_calibration.get('min_activity_duration_minutes', 10)} minutes"
                    )
                else:
                    lines.append(
                        "    Effective Max HR: "
                        f"{hr_calibration.get('effective_max_hr', 'unknown')}"
                    )
                    lines.append(
                        f"    Source: {hr_calibration.get('source', 'unknown')}"
                    )
                    lines.append(
                        "    Confidence: "
                        f"{hr_calibration.get('confidence', 'unknown')}"
                    )

        # Weekly metrics
        if runner_state.get("weekly_metrics"):
            metrics = runner_state["weekly_metrics"]
            lines.append(f"\nCurrent Week Metrics:")
            lines.append(f"  Week Start: {metrics.get('week_start', 'Unknown')}")
            lines.append(f"  Mileage: {metrics.get('mileage', 0):.1f} miles")
            lines.append(f"  Volume Score: {metrics.get('volume_score', 0):.1f}")
            lines.append(f"  Intensity Score: {metrics.get('intensity_score', 0):.1f}")
            lines.append(
                f"  Consistency Score: {metrics.get('consistency_score', 0):.1f}"
            )
            if metrics.get("load_change_pct") is not None:
                lines.append(f"  Load Change: {metrics['load_change_pct']:.1f}%")
            if metrics.get("fatigue_flags"):
                lines.append(f"  Fatigue Flags: {', '.join(metrics['fatigue_flags'])}")

        # Patterns
        if runner_state.get("patterns"):
            patterns = runner_state["patterns"]
            lines.append(f"\nTraining Patterns:")
            lines.append(
                f"  Long Runs Too Fast: {patterns.get('long_runs_too_fast_count', 0)}"
            )
            lines.append(
                f"  Missed Key Workouts (Last 4 Weeks): {patterns.get('missed_key_workouts_last_4_weeks', 0)}"
            )
            lines.append(f"  Trend: {patterns.get('trend', 'stable').capitalize()}")

        # Safety indicators
        if runner_state.get("safety"):
            safety = runner_state["safety"]
            lines.append(f"\nSafety Indicators:")
            lines.append(f"  HR Data Reliable: {safety.get('hr_data_reliable', False)}")
            lines.append(
                f"  Pace Data Reliable: {safety.get('pace_data_reliable', False)}"
            )
            lines.append(f"  Reported Injury: {safety.get('reported_injury', False)}")

        return "\n".join(lines)

    def _format_question_context(self, question_context: Dict[str, Any]) -> str:
        """
        Format QuestionContext into readable text.

        Args:
            question_context: QuestionContext dict (inner, not wrapped)

        Returns:
            Formatted string
        """
        lines = []
        intent = question_context.get("intent", "unknown")
        lines.append(f"Intent: {intent}")

        # Format intent-specific context
        if "workout_review" in question_context:
            workout_review = question_context["workout_review"]
            lines.append("\nWorkout Review Context:")
            if workout_review.get("activity"):
                activity = workout_review["activity"]
                lines.append(f"  Date: {activity.get('date', 'Unknown')}")
                lines.append(
                    f"  Distance: {activity.get('distance_miles', 0):.1f} miles"
                )
                if activity.get("avg_pace"):
                    lines.append(f"  Average Pace: {activity['avg_pace']}")
                if activity.get("avg_hr"):
                    lines.append(f"  Average HR: {activity['avg_hr']} bpm")
                if activity.get("zone_distribution"):
                    lines.append("  HR Zone Distribution:")
                    for zone, pct in activity["zone_distribution"].items():
                        lines.append(f"    {zone.upper()}: {pct}")

        elif "this_week_plan" in question_context:
            plan_ctx = question_context["this_week_plan"]
            if plan_ctx.get("current_week"):
                week = plan_ctx["current_week"]
                lines.append(f"\nThis Week Plan:")
                lines.append(f"  Week Number: {week.get('week_number', 'Unknown')}")
                if week.get("workouts"):
                    lines.append("  Workouts:")
                    for workout in week["workouts"]:
                        lines.append(
                            f"    {workout.get('day', 'Unknown')}: {workout.get('type', 'Unknown')} - {workout.get('miles', 0):.1f} miles"
                        )
                        if workout.get("pace"):
                            lines.append(f"      Pace: {workout['pace']}")

        elif "progress_check" in question_context:
            progress = question_context["progress_check"]
            lines.append("\nProgress Check Context:")
            if progress.get("last_7_days_summary"):
                summary = progress["last_7_days_summary"]
                lines.append(f"  Last 7 Days:")
                lines.append(f"    Total Miles: {summary.get('total_miles', 0):.1f}")
                lines.append(f"    Activity Count: {summary.get('activity_count', 0)}")
                if summary.get("average_pace_seconds_per_mile"):
                    pace_sec = summary["average_pace_seconds_per_mile"]
                    pace_str = f"{int(pace_sec // 60)}:{int(pace_sec % 60):02d}/mi"
                    lines.append(f"    Average Pace: {pace_str}")
                if summary.get("average_heartrate"):
                    lines.append(
                        f"    Average HR: {summary['average_heartrate']:.0f} bpm"
                    )

        elif "progress_review_last_week" in question_context:
            weekly = question_context["progress_review_last_week"]
            lines.append("\nLast Week's Training:")
            lines.append(
                f"  Week: {weekly.get('week', {}).get('start', 'Unknown')} to {weekly.get('week', {}).get('end', 'Unknown')}"
            )
            lines.append(f"  Planned Miles: {weekly.get('plan_miles', 0):.1f}")
            lines.append(f"  Completed Miles: {weekly.get('actual_miles', 0):.1f}")
            lines.append(f"  Completion Rate: {weekly.get('completion_rate', 0):.1%}")
            lines.append(f"  Runs Completed: {weekly.get('run_count', 0)}")

            if weekly.get("runs"):
                lines.append("  Runs:")
                for run in weekly["runs"]:
                    run_line = f"    {run.get('day', 'Unknown')} ({run.get('date', 'Unknown')}): {run.get('distance', 0):.1f} miles"
                    if run.get("pace"):
                        run_line += f" @ {run.get('pace')}"
                    if run.get("hr"):
                        run_line += f", HR: {run.get('hr')} bpm"
                    if run.get("evaluation"):
                        run_line += f" [{run.get('evaluation')}]"
                    lines.append(run_line)

            if weekly.get("long_run"):
                lr = weekly["long_run"]
                lines.append("  Long Run:")
                lines.append(f"    Distance: {lr.get('distance', 0):.1f} miles")
                if lr.get("pace"):
                    lines.append(f"    Pace: {lr.get('pace')}")
                if lr.get("target_pace"):
                    lines.append(f"    Target Pace: {lr.get('target_pace')}")
                lines.append(f"    Evaluation: {lr.get('evaluation', 'Unknown')}")

            if weekly.get("key_insights"):
                lines.append("  Key Insights:")
                for insight in weekly["key_insights"]:
                    lines.append(f"    - {insight}")

        elif "injury_or_symptom" in question_context:
            injury_ctx = question_context["injury_or_symptom"]
            lines.append("\nInjury/Symptom Context:")
            if injury_ctx.get("safety_flags"):
                lines.append(f"  Safety Flags: {', '.join(injury_ctx['safety_flags'])}")

        # Format as JSON for more complex contexts (fallback)
        if len(lines) == 1:  # Only intent was added
            lines.append(f"\n{json.dumps(question_context, indent=2)}")

        return "\n".join(lines)

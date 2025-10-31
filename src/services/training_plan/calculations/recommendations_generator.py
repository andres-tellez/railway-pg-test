"""
Recommendations generator for Layer 2.

Generates safe starting points, progression rates, and training
recommendations based on current fitness and safety assessments.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
from .week_utils import get_complete_weeks, calculate_week_mileage

logger = logging.getLogger(__name__)


class RecommendationsGenerator:
    """
    Generates training recommendations based on analysis.

    Provides safe starting points, progression rates, and focus areas
    for marathon training based on current fitness and safety assessments.
    """

    def generate_recommendations(
        self,
        activities: List[Dict[str, Any]],
        user_profile: Dict[str, Any],
        plan_request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate all training recommendations.

        Args:
            activities: List of activity dictionaries
            user_profile: User demographic and preference information
            plan_request: Plan creation request parameters

        Returns:
            Dictionary containing training recommendations
        """
        logger.debug(f"Generating recommendations for {len(activities)} activities")

        # Calculate current fitness metrics
        current_weekly_mileage = self._calculate_current_weekly_mileage(activities)
        longest_run = self._find_longest_run(activities)

        # Generate recommendations
        starting_mileage = self._calculate_safe_starting_mileage(
            current_weekly_mileage, longest_run, activities
        )

        progression_rate = self._calculate_safe_progression_rate(activities)

        focus_areas = self._identify_focus_areas(activities, user_profile, plan_request)

        training_frequency = self._recommend_training_frequency(
            activities, user_profile
        )

        long_run_recommendation = self._recommend_long_run_distance(activities)

        return {
            "starting_mileage": starting_mileage,
            "progression_rate": progression_rate,
            "focus_areas": focus_areas,
            "training_frequency": training_frequency,
            "long_run_distance": long_run_recommendation,
            "training_principles": self._get_training_principles(),
            "safety_guidelines": self._get_safety_guidelines(),
        }

    def _calculate_current_weekly_mileage(
        self, activities: List[Dict[str, Any]]
    ) -> float:
        """
        Get current weekly mileage from the most recent complete week.

        This is the simple approach used by running coaches: "What did you run last week?"
        """
        if not activities:
            return 0.0

        # Get the most recent complete week
        weekly_data = get_complete_weeks(activities, max_weeks=1)

        if not weekly_data:
            return 0.0

        # Get mileage from last complete week
        most_recent_week = list(weekly_data.values())[0]
        return calculate_week_mileage(most_recent_week)

    def _find_longest_run(self, activities: List[Dict[str, Any]]) -> float:
        """Find longest run in last 4 weeks."""
        if not activities:
            return 0.0

        cutoff_date = datetime.now() - timedelta(weeks=4)

        longest_distance = 0.0
        for activity in activities:
            if not activity.get("date"):
                continue

            try:
                activity_date = datetime.strptime(activity["date"], "%Y-%m-%d")
                if activity_date >= cutoff_date:
                    distance = activity.get("distance", 0.0)
                    if distance and distance > longest_distance:
                        longest_distance = distance
            except (ValueError, TypeError):
                continue

        return round(longest_distance, 1)

    def _calculate_safe_starting_mileage(
        self,
        current_weekly: float,
        longest_run: float,
        activities: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Determine starting mileage using the expert approach:
        - Hal Higdon, Jack Daniels, Pete Pfitzinger method
        - Check if runner meets minimum base (20 mpw)
        - If yes: Start at current mileage
        - If no: Build base first
        """
        MINIMUM_BASE = 20.0  # Minimum recommended by all major coaches

        if not activities or current_weekly == 0:
            return {
                "weekly_mileage": 0.0,
                "rationale": "No recent training - build base to 20+ mpw first",
                "confidence": "Low",
                "ready_for_marathon": False,
            }

        # Check if they meet minimum base requirement
        if current_weekly < MINIMUM_BASE:
            return {
                "weekly_mileage": current_weekly,
                "rationale": f"Current mileage ({current_weekly} mpw) below minimum - build base to 20+ mpw first",
                "confidence": "Low",
                "ready_for_marathon": False,
            }

        # They're ready! Start at current mileage
        return {
            "weekly_mileage": current_weekly,
            "rationale": f"Current mileage: {current_weekly} mpw",
            "confidence": "High",
            "ready_for_marathon": True,
        }

    def _calculate_safe_progression_rate(
        self, activities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Return the standard 10% rule for safe weekly mileage progression.

        The 10% rule is the universally accepted standard for safe mileage
        increases, supported by running coaches and injury research.
        """
        return {
            "rate_percent": 10.0,
            "rationale": "Standard 10% rule for safe weekly mileage progression",
            "confidence": "High",
        }

    def _identify_focus_areas(
        self,
        activities: List[Dict[str, Any]],
        user_profile: Dict[str, Any],
        plan_request: Dict[str, Any],
    ) -> List[str]:
        """
        Identify focus areas for training based on analysis.

        Returns list of focus areas like ["Consistency", "Base Building", "Injury Prevention"]
        """
        focus_areas = []

        # Analyze training consistency
        if activities:
            weekly_data = self._group_activities_by_week(activities)
            if len(weekly_data) >= 2:
                weekly_mileages = []
                for week_activities in weekly_data.values():
                    week_mileage = sum(
                        activity.get("distance", 0.0)
                        for activity in week_activities
                        if activity.get("distance", 0.0) > 0
                    )
                    weekly_mileages.append(week_mileage)

                if weekly_mileages:
                    # Check consistency
                    max_mileage = max(weekly_mileages)
                    min_mileage = min(weekly_mileages)
                    if max_mileage > 0:
                        variance = (max_mileage - min_mileage) / max_mileage
                        if variance > 0.5:
                            focus_areas.append("Consistency")

        # Check current fitness level
        current_weekly = self._calculate_current_weekly_mileage(activities)
        if current_weekly < 20:
            focus_areas.append("Base Building")
        elif current_weekly < 35:
            focus_areas.append("Mileage Building")
        else:
            focus_areas.append("Marathon Preparation")

        # Check goal
        goal = plan_request.get("primary_goal", "Just Finish")
        if goal == "Just Finish":
            focus_areas.append("Endurance Focus")
        elif goal == "Target Time":
            focus_areas.append("Pace Training")

        # Remove duplicates and return
        return list(set(focus_areas))

    def _recommend_training_frequency(
        self, activities: List[Dict[str, Any]], user_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recommend training frequency based on history and preferences."""
        if not activities:
            return {
                "runs_per_week": 3,
                "rationale": "Conservative starting point for beginners",
                "confidence": "Medium",
            }

        # Calculate current frequency
        current_frequency = self._calculate_training_frequency(activities)

        # Get user preferences
        preferred_days = user_profile.get("training_days", [])

        # Recommend frequency
        if current_frequency >= 5:
            recommended_frequency = 5
            rationale = f"Current frequency is {current_frequency:.1f} runs/week - maintaining high frequency"
            confidence = "High"
        elif current_frequency >= 4:
            recommended_frequency = 4
            rationale = f"Current frequency is {current_frequency:.1f} runs/week - good frequency"
            confidence = "High"
        elif current_frequency >= 3:
            recommended_frequency = 3
            rationale = f"Current frequency is {current_frequency:.1f} runs/week - appropriate for marathon training"
            confidence = "High"
        else:
            recommended_frequency = 3
            rationale = f"Current frequency is {current_frequency:.1f} runs/week - increasing to 3 for marathon training"
            confidence = "Medium"

        # Consider user preferences
        if preferred_days and len(preferred_days) < recommended_frequency:
            recommended_frequency = len(preferred_days)
            rationale += f" (adjusted to user preference of {len(preferred_days)} days)"

        return {
            "runs_per_week": recommended_frequency,
            "rationale": rationale,
            "confidence": confidence,
        }

    def _recommend_long_run_distance(
        self, activities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Recommend starting long run distance based on recent training.

        Uses the longest run from the last 4 weeks (most recent month) as the baseline.
        This is the "last long run" approach used by running coaches.
        """
        if not activities:
            return {
                "distance": 10.0,
                "rationale": "No recent data - conservative 10 mile starting point",
                "confidence": "Low",
            }

        # Get longest run from last 4 weeks
        from datetime import datetime, timedelta

        cutoff_date = datetime.now() - timedelta(weeks=4)

        recent_longest = 0.0
        for activity in activities:
            if not activity.get("date"):
                continue

            try:
                activity_date = datetime.strptime(activity["date"], "%Y-%m-%d")
                if activity_date >= cutoff_date:
                    distance = activity.get("distance", 0.0)
                    if distance and distance > recent_longest:
                        recent_longest = distance
            except (ValueError, TypeError):
                continue

        if recent_longest == 0:
            return {
                "distance": 10.0,
                "rationale": "No recent long runs - conservative 10 mile starting point",
                "confidence": "Low",
            }

        # Start 1 mile more than the last long run (standard progression)
        starting_long_run = recent_longest + 1.0

        return {
            "distance": round(starting_long_run, 1),
            "rationale": f"Last long run: {recent_longest} miles, starting at {starting_long_run} miles",
            "confidence": "High",
        }

    def _group_activities_by_week(
        self, activities: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group activities by week for analysis."""
        weekly_data = {}

        for activity in activities:
            if not activity.get("date"):
                continue

            try:
                activity_date = datetime.strptime(activity["date"], "%Y-%m-%d")
                week_key = activity_date.isocalendar()[1]  # Week number
                year = activity_date.year
                week_id = f"{year}-W{week_key:02d}"

                if week_id not in weekly_data:
                    weekly_data[week_id] = []
                weekly_data[week_id].append(activity)
            except (ValueError, TypeError):
                continue

        return weekly_data

    def _calculate_training_frequency(self, activities: List[Dict[str, Any]]) -> float:
        """Calculate training frequency in runs per week."""
        if not activities:
            return 0.0

        # Get date range
        dates = []
        for activity in activities:
            if activity.get("date"):
                try:
                    activity_date = datetime.strptime(activity["date"], "%Y-%m-%d")
                    dates.append(activity_date)
                except (ValueError, TypeError):
                    continue

        if not dates:
            return 0.0

        earliest = min(dates)
        latest = max(dates)
        days_diff = (latest - earliest).days

        if days_diff == 0:
            return len(activities)

        weeks = max(1, days_diff / 7)
        return len(activities) / weeks

    def _get_training_principles(self) -> List[str]:
        """Get fundamental training principles."""
        return [
            "Follow the 10% rule for weekly mileage increases",
            "Include one long run per week (20-30% of weekly mileage)",
            "Maintain 80/20 easy-to-hard training ratio",
            "Allow adequate recovery between hard sessions",
            "Listen to your body and adjust as needed",
        ]

    def _get_safety_guidelines(self) -> List[str]:
        """Get safety guidelines for training."""
        return [
            "Stop training if you experience pain",
            "Increase mileage gradually (10% per week maximum)",
            "Take rest days seriously",
            "Stay hydrated and fuel properly",
            "Consult a healthcare provider for any concerns",
        ]

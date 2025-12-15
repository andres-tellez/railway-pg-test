"""
RaceInfoBuilder submodule for RunnerStateBuilder.

Extracts race information from the active training plan.
"""

from datetime import date
from typing import Dict, Optional

from src.db.dao.plans_dao import get_active_plan
from src.db.models.plans import Plan


class RaceInfoBuilder:
    """
    Builds race information from the active training plan.

    Extracts:
    - Race date
    - Race distance
    - Goal type (Just Finish or Target Time)
    - Target time (if goal is Target Time)
    """

    def __init__(self, session, user_id: str):
        """
        Initialize RaceInfoBuilder.

        Args:
            session: Database session
            user_id: User ID to get active plan for
        """
        self.session = session
        self.user_id = user_id

    def build(self) -> Optional[Dict[str, any]]:
        """
        Build race information from active plan.

        Returns:
            Dictionary with race information matching schema, or None if no active plan
            {
                "date": "YYYY-MM-DD",
                "distance": "Marathon",
                "goal_type": "Just Finish" | "Target Time",
                "target_time": "HH:MM:SS" (optional, only if goal_type is "Target Time")
            }
        """
        plan = get_active_plan(self.session, self.user_id)

        if not plan:
            return None

        # Race date and distance are required per schema
        if not plan.race_date or not plan.race_distance:
            return None

        race_info = {
            "date": (
                plan.race_date.isoformat()
                if isinstance(plan.race_date, date)
                else str(plan.race_date)
            ),
            "distance": plan.race_distance,
        }

        # Goal type
        if plan.primary_goal:
            race_info["goal_type"] = plan.primary_goal
        else:
            # Default to "Just Finish" if not specified
            race_info["goal_type"] = "Just Finish"

        # Target time (only if goal is Target Time)
        if race_info["goal_type"] == "Target Time" and plan.target_time:
            race_info["target_time"] = plan.target_time

        return race_info

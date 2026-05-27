"""Tier 2: per-activity execution facts for Insights."""

from src.smartcoach_mobile_coach.execution_analytics.combine import (
    StoredTempoRunFact,
    combine_weekly_from_stored_run_facts,
    run_fact_eligible_for_week_chart,
)
from src.smartcoach_mobile_coach.execution_analytics.producer import (
    EXECUTION_ANALYTICS_VERSION,
    compute_activity_execution,
    compute_and_apply_activity_execution,
    refresh_activity_execution_kpis,
)

__all__ = [
    "EXECUTION_ANALYTICS_VERSION",
    "StoredTempoRunFact",
    "combine_weekly_from_stored_run_facts",
    "compute_activity_execution",
    "compute_and_apply_activity_execution",
    "refresh_activity_execution_kpis",
    "run_fact_eligible_for_week_chart",
]

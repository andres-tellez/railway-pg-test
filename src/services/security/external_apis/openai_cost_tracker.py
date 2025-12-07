"""
OpenAI Cost Tracker
===================

Cost tracking for OpenAI API calls to monitor spending and enforce budget limits.

This module provides:
- Per-user daily cost tracking
- Global daily cost tracking
- Token usage → cost calculation
- Cost limit checking (per-user and global)
- Cost statistics and reporting

Model Pricing (as of 2024):
---------------------------
- gpt-4o: $2.50/$10.00 per 1M tokens (input/output)
- gpt-3.5-turbo: $0.50/$1.50 per 1M tokens (input/output)
- gpt-4: $30.00/$60.00 per 1M tokens (input/output)

Cost Limits:
------------
- Per-user: $2.00/day (prevents single user abuse)
- Global alert: $50.00/day (warning threshold)
- Global hard limit: $100.00/day (blocks all requests)
"""

import time
from collections import defaultdict
from datetime import datetime, date
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Model pricing (per 1M tokens) - input/output
MODEL_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-08-06": {"input": 2.50, "output": 10.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "gpt-3.5-turbo-16k": {"input": 3.00, "output": 4.00},
}

# Cost limits
PER_USER_DAILY_LIMIT = 2.00  # $2/day per user
GLOBAL_DAILY_ALERT = 50.00  # $50/day warning threshold
GLOBAL_DAILY_HARD_LIMIT = 100.00  # $100/day hard limit (blocks all requests)

# In-memory storage: {date_str: {user_id: total_cost}}
_daily_costs_per_user: Dict[str, Dict[str, float]] = defaultdict(
    lambda: defaultdict(float)
)
# Global daily costs: {date_str: total_cost}
_global_daily_costs: Dict[str, float] = defaultdict(float)


def _get_today_str() -> str:
    """Get today's date as YYYY-MM-DD string."""
    return date.today().isoformat()


def _calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Calculate cost for a request based on model and token usage.

    Args:
        model: Model name (e.g., "gpt-4o")
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens

    Returns:
        Cost in USD
    """
    # Normalize model name (remove version suffix if present)
    base_model = (
        model.split("-")[0] + "-" + model.split("-")[1] if "-" in model else model
    )
    if "4o" in model:
        base_model = "gpt-4o"
    elif "3.5" in model:
        base_model = "gpt-3.5-turbo"
    elif "4-turbo" in model:
        base_model = "gpt-4-turbo"
    elif model.startswith("gpt-4"):
        base_model = "gpt-4"

    pricing = MODEL_PRICING.get(base_model, MODEL_PRICING["gpt-4o"])

    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]

    return input_cost + output_cost


def record_request_cost(
    user_id: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """
    Record cost for an OpenAI API request.

    Args:
        user_id: User identifier
        model: Model used (e.g., "gpt-4o")
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens

    Returns:
        Cost of this request in USD
    """
    cost = _calculate_cost(model, prompt_tokens, completion_tokens)
    today = _get_today_str()

    # Update per-user cost
    _daily_costs_per_user[today][user_id] += cost

    # Update global cost
    _global_daily_costs[today] += cost

    logger.debug(
        f"Recorded OpenAI cost: user={user_id}, model={model}, "
        f"tokens={prompt_tokens}+{completion_tokens}, cost=${cost:.4f}"
    )

    return cost


def check_cost_limits(user_id: str) -> Tuple[bool, Optional[str], Optional[float]]:
    """
    Check if request is within cost limits.

    Args:
        user_id: User identifier

    Returns:
        Tuple of (is_allowed, error_message, exceeded_by_amount)
        - is_allowed: True if within limits
        - error_message: Error message if limit exceeded (None if allowed)
        - exceeded_by: Amount exceeded by (None if allowed)
    """
    today = _get_today_str()

    # Check per-user limit
    user_cost = _daily_costs_per_user[today].get(user_id, 0.0)
    if user_cost >= PER_USER_DAILY_LIMIT:
        exceeded_by = user_cost - PER_USER_DAILY_LIMIT
        return (
            False,
            f"Daily cost limit exceeded. You have spent ${user_cost:.2f} today (limit: ${PER_USER_DAILY_LIMIT:.2f}).",
            exceeded_by,
        )

    # Check global hard limit
    global_cost = _global_daily_costs[today]
    if global_cost >= GLOBAL_DAILY_HARD_LIMIT:
        exceeded_by = global_cost - GLOBAL_DAILY_HARD_LIMIT
        logger.error(
            f"GLOBAL COST LIMIT EXCEEDED: ${global_cost:.2f} today "
            f"(limit: ${GLOBAL_DAILY_HARD_LIMIT:.2f})"
        )
        return (
            False,
            f"Service daily cost limit reached. Please try again tomorrow.",
            exceeded_by,
        )

    # Check global alert threshold (log warning, but don't block)
    if global_cost >= GLOBAL_DAILY_ALERT:
        logger.warning(
            f"GLOBAL COST ALERT: ${global_cost:.2f} today "
            f"(alert threshold: ${GLOBAL_DAILY_ALERT:.2f})"
        )

    return True, None, None


def get_user_cost_stats(user_id: str) -> Dict:
    """
    Get cost statistics for a user.

    Args:
        user_id: User identifier

    Returns:
        Dictionary with cost statistics:
        - today_cost: Total cost today
        - limit: Daily limit
        - remaining: Remaining budget for today
        - percent_used: Percentage of limit used
    """
    today = _get_today_str()
    today_cost = _daily_costs_per_user[today].get(user_id, 0.0)
    remaining = max(0, PER_USER_DAILY_LIMIT - today_cost)
    percent_used = (
        (today_cost / PER_USER_DAILY_LIMIT * 100) if PER_USER_DAILY_LIMIT > 0 else 0
    )

    return {
        "today_cost": round(today_cost, 4),
        "limit": PER_USER_DAILY_LIMIT,
        "remaining": round(remaining, 4),
        "percent_used": round(percent_used, 2),
    }


def get_global_cost_stats() -> Dict:
    """
    Get global cost statistics.

    Returns:
        Dictionary with global cost statistics:
        - today_cost: Total cost today across all users
        - alert_threshold: Alert threshold
        - hard_limit: Hard limit
        - percent_of_limit: Percentage of hard limit used
    """
    today = _get_today_str()
    today_cost = _global_daily_costs.get(today, 0.0)
    percent_of_limit = (
        (today_cost / GLOBAL_DAILY_HARD_LIMIT * 100)
        if GLOBAL_DAILY_HARD_LIMIT > 0
        else 0
    )

    return {
        "today_cost": round(today_cost, 4),
        "alert_threshold": GLOBAL_DAILY_ALERT,
        "hard_limit": GLOBAL_DAILY_HARD_LIMIT,
        "percent_of_limit": round(percent_of_limit, 2),
        "at_alert": today_cost >= GLOBAL_DAILY_ALERT,
        "at_limit": today_cost >= GLOBAL_DAILY_HARD_LIMIT,
    }


def reset_cost_tracking(user_id: str = None, date_str: str = None):
    """
    Reset cost tracking for testing or manual cleanup.

    Args:
        user_id: Specific user to reset, or None for all users
        date_str: Specific date to reset (YYYY-MM-DD), or None for today
    """
    if date_str is None:
        date_str = _get_today_str()

    if user_id:
        if date_str in _daily_costs_per_user:
            _daily_costs_per_user[date_str].pop(user_id, None)
        logger.info(f"Cost tracking reset for user {user_id} on {date_str}")
    else:
        if date_str in _daily_costs_per_user:
            del _daily_costs_per_user[date_str]
        if date_str in _global_daily_costs:
            del _global_daily_costs[date_str]
        logger.info(f"Cost tracking reset for all users on {date_str}")


def cleanup_old_data(days_to_keep: int = 7):
    """
    Clean up cost tracking data older than specified days.

    Args:
        days_to_keep: Number of days of data to keep (default: 7)
    """
    from datetime import timedelta

    cutoff_date = date.today() - timedelta(days=days_to_keep)
    cutoff_str = cutoff_date.isoformat()

    # Clean up per-user costs
    dates_to_remove = [d for d in _daily_costs_per_user.keys() if d < cutoff_str]
    for d in dates_to_remove:
        del _daily_costs_per_user[d]

    # Clean up global costs
    dates_to_remove = [d for d in _global_daily_costs.keys() if d < cutoff_str]
    for d in dates_to_remove:
        del _global_daily_costs[d]

    if dates_to_remove:
        logger.info(f"Cleaned up cost tracking data older than {days_to_keep} days")

"""
Heart Rate Zone Input Validation Utilities

VALIDATION SCOPE RULES:
- ✅ Validate input SHAPES and TYPES only
- ✅ Pre-service validation (before calling pure services)
- ❌ NEVER validate physiological ranges (services do this)
- ❌ NEVER duplicate service-level validation

Physiological range validation MUST stay in pure services
so it cannot be bypassed.
"""

from typing import Tuple, Optional, Any


def validate_activities_shape(
    activities: Any,
) -> Tuple[bool, Optional[str]]:
    """
    Validate activities list SHAPE only.

    Checks:
    - Is it a list?
    - Is it not None?
    - Is it not empty?

    Does NOT check:
    - HR values (hrmax_estimation_service does this)
    - Moving times (hrmax_estimation_service does this)

    Args:
        activities: Activities list to validate

    Returns:
        (is_valid, error_message)
    """
    if activities is None:
        return False, "activities cannot be None"

    if not isinstance(activities, list):
        return False, f"activities must be a list, got {type(activities).__name__}"

    if len(activities) == 0:
        return False, "activities list cannot be empty"

    return True, None


def validate_numeric_type(value: Any, param_name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate numeric type only (not range).

    Range validation happens in services.

    Args:
        value: Value to validate
        param_name: Name of parameter for error message

    Returns:
        (is_valid, error_message)
    """
    if not isinstance(value, (int, float)):
        return (
            False,
            f"{param_name} must be numeric, got {type(value).__name__}",
        )

    return True, None

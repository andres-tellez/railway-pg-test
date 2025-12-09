"""
Pace Zone Calculator

Main entry point for calculating pace zones.
Handles routing: Performance-based → calibration fallback.
"""
from sqlalchemy.orm import Session

from .models import PaceSeed
from .performance_calculator import calculate_paces_from_performance
from .calibration import get_calibration_pace_seed

def get_initial_pace_seed(
    session: Session,
    user_id: str,
    week1_long: float = 8.0,
    lookback_weeks: int = 6,
) -> PaceSeed:
    """
    Calculate initial pace zones for a user.
    
    Strategy:
    1. Try performance-based calculation (median easy pace from recent runs)
    2. Fall back to calibration if insufficient data (< 6 runs)
    
    Args:
        session: Database session
        user_id: User UUID
        week1_long: Planned long run distance for week 1
        lookback_weeks: Weeks of history to analyze (default: 6)
    
    Returns:
        PaceSeed with all pace zones
    """
    # Try performance-based calculation first
    performance_paces = calculate_paces_from_performance(
        session=session,
        user_id=user_id,
        lookback_weeks=lookback_weeks,
    )
    
    if performance_paces:
        return performance_paces
    
    # Fall back to calibration
    return get_calibration_pace_seed(week1_long=week1_long)


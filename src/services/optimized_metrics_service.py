"""
Optimized Metrics Service
=========================

High-performance metrics calculation service with caching and optimized queries.
Combines multiple database queries into efficient single queries where possible.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy import func, and_, or_, case
from sqlalchemy.orm import Session

from src.db.models.activities import Activity
from src.services.metrics_cache_service import cache_metrics, invalidate_athlete_cache

class OptimizedMetricsService:
    """High-performance metrics service with caching and query optimization."""
    
    @staticmethod
    @cache_metrics('weekly_distance', ttl=300)  # 5 minutes
    def get_weekly_distance_metrics(session: Session, athlete_id: int) -> Dict[str, float]:
        """Get current and previous week distance in a single optimized query."""
        today = datetime.utcnow()
        current_week_start = today - timedelta(days=today.weekday())
        last_week_start = current_week_start - timedelta(days=7)
        last_week_end = current_week_start - timedelta(seconds=1)
        
        # Single query to get both current and previous week distances
        result = session.query(
            func.sum(
                case(
                    (Activity.start_date >= current_week_start, Activity.distance),
                    else_=0
                )
            ).label('current_week_distance'),
            func.sum(
                case(
                    (and_(Activity.start_date >= last_week_start, Activity.start_date <= last_week_end), Activity.distance),
                    else_=0
                )
            ).label('previous_week_distance')
        ).filter(
            Activity.athlete_id == athlete_id,
            Activity.type == "Run",
            Activity.distance > 0
        ).first()
        
        current_distance = result.current_week_distance or 0.0
        previous_distance = result.previous_week_distance or 0.0
        
        # Convert meters to miles
        current_miles = round(current_distance / 1609.34, 1)
        previous_miles = round(previous_distance / 1609.34, 1)
        
        change_pct = (
            ((current_miles - previous_miles) / previous_miles * 100) 
            if previous_miles > 0 else 0
        )
        
        return {
            'current': current_miles,
            'previous': previous_miles,
            'change_pct': round(change_pct, 1)
        }
    
    @staticmethod
    @cache_metrics('weekly_runs_count', ttl=300)  # 5 minutes
    def get_weekly_runs_count(session: Session, athlete_id: int) -> Dict[str, int]:
        """Get current and previous week run counts in a single optimized query."""
        today = datetime.utcnow()
        current_week_start = today - timedelta(days=today.weekday())
        last_week_start = current_week_start - timedelta(days=7)
        last_week_end = current_week_start - timedelta(seconds=1)
        
        # Single query to get both current and previous week counts
        result = session.query(
            func.count(
                case(
                    (Activity.start_date >= current_week_start, 1),
                    else_=None
                )
            ).label('current_week_runs'),
            func.count(
                case(
                    (and_(Activity.start_date >= last_week_start, Activity.start_date <= last_week_end), 1),
                    else_=None
                )
            ).label('previous_week_runs')
        ).filter(
            Activity.athlete_id == athlete_id,
            Activity.type == "Run"
        ).first()
        
        current_runs = result.current_week_runs or 0
        previous_runs = result.previous_week_runs or 0
        
        change_pct = (
            ((current_runs - previous_runs) / previous_runs * 100)
            if previous_runs > 0 else 0
        )
        
        return {
            'current': current_runs,
            'previous': previous_runs,
            'change_pct': round(change_pct, 1)
        }
    
    @staticmethod
    @cache_metrics('average_pace', ttl=300)  # 5 minutes
    def get_average_pace_metrics(session: Session, athlete_id: int) -> Dict[str, Any]:
        """Get average pace for current and previous periods in a single query."""
        today = datetime.utcnow()
        current_period_start = today - timedelta(days=30)
        previous_period_start = today - timedelta(days=60)
        previous_period_end = today - timedelta(days=30)
        
        # Single query to get average pace for both periods
        result = session.query(
            func.avg(
                case(
                    (Activity.start_date >= current_period_start, Activity.distance / Activity.moving_time),
                    else_=None
                )
            ).label('current_pace_mps'),
            func.avg(
                case(
                    (and_(Activity.start_date >= previous_period_start, Activity.start_date <= previous_period_end), 
                     Activity.distance / Activity.moving_time),
                    else_=None
                )
            ).label('previous_pace_mps')
        ).filter(
            Activity.athlete_id == athlete_id,
            Activity.type == "Run",
            Activity.distance > 0,
            Activity.moving_time > 0
        ).first()
        
        current_pace_mps = result.current_pace_mps
        previous_pace_mps = result.previous_pace_mps
        
        current_pace_str = OptimizedMetricsService._format_pace(current_pace_mps)
        previous_pace_str = OptimizedMetricsService._format_pace(previous_pace_mps)
        
        pace_change = (
            ((previous_pace_mps - current_pace_mps) / previous_pace_mps * 100)
            if previous_pace_mps and previous_pace_mps > 0 else 0
        )
        
        return {
            'current': current_pace_str,
            'previous': previous_pace_str,
            'change_pct': round(pace_change, 1)
        }
    
    @staticmethod
    @cache_metrics('hr_zones', ttl=600)  # 10 minutes (HR zones change less frequently)
    def get_hr_zone_summary(session: Session, athlete_id: int) -> Dict[str, float]:
        """Get heart rate zone distribution for the last 30 days."""
        cutoff = datetime.utcnow() - timedelta(days=30)
        
        result = session.query(
            func.avg(Activity.hr_zone_1),
            func.avg(Activity.hr_zone_2),
            func.avg(Activity.hr_zone_3),
            func.avg(Activity.hr_zone_4),
            func.avg(Activity.hr_zone_5),
        ).filter(
            Activity.athlete_id == athlete_id,
            Activity.type == "Run",
            Activity.start_date >= cutoff,
        ).first()
        
        return {
            "zone_1": round(result[0] or 0.0, 1),
            "zone_2": round(result[1] or 0.0, 1),
            "zone_3": round(result[2] or 0.0, 1),
            "zone_4": round(result[3] or 0.0, 1),
            "zone_5": round(result[4] or 0.0, 1)
        }
    
    @staticmethod
    def get_all_metrics(session: Session, athlete_id: int) -> Dict[str, Any]:
        """Get all metrics in optimized queries with caching."""
        start_time = datetime.utcnow()
        
        # Get all metrics (each method has its own cache)
        weekly_distance = OptimizedMetricsService.get_weekly_distance_metrics(session, athlete_id)
        weekly_runs = OptimizedMetricsService.get_weekly_runs_count(session, athlete_id)
        average_pace = OptimizedMetricsService.get_average_pace_metrics(session, athlete_id)
        hr_zones = OptimizedMetricsService.get_hr_zone_summary(session, athlete_id)
        
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            "weekly_distance": weekly_distance,
            "weekly_runs": weekly_runs,
            "average_pace": average_pace,
            "hr_zones": hr_zones,
            "_performance": {
                "execution_time_ms": round(execution_time * 1000, 2),
                "cached": True  # All methods use caching
            }
        }
    
    @staticmethod
    def _format_pace(avg_speed_mps: Optional[float]) -> str:
        """Convert average speed (m/s) to pace (min/mi)."""
        if not avg_speed_mps or avg_speed_mps == 0:
            return "0:00"
        
        # Convert m/s to min/mi
        seconds_per_mile = 1609.34 / avg_speed_mps
        minutes = int(seconds_per_mile // 60)
        seconds = int(seconds_per_mile % 60)
        
        return f"{minutes}:{seconds:02d}"
    
    @staticmethod
    def invalidate_cache_for_athlete(athlete_id: int) -> None:
        """Invalidate all cached metrics for a specific athlete."""
        invalidate_athlete_cache(athlete_id)
        print(f"[CACHE] Invalidated cache for athlete {athlete_id}")

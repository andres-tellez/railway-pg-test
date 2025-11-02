"""
Trend Analysis Service - Multi-Week Pattern Detection

Purpose:
    Analyze trends across 2-3 weeks to identify patterns:
    - Improving: Metrics getting better
    - Declining: Metrics getting worse
    - Stable: Metrics consistent

    Prevents overreaction to single-week anomalies.

Responsibilities:
    - Calculate rolling averages for each metric
    - Identify trend direction (improving/declining/stable)
    - Detect anomalies (outliers from trend)

Dependencies:
    - WeeklyMetricsService (for historical data)
    - WeekAnalysisResult (from Stage 2)

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from dataclasses import dataclass
from typing import List, Optional, Literal
from datetime import date
from sqlalchemy.orm import Session
import logging
import statistics

from .week_analysis_service import WeekAnalysisResult
from src.utils.adaptive_constants import (
    TREND_LOOKBACK_WEEKS,
    ANOMALY_THRESHOLD_SIGMA,
)

# Import WeeklyMetricsService inside function to avoid circular import

logger = logging.getLogger(__name__)


@dataclass
class TrendAnalysisResult:
    """Trend analysis across multiple weeks."""

    # Trend directions for each metric
    volume_trend: Literal["improving", "declining", "stable"]
    intensity_trend: Literal["improving", "declining", "stable"]
    consistency_trend: Literal["improving", "declining", "stable"]
    pace_trend: Literal["improving", "declining", "stable"]
    load_trend: Literal["improving", "declining", "stable"]

    # Rolling averages (3-week)
    volume_rolling_avg: float
    intensity_rolling_avg: float
    consistency_rolling_avg: float
    pace_deviation_rolling_avg: float
    load_delta_rolling_avg: Optional[float]

    # Anomaly detection
    has_anomalies: bool
    anomalies: List[str]  # ["volume_spike", "pace_sudden_change", etc.]

    # Weeks analyzed
    weeks_analyzed: int  # 1-3 weeks
    week_start_dates: List[date]


class TrendAnalysisService:
    """Service for analyzing multi-week trends."""

    @staticmethod
    def analyze_trends(
        session: Session,
        current_week_analysis: WeekAnalysisResult,
        plan_id: int,
        lookback_weeks: int = 2,
    ) -> TrendAnalysisResult:
        """
        Analyze trends across 2-3 weeks.

        Fetches historical metrics and calculates:
        - Rolling averages for each metric
        - Trend direction (improving/declining/stable)
        - Anomaly detection

        Args:
            session: SQLAlchemy session
            current_week_analysis: Current week's analysis
            plan_id: Plan ID for historical data lookup
            lookback_weeks: Number of weeks to look back (default: 2)

        Returns:
            TrendAnalysisResult with trend analysis
        """
        # Fetch historical metrics (import here to avoid circular import)
        from .weekly_metrics_service import WeeklyMetricsService

        historical_metrics = WeeklyMetricsService.get_historical_metrics(
            session, plan_id, weeks=lookback_weeks
        )

        # Convert to WeekAnalysisResult format (if needed)
        all_metrics = [current_week_analysis]
        week_start_dates = [current_week_analysis.week_start_date]

        # Add historical metrics (convert from WeeklyMetrics model if needed)
        for metrics in historical_metrics:
            # Convert WeeklyMetrics to WeekAnalysisResult-like structure
            historical_result = WeekAnalysisResult(
                volume_score=float(metrics.volume_score or 0),
                intensity_score=float(metrics.intensity_score or 0),
                consistency_score=float(metrics.consistency_score or 0),
                pace_deviation=float(metrics.pace_deviation or 0),
                avg_actual_pace=(
                    float(metrics.avg_actual_pace) if metrics.avg_actual_pace else None
                ),
                avg_planned_pace=(
                    float(metrics.avg_planned_pace)
                    if metrics.avg_planned_pace
                    else None
                ),
                consecutive_missed_days=metrics.consecutive_missed_days or 0,
                fatigue_markers=[],
                current_week_load=float(metrics.current_week_load or 0),
                previous_week_load=(
                    float(metrics.previous_week_load)
                    if metrics.previous_week_load
                    else None
                ),
                load_delta_pct=(
                    float(metrics.load_delta_pct) if metrics.load_delta_pct else None
                ),
                pace_threshold=float(metrics.pace_threshold or 10.0),
                hr_threshold=float(metrics.hr_threshold or 5.0),
                week_num=metrics.week_num,
                week_start_date=metrics.week_start_date,
                total_planned_miles=0.0,
                total_actual_miles=0.0,
                planned_workouts=0,
                completed_workouts=0,
            )
            all_metrics.append(historical_result)
            week_start_dates.append(metrics.week_start_date)

        weeks_analyzed = len(all_metrics)

        # Calculate rolling averages
        volume_values = [m.volume_score for m in all_metrics]
        intensity_values = [m.intensity_score for m in all_metrics]
        consistency_values = [m.consistency_score for m in all_metrics]
        pace_values = [m.pace_deviation for m in all_metrics]
        load_values = [
            m.load_delta_pct for m in all_metrics if m.load_delta_pct is not None
        ]

        volume_rolling_avg = statistics.mean(volume_values) if volume_values else 0.0
        intensity_rolling_avg = (
            statistics.mean(intensity_values) if intensity_values else 0.0
        )
        consistency_rolling_avg = (
            statistics.mean(consistency_values) if consistency_values else 0.0
        )
        pace_deviation_rolling_avg = (
            statistics.mean(pace_values) if pace_values else 0.0
        )
        load_delta_rolling_avg = statistics.mean(load_values) if load_values else None

        # Calculate trends
        volume_trend = TrendAnalysisService._calculate_trend(volume_values)
        intensity_trend = TrendAnalysisService._calculate_trend(intensity_values)
        consistency_trend = TrendAnalysisService._calculate_trend(consistency_values)
        pace_trend = TrendAnalysisService._calculate_trend(
            pace_values, reverse=True
        )  # Lower is better for pace
        load_trend = (
            TrendAnalysisService._calculate_trend(load_values)
            if load_values
            else "stable"
        )

        # Detect anomalies
        anomalies = []
        current = current_week_analysis

        anomaly = TrendAnalysisService._detect_anomalies(
            current.volume_score, volume_rolling_avg, "volume"
        )
        if anomaly:
            anomalies.append(anomaly)

        anomaly = TrendAnalysisService._detect_anomalies(
            current.intensity_score, intensity_rolling_avg, "intensity"
        )
        if anomaly:
            anomalies.append(anomaly)

        anomaly = TrendAnalysisService._detect_anomalies(
            current.pace_deviation, pace_deviation_rolling_avg, "pace"
        )
        if anomaly:
            anomalies.append(anomaly)

        return TrendAnalysisResult(
            volume_trend=volume_trend,
            intensity_trend=intensity_trend,
            consistency_trend=consistency_trend,
            pace_trend=pace_trend,
            load_trend=load_trend,
            volume_rolling_avg=volume_rolling_avg,
            intensity_rolling_avg=intensity_rolling_avg,
            consistency_rolling_avg=consistency_rolling_avg,
            pace_deviation_rolling_avg=pace_deviation_rolling_avg,
            load_delta_rolling_avg=load_delta_rolling_avg,
            has_anomalies=len(anomalies) > 0,
            anomalies=anomalies,
            weeks_analyzed=weeks_analyzed,
            week_start_dates=week_start_dates,
        )

    @staticmethod
    def _calculate_trend(
        values: List[float],
        reverse: bool = False,
    ) -> Literal["improving", "declining", "stable"]:
        """
        Determine trend direction from list of values.

        Rules:
        - Improving: Values increasing over time (or decreasing if reverse=True)
        - Declining: Values decreasing over time (or increasing if reverse=True)
        - Stable: No clear direction

        Uses simple linear regression or moving average comparison.
        """
        if len(values) < 2:
            return "stable"

        # Simple approach: compare first half vs second half
        mid_point = len(values) // 2
        first_half = values[:mid_point]
        second_half = values[mid_point:]

        first_avg = statistics.mean(first_half) if first_half else 0.0
        second_avg = statistics.mean(second_half) if second_half else 0.0

        diff = second_avg - first_avg
        threshold = max(5.0, abs(first_avg) * 0.1)  # 10% change or 5 points minimum

        if reverse:
            # For pace: lower is better
            if diff < -threshold:
                return "improving"  # Pace getting faster (lower)
            elif diff > threshold:
                return "declining"  # Pace getting slower (higher)
        else:
            # For scores: higher is better
            if diff > threshold:
                return "improving"  # Scores increasing
            elif diff < -threshold:
                return "declining"  # Scores decreasing

        return "stable"

    @staticmethod
    def _detect_anomalies(
        current_value: float,
        rolling_avg: float,
        metric_name: str,
    ) -> Optional[str]:
        """
        Detect anomalies in current week's metrics.

        Anomaly = value deviates >2 standard deviations from rolling average.
        """
        # Simple check: if current value is >50% different from average
        if rolling_avg == 0:
            return None

        deviation_pct = abs((current_value - rolling_avg) / rolling_avg)

        if deviation_pct > 0.5:  # 50% deviation
            if current_value > rolling_avg:
                return f"{metric_name}_spike"
            else:
                return f"{metric_name}_drop"

        return None

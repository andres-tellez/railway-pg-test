# Adaptive Training Plan Architecture

## Version 1.0 - Multi-Dimensional Analysis Pipeline

**Last Updated:** January 2026
**Status:** Design Phase
**Approach:** Layered Pipeline Architecture

---

## 📋 TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Component Specifications](#component-specifications)
4. [Data Flow Pipeline](#data-flow-pipeline)
5. [Configuration Management](#configuration-management)
6. [Database Schema](#database-schema)
7. [Code Organization](#code-organization)
8. [Integration Points](#integration-points)
9. [Testing Strategy](#testing-strategy)
10. [Implementation Roadmap](#implementation-roadmap)

---

## 🎯 EXECUTIVE SUMMARY

### **Core Principles**

1. **Clear Separation of Concerns**: Each component has a single, well-defined responsibility
2. **Centralized Configuration**: All thresholds, weights, and constants in one place
3. **Layered Pipeline**: Data → Analysis → Adjustment → Storage (no circular dependencies)
4. **No Spaghetti Code**: Clear data flow, no hidden dependencies
5. **Maintainable**: Inline documentation, type hints, clear naming
6. **Testable**: Pure functions where possible, dependency injection
7. **Pattern Consistency**: Follows existing codebase patterns

### **Architecture Pattern**

**5-Stage Pipeline:**

1. **Data Collection** (enhanced week log matching)
2. **Multi-Dimensional Analysis** (6 metrics calculation)
3. **Trend Analysis** (2-3 week lookback)
4. **Adaptive Adjustment** (phase-aware decision logic)
5. **Storage & Logging** (persist results and decisions)

Each stage is independent, testable, and can be evolved separately.

---

## 🏗️ ARCHITECTURE OVERVIEW

### **Component Hierarchy**

```
src/services/training_plan/
├── week_log_service.py              # Stage 1: Enhanced matching
├── week_analysis_service.py          # Stage 2: Multi-dimensional analysis (NEW)
├── trend_analysis_service.py         # Stage 3: Trend calculation (NEW)
├── adaptive_adjustment_service.py    # Stage 4: Phase-aware adjustments (NEW)
├── weekly_metrics_service.py        # Stage 5: Metrics persistence (NEW)
├── weekly_rebuild_service.py         # Orchestrator (modified)
└── adaptive_config.py                # Centralized configuration (NEW)

src/db/dao/
├── weekly_metrics_dao.py             # DAO for metrics storage (NEW)
└── weekly_decision_log_dao.py        # DAO for decision logging (NEW)

src/db/models/
├── weekly_metrics.py                  # WeeklyMetrics model (NEW)
└── weekly_decision_log.py            # WeeklyDecisionLog model (NEW)

src/utils/
└── adaptive_constants.py             # Shared constants (NEW)
```

### **Data Flow Diagram**

```
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 1: Enhanced Week Log Creation                             │
│ ─────────────────────────────────────────────────────────────── │
│ Input: PlanWorkout[] (planned), Activity[] (actual)             │
│ Process: Flexible matching (±2-3 days, ±30-40% distance)       │
│ Output: List[WeekLogRun] with match scores                     │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 2: Multi-Dimensional Analysis                             │
│ ─────────────────────────────────────────────────────────────── │
│ Input: List[WeekLogRun], PlanWorkout[]                          │
│ Process: Calculate 6 metrics (volume, intensity, consistency,  │
│          pace, recovery, load_delta)                            │
│ Output: WeekAnalysisResult (dataclass)                          │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 3: Trend Analysis                                          │
│ ─────────────────────────────────────────────────────────────── │
│ Input: WeekAnalysisResult (current), WeeklyMetrics[] (history)  │
│ Process: Calculate 2-3 week rolling trends                      │
│ Output: TrendAnalysisResult (dataclass)                         │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 4: Adaptive Adjustment                                     │
│ ─────────────────────────────────────────────────────────────── │
│ Input: WeekAnalysisResult, TrendAnalysisResult, Phase          │
│ Process: Phase-aware adjustment rules + safety constraints      │
│ Output: AdjustmentDecision (dataclass)                         │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 5: Storage & Logging                                       │
│ ─────────────────────────────────────────────────────────────── │
│ Input: WeekAnalysisResult, TrendAnalysisResult,                │
│        AdjustmentDecision                                        │
│ Process: Persist to weekly_metrics, log decision                │
│ Output: Saved metrics, decision log record                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 COMPONENT SPECIFICATIONS

### **STAGE 1: Enhanced Week Log Service**

**File:** `src/services/training_plan/week_log_service.py` (ENHANCE existing)

**Purpose:**

- Match planned workouts with actual Strava activities using flexible criteria
- Generate `WeekLogRun` entries with match scores

**Responsibilities:**

- Flexible matching algorithm (±2-3 days, ±30-40% distance)
- Multi-match scoring (1.0 → 0.4 → 0.0)
- Handle unmatched workouts (mark as missed)

**Pattern:**

```python
"""
Week Log Service - Enhanced Matching

Purpose:
    Match planned workouts with actual Strava activities using flexible criteria.
    Supports day shifting and distance variations common in real-world training.

Responsibilities:
    - Flexible matching (±2-3 days, ±30-40% distance)
    - Multi-match scoring system
    - Unmatched workout handling

Dependencies:
    - DataCollectionService (for Strava activities)
    - PlanWorkout model
    - Activity model

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import date, timedelta
from sqlalchemy.orm import Session
import logging

from .weekly_adjuster import WeekLogRun
from .data_collection_service import DataCollectionService
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.activities import Activity
from src.utils.adaptive_constants import (
    MATCH_DAY_WINDOW,
    MATCH_DISTANCE_TOLERANCE_EASY,
    MATCH_DISTANCE_TOLERANCE_QUALITY,
)

logger = logging.getLogger(__name__)


@dataclass
class WorkoutMatch:
    """Result of matching a planned workout with actual activity."""

    workout: PlanWorkout
    activity: Optional[Activity]  # None if no match
    match_score: float  # 1.0 = perfect, 0.0 = no match
    match_reason: str  # "perfect_match", "day_shifted", "distance_varied", etc.


class WeekLogService:
    """Service for creating week logs from planned workouts and actual activities."""

    @staticmethod
    def create_week_logs(
        session: Session,
        plan_id: int,
        week_num: int,
        race_date: date,
    ) -> List[WeekLogRun]:
        """
        Create week logs by matching planned workouts with actual activities.

        Uses flexible matching criteria:
        - Day window: ±3 days
        - Distance tolerance: ±40% for easy, ±20% for quality
        - Type matching: Must match workout type

        Args:
            session: SQLAlchemy session
            plan_id: Plan ID
            week_num: Week number (1-based)
            race_date: Race date for week calculation

        Returns:
            List of WeekLogRun entries with match scores
        """
        # Implementation details...
        pass

    @staticmethod
    def _match_workout_to_activities(
        workout: PlanWorkout,
        activities: List[Activity],
        week_start: date,
        week_end: date,
    ) -> WorkoutMatch:
        """
        Match a single planned workout to actual activities.

        Scoring:
        - Perfect match (same day, same distance, same type) = 1.0
        - Good match (same type, within 2 days, ±30% distance) = 0.8
        - Partial match (same type, within 3 days, ±40% distance) = 0.6
        - Type match only (correct type, wrong day/distance) = 0.4
        - No match = 0.0

        Returns:
            WorkoutMatch with best match found
        """
        # Implementation details...
        pass
```

**Key Features:**

- Centralized matching constants in `adaptive_constants.py`
- Clear scoring algorithm with documentation
- Returns structured `WorkoutMatch` dataclass
- Handles edge cases (no activities, multiple potential matches)

---

### **STAGE 2: Week Analysis Service**

**File:** `src/services/training_plan/week_analysis_service.py` (NEW)

**Purpose:**

- Calculate 6 core metrics from week logs and planned workouts
- Generate comprehensive analysis result

**Pattern:**

```python
"""
Week Analysis Service - Multi-Dimensional Metrics

Purpose:
    Calculate 6 core metrics from week logs to assess training performance:
    1. Volume Score (% of planned miles completed)
    2. Intensity Score (% of quality workouts completed)
    3. Consistency Score (% of planned days completed)
    4. Pace Trend (deviation from planned pace)
    5. Recovery Indicators (fatigue markers)
    6. Training Load Delta (week-over-week load change)

Responsibilities:
    - Calculate all 6 metrics
    - Generate comprehensive analysis result
    - Calculate dynamic thresholds for fatigue detection

Dependencies:
    - WeekLogService (for week logs)
    - AdaptiveConfig (for thresholds)
    - WorkoutUtils (for pace calculations)

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import date
from sqlalchemy.orm import Session
import logging

from .weekly_adjuster import WeekLogRun
from src.db.models.plan_workouts import PlanWorkout
from src.utils.adaptive_constants import AdaptiveConfig
from src.services.training_plan.workout_utils import seconds_to_pace_str

logger = logging.getLogger(__name__)


@dataclass
class WeekAnalysisResult:
    """Complete analysis of a week's training performance."""

    # Core metrics (0-100 scores)
    volume_score: float  # % of planned miles completed
    intensity_score: float  # % of quality workouts completed
    consistency_score: float  # % of planned days completed

    # Pace analysis
    pace_deviation: float  # seconds (negative = faster, positive = slower)
    avg_actual_pace: Optional[float]  # seconds per mile
    avg_planned_pace: Optional[float]  # seconds per mile

    # Recovery indicators
    consecutive_missed_days: int
    fatigue_markers: List[str]  # ["pace_declining", "hr_increasing", etc.]

    # Training load
    current_week_load: float  # Proxy TSS (distance × RPE)
    previous_week_load: Optional[float]
    load_delta_pct: Optional[float]  # % change from previous week

    # Dynamic thresholds (calculated from baseline)
    pace_threshold: float  # Dynamic threshold for fatigue detection
    hr_threshold: float  # Dynamic threshold for fatigue detection

    # Metadata
    week_num: int
    week_start_date: date
    total_planned_miles: float
    total_actual_miles: float
    planned_workouts: int
    completed_workouts: int


class WeekAnalysisService:
    """Service for analyzing week performance across multiple dimensions."""

    @staticmethod
    def analyze_week(
        session: Session,
        week_logs: List[WeekLogRun],
        planned_workouts: List[PlanWorkout],
        week_num: int,
        week_start_date: date,
        previous_week_metrics: Optional['WeekAnalysisResult'] = None,
    ) -> WeekAnalysisResult:
        """
        Analyze week performance across 6 dimensions.

        Calculates:
        - Volume score: actual_miles / planned_miles
        - Intensity score: quality_completed / quality_planned
        - Consistency score: days_completed / days_planned
        - Pace trend: avg_actual_pace - avg_planned_pace
        - Recovery indicators: fatigue markers
        - Load delta: (current_load - prev_load) / prev_load

        Also calculates dynamic thresholds for fatigue detection.

        Args:
            session: SQLAlchemy session (for fetching previous week data)
            week_logs: List of WeekLogRun entries
            planned_workouts: List of planned workouts for the week
            week_num: Week number
            week_start_date: Week start date (Monday)
            previous_week_metrics: Optional previous week metrics for load delta

        Returns:
            WeekAnalysisResult with all metrics calculated
        """
        # Implementation: Calculate each metric
        pass

    @staticmethod
    def _calculate_volume_score(
        week_logs: List[WeekLogRun],
        planned_workouts: List[PlanWorkout],
    ) -> float:
        """Calculate volume score (0-100%)."""
        pass

    @staticmethod
    def _calculate_intensity_score(
        week_logs: List[WeekLogRun],
        planned_workouts: List[PlanWorkout],
    ) -> float:
        """Calculate intensity score (0-100%)."""
        pass

    @staticmethod
    def _calculate_consistency_score(
        week_logs: List[WeekLogRun],
        planned_workouts: List[PlanWorkout],
    ) -> float:
        """Calculate consistency score (0-100%)."""
        pass

    @staticmethod
    def _calculate_pace_trend(
        week_logs: List[WeekLogRun],
        planned_workouts: List[PlanWorkout],
    ) -> Dict[str, Optional[float]]:
        """
        Calculate pace trend analysis.

        Returns:
            {
                "pace_deviation": float,  # seconds
                "avg_actual_pace": Optional[float],
                "avg_planned_pace": Optional[float],
            }
        """
        pass

    @staticmethod
    def _calculate_recovery_indicators(
        week_logs: List[WeekLogRun],
        planned_workouts: List[PlanWorkout],
    ) -> Dict[str, Any]:
        """
        Calculate recovery indicators (fatigue markers).

        Returns:
            {
                "consecutive_missed_days": int,
                "fatigue_markers": List[str],
            }
        """
        pass

    @staticmethod
    def _calculate_training_load(
        week_logs: List[WeekLogRun],
        previous_week_load: Optional[float] = None,
    ) -> Dict[str, Optional[float]]:
        """
        Calculate training load (proxy TSS) and delta.

        Proxy TSS = Σ(distance_mi × estimated_rpe)

        Returns:
            {
                "current_week_load": float,
                "previous_week_load": Optional[float],
                "load_delta_pct": Optional[float],
            }
        """
        pass

    @staticmethod
    def _calculate_dynamic_thresholds(
        session: Session,
        user_id: str,
        week_start_date: date,
    ) -> Dict[str, float]:
        """
        Calculate dynamic thresholds for fatigue detection.

        Uses last 2-3 weeks of easy runs to establish baseline:
        - Pace threshold: max(10s, 2% of baseline pace)
        - HR threshold: 3% of baseline HR

        Returns:
            {
                "pace_threshold": float,
                "hr_threshold": float,
            }
        """
        pass
```

**Key Features:**

- All 6 metrics calculated in one service
- Returns structured `WeekAnalysisResult` dataclass
- Pure calculation methods (testable)
- Dynamic threshold calculation
- Clear separation of metric calculations

---

### **STAGE 3: Trend Analysis Service**

**File:** `src/services/training_plan/trend_analysis_service.py` (NEW)

**Purpose:**

- Analyze 2-3 week trends across all metrics
- Identify improving/declining/stable patterns

**Pattern:**

```python
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

from .week_analysis_service import WeekAnalysisResult
from .weekly_metrics_service import WeeklyMetricsService

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
        pass

    @staticmethod
    def _calculate_trend(
        values: List[float],
    ) -> Literal["improving", "declining", "stable"]:
        """
        Determine trend direction from list of values.

        Rules:
        - Improving: Values increasing over time
        - Declining: Values decreasing over time
        - Stable: No clear direction

        Uses simple linear regression or moving average comparison.
        """
        pass

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
        pass
```

**Key Features:**

- Fetches historical metrics from database
- Calculates rolling averages
- Identifies trend directions
- Anomaly detection

---

### **STAGE 4: Adaptive Adjustment Service**

**File:** `src/services/training_plan/adaptive_adjustment_service.py` (NEW)

**Purpose:**

- Apply phase-aware adjustment rules
- Calculate pace seed adjustments
- Enforce safety constraints
- Generate adjustment decisions

**Pattern:**

```python
"""
Adaptive Adjustment Service - Phase-Aware Decision Logic

Purpose:
    Apply phase-aware adjustment rules based on week analysis and trends.
    Different rules for Base/Build/Peak/Taper phases.
    Enforces safety constraints to prevent dangerous adjustments.

Responsibilities:
    - Apply phase-specific adjustment rules
    - Calculate pace seed adjustments
    - Enforce safety constraints (max ±15% volume, ±10s/mile pace)
    - Generate weighted match_score
    - Create adjustment decisions with explanations

Dependencies:
    - WeekAnalysisResult (from Stage 2)
    - TrendAnalysisResult (from Stage 3)
    - AdaptiveConfig (for phase rules and constraints)
    - PaceSeedService (for pace adjustments)

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from dataclasses import dataclass
from typing import List, Optional, Literal
from sqlalchemy.orm import Session
import logging

from .week_analysis_service import WeekAnalysisResult
from .trend_analysis_service import TrendAnalysisResult
from .pace_seed_service import PaceSeed
from src.utils.adaptive_constants import AdaptiveConfig

logger = logging.getLogger(__name__)


@dataclass
class AdjustmentDecision:
    """Final adjustment decision with explanation."""

    # Decision type
    decision_type: Literal[
        "no_change",
        "volume_increase",
        "volume_decrease",
        "pace_increase",
        "pace_decrease",
        "quality_disable",
        "quality_enable",
        "fatigue_reduction",
    ]

    # Adjustments to apply
    volume_change_pct: float  # Percentage change (-15 to +15)
    pace_adjustment_sec: float  # Seconds per mile (-10 to +10)
    disable_quality_workouts: bool

    # Trigger information
    trigger_reason: str  # Human-readable explanation
    metrics_used: Dict[str, float]  # Which metrics triggered this

    # Composite score
    match_score: float  # Weighted composite (0.0-1.0)

    # Phase context
    phase: str  # "Base", "Build", "Peak", "Taper"
    weeks_remaining: int

    # Safety overrides
    safety_constraints_applied: List[str]  # ["volume_capped_15pct", etc.]


class AdaptiveAdjustmentService:
    """Service for calculating phase-aware adjustments."""

    @staticmethod
    def calculate_adjustment(
        analysis: WeekAnalysisResult,
        trends: TrendAnalysisResult,
        current_seed: PaceSeed,
        phase: str,
        weeks_remaining: int,
    ) -> AdjustmentDecision:
        """
        Calculate adjustment decision based on analysis and trends.

        Applies phase-specific rules:
        - Base: Focus on volume, lenient on pace
        - Build: Balance volume + intensity
        - Peak: Quality critical, strict on paces
        - Taper: Minimal changes, safety only

        Enforces safety constraints:
        - Max ±15% volume change
        - Max ±10s/mile pace change
        - Progressive constraints based on weeks remaining

        Args:
            analysis: Current week's analysis
            trends: Multi-week trend analysis
            current_seed: Current pace seed
            phase: Training phase ("Base", "Build", "Peak", "Taper")
            weeks_remaining: Weeks until race

        Returns:
            AdjustmentDecision with all adjustments and explanations
        """
        pass

    @staticmethod
    def _calculate_match_score(
        analysis: WeekAnalysisResult,
        phase: str,
    ) -> float:
        """
        Calculate weighted composite match_score.

        Base phase weights:
        - 0.5 * volume + 0.2 * intensity + 0.2 * consistency + 0.1 * recovery

        Peak phase weights:
        - 0.3 * volume + 0.4 * intensity + 0.2 * consistency + 0.1 * recovery

        Returns:
            Composite score (0.0-1.0)
        """
        pass

    @staticmethod
    def _apply_base_phase_rules(
        analysis: WeekAnalysisResult,
        trends: TrendAnalysisResult,
    ) -> AdjustmentDecision:
        """Apply Base phase adjustment rules."""
        pass

    @staticmethod
    def _apply_build_phase_rules(
        analysis: WeekAnalysisResult,
        trends: TrendAnalysisResult,
    ) -> AdjustmentDecision:
        """Apply Build phase adjustment rules."""
        pass

    @staticmethod
    def _apply_peak_phase_rules(
        analysis: WeekAnalysisResult,
        trends: TrendAnalysisResult,
    ) -> AdjustmentDecision:
        """Apply Peak phase adjustment rules."""
        pass

    @staticmethod
    def _apply_taper_phase_rules(
        analysis: WeekAnalysisResult,
        trends: TrendAnalysisResult,
    ) -> AdjustmentDecision:
        """Apply Taper phase adjustment rules."""
        pass

    @staticmethod
    def _detect_fatigue(
        analysis: WeekAnalysisResult,
        trends: TrendAnalysisResult,
    ) -> bool:
        """
        Detect fatigue patterns using dynamic thresholds.

        Fatigue detected if ALL of:
        - Load delta >15%
        - Pace slower than dynamic threshold
        - HR higher than dynamic threshold

        Returns:
            True if fatigue pattern detected
        """
        pass

    @staticmethod
    def _apply_safety_constraints(
        decision: AdjustmentDecision,
        previous_week_volume: float,
        weeks_remaining: int,
    ) -> AdjustmentDecision:
        """
        Apply final safety constraints to adjustment decision.

        Constraints:
        - Max ±15% volume change (hard limit)
        - Max ±10s/mile pace change (hard limit)
        - Progressive limits based on weeks remaining:
          * >8 weeks: Allow ±10s, ±15%
          * 4-8 weeks: Allow ±5s, ±10%
          * <4 weeks: Allow ±3s, ±5%

        Returns:
            Modified decision with constraints applied
        """
        pass
```

**Key Features:**

- Phase-specific rule methods (clear separation)
- Safety constraint enforcement (final check)
- Weighted match_score calculation
- Fatigue detection using dynamic thresholds
- Structured decision output

---

### **STAGE 5: Weekly Metrics Service**

**File:** `src/services/training_plan/weekly_metrics_service.py` (NEW)

**Purpose:**

- Persist weekly metrics to database
- Store decision logs
- Provide historical querying

**Pattern:**

```python
"""
Weekly Metrics Service - Metrics Persistence

Purpose:
    Persist weekly analysis metrics and decision logs to database.
    Enables historical trend analysis and future ML features.

Responsibilities:
    - Save weekly metrics to weekly_metrics table
    - Save decision logs to weekly_decision_log table
    - Query historical metrics for trend analysis

Dependencies:
    - WeeklyMetricsDAO (database operations)
    - WeeklyDecisionLogDAO (database operations)
    - WeekAnalysisResult (from Stage 2)
    - AdjustmentDecision (from Stage 4)

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session
import logging

from .week_analysis_service import WeekAnalysisResult
from .adaptive_adjustment_service import AdjustmentDecision
from src.db.dao.weekly_metrics_dao import WeeklyMetricsDAO
from src.db.dao.weekly_decision_log_dao import WeeklyDecisionLogDAO

logger = logging.getLogger(__name__)


class WeeklyMetricsService:
    """Service for persisting and querying weekly metrics."""

    @staticmethod
    def save_week_metrics(
        session: Session,
        plan_id: int,
        analysis: WeekAnalysisResult,
        decision: AdjustmentDecision,
    ) -> int:
        """
        Save weekly metrics and decision log to database.

        Creates records in:
        - weekly_metrics table
        - weekly_decision_log table

        Returns:
            ID of saved weekly_metrics record
        """
        pass

    @staticmethod
    def get_historical_metrics(
        session: Session,
        plan_id: int,
        weeks: int = 3,
    ) -> List[WeekAnalysisResult]:
        """
        Get historical metrics for trend analysis.

        Args:
            session: SQLAlchemy session
            plan_id: Plan ID
            weeks: Number of weeks to fetch (default: 3)

        Returns:
            List of WeekAnalysisResult (most recent first)
        """
        pass

    @staticmethod
    def get_decision_logs(
        session: Session,
        plan_id: int,
        week_num: Optional[int] = None,
    ) -> List[dict]:
        """
        Get decision logs for a plan (or specific week).

        Returns:
            List of decision log dictionaries
        """
        pass
```

**Key Features:**

- Separate DAOs for database operations
- Service layer for business logic
- Historical querying support

---

### **CENTRALIZED CONFIGURATION**

**File:** `src/utils/adaptive_constants.py` (NEW)

**Purpose:**

- Centralize all thresholds, weights, and configuration
- Single source of truth
- Easy to adjust without code changes

**Pattern:**

```python
"""
Adaptive Training Constants - Centralized Configuration

Purpose:
    Centralize all thresholds, weights, and configuration values
    for adaptive training plan adjustments.

    Single source of truth prevents drift and makes tuning easy.

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from dataclasses import dataclass
from typing import Dict


# ============================================================================
# MATCHING CONFIGURATION
# ============================================================================

# Day window for flexible matching (±days)
MATCH_DAY_WINDOW = 3  # Match within ±3 days

# Distance tolerance for matching
MATCH_DISTANCE_TOLERANCE_EASY = 0.40  # ±40% for easy runs
MATCH_DISTANCE_TOLERANCE_QUALITY = 0.20  # ±20% for quality workouts

# Match score thresholds
MATCH_SCORE_PERFECT = 1.0  # Same day, same distance, same type
MATCH_SCORE_GOOD = 0.8  # Same type, within 2 days, ±30% distance
MATCH_SCORE_PARTIAL = 0.6  # Same type, within 3 days, ±40% distance
MATCH_SCORE_TYPE_ONLY = 0.4  # Correct type, wrong day/distance
MATCH_SCORE_NONE = 0.0  # No match


# ============================================================================
# METRIC THRESHOLDS
# ============================================================================

# Volume score thresholds
VOLUME_SCORE_LOW = 0.70  # <70% = low completion
VOLUME_SCORE_GOOD = 0.90  # ≥90% = good completion

# Intensity score thresholds
INTENSITY_SCORE_LOW = 0.60  # <60% = low quality completion
INTENSITY_SCORE_GOOD = 0.80  # ≥80% = good quality completion

# Consistency score thresholds
CONSISTENCY_SCORE_LOW = 0.60  # <60% = low consistency


# ============================================================================
# PHASE-SPECIFIC ADJUSTMENT RULES
# ============================================================================

@dataclass
class PhaseRules:
    """Adjustment rules for a specific training phase."""

    volume_low_threshold: float
    volume_good_threshold: float
    intensity_low_threshold: float
    pace_adjustment_max: float  # seconds per mile
    volume_adjustment_max: float  # percentage
    allow_volume_increase: bool
    allow_pace_increase: bool
    match_score_weights: Dict[str, float]  # Weighting for match_score


# Phase-specific rules
BASE_PHASE_RULES = PhaseRules(
    volume_low_threshold=0.70,
    volume_good_threshold=0.90,
    intensity_low_threshold=0.60,
    pace_adjustment_max=15.0,  # More lenient
    volume_adjustment_max=15.0,
    allow_volume_increase=True,
    allow_pace_increase=True,
    match_score_weights={
        "volume": 0.5,
        "intensity": 0.2,
        "consistency": 0.2,
        "recovery": 0.1,
    },
)

BUILD_PHASE_RULES = PhaseRules(
    volume_low_threshold=0.75,
    volume_good_threshold=0.90,
    intensity_low_threshold=0.60,
    pace_adjustment_max=10.0,
    volume_adjustment_max=15.0,
    allow_volume_increase=True,
    allow_pace_increase=True,
    match_score_weights={
        "volume": 0.4,
        "intensity": 0.3,
        "consistency": 0.2,
        "recovery": 0.1,
    },
)

PEAK_PHASE_RULES = PhaseRules(
    volume_low_threshold=0.75,
    volume_good_threshold=0.90,
    intensity_low_threshold=0.70,  # Stricter on quality
    pace_adjustment_max=10.0,
    volume_adjustment_max=15.0,
    allow_volume_increase=False,  # Don't increase in peak
    allow_pace_increase=False,
    match_score_weights={
        "volume": 0.3,
        "intensity": 0.4,  # Prioritize quality
        "consistency": 0.2,
        "recovery": 0.1,
    },
)

TAPER_PHASE_RULES = PhaseRules(
    volume_low_threshold=0.50,  # Very lenient
    volume_good_threshold=0.90,
    intensity_low_threshold=0.70,
    pace_adjustment_max=5.0,  # Very strict
    volume_adjustment_max=10.0,  # Very strict
    allow_volume_increase=False,  # Never increase in taper
    allow_pace_increase=False,
    match_score_weights={
        "volume": 0.2,
        "intensity": 0.4,
        "consistency": 0.3,
        "recovery": 0.1,
    },
)


# ============================================================================
# FATIGUE DETECTION CONFIGURATION
# ============================================================================

# Dynamic threshold percentages
FATIGUE_PACE_THRESHOLD_PCT = 0.02  # 2% of baseline pace
FATIGUE_HR_THRESHOLD_PCT = 0.03  # 3% of baseline HR
FATIGUE_PACE_THRESHOLD_MIN = 10.0  # Minimum 10 seconds
FATIGUE_LOAD_DELTA_THRESHOLD = 0.15  # 15% load increase

# Lookback period for baseline calculation
FATIGUE_BASELINE_WEEKS = 2  # Use last 2 weeks for baseline


# ============================================================================
# SAFETY CONSTRAINTS
# ============================================================================

# Hard limits (absolute maximums)
MAX_VOLUME_CHANGE_PCT = 15.0  # Never exceed ±15% volume change
MAX_PACE_CHANGE_SEC = 10.0  # Never exceed ±10 seconds/mile

# Progressive limits based on weeks remaining
SAFETY_LIMITS_BY_WEEKS_REMAINING = {
    "high": {  # >8 weeks
        "max_volume_pct": 15.0,
        "max_pace_sec": 10.0,
    },
    "medium": {  # 4-8 weeks
        "max_volume_pct": 10.0,
        "max_pace_sec": 5.0,
    },
    "low": {  # <4 weeks
        "max_volume_pct": 5.0,
        "max_pace_sec": 3.0,
    },
}


# ============================================================================
# TREND ANALYSIS CONFIGURATION
# ============================================================================

# Lookback period for trends
TREND_LOOKBACK_WEEKS = 2  # Analyze 2 weeks back
TREND_ROLLING_AVG_WEEKS = 3  # 3-week rolling average

# Anomaly detection threshold (standard deviations)
ANOMALY_THRESHOLD_SIGMA = 2.0


# ============================================================================
# GRACE PERIODS
# ============================================================================

# First N weeks of plan (lenient matching)
GRACE_PERIOD_WEEKS = 2

# Rebuild ramp after missed week
REBUILD_RAMP_PCT = 0.80  # Resume at 80% of previous load


class AdaptiveConfig:
    """Centralized configuration accessor."""

    @staticmethod
    def get_phase_rules(phase: str) -> PhaseRules:
        """Get phase-specific rules."""
        rules_map = {
            "Base": BASE_PHASE_RULES,
            "Build": BUILD_PHASE_RULES,
            "Peak": PEAK_PHASE_RULES,
            "Taper": TAPER_PHASE_RULES,
        }
        return rules_map.get(phase, BUILD_PHASE_RULES)

    @staticmethod
    def get_safety_limits(weeks_remaining: int) -> Dict[str, float]:
        """Get safety limits based on weeks remaining."""
        if weeks_remaining > 8:
            return SAFETY_LIMITS_BY_WEEKS_REMAINING["high"]
        elif weeks_remaining >= 4:
            return SAFETY_LIMITS_BY_WEEKS_REMAINING["medium"]
        else:
            return SAFETY_LIMITS_BY_WEEKS_REMAINING["low"]
```

**Key Features:**

- All configuration in one place
- Phase-specific rules as dataclasses
- Easy to adjust without touching logic code
- Clear documentation for each constant

---

### **ORCHESTRATOR: Weekly Rebuild Service**

**File:** `src/services/training_plan/weekly_rebuild_service.py` (MODIFY existing)

**Purpose:**

- Orchestrate the 5-stage pipeline
- Coordinate all services
- Apply adjustments to pace seed
- Rebuild workout details

**Pattern:**

```python
"""
Weekly Rebuild Service - Orchestrator

Purpose:
    Orchestrate the adaptive training plan rebuild pipeline:
    1. Create enhanced week logs (Stage 1)
    2. Analyze week performance (Stage 2)
    3. Analyze trends (Stage 3)
    4. Calculate adjustments (Stage 4)
    5. Persist metrics and decisions (Stage 5)
    6. Apply adjustments and rebuild workouts

This service coordinates all stages but delegates specific logic
to specialized services.

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from typing import Dict, Any, List, Optional
from datetime import date
from sqlalchemy.orm import Session
import logging

# Stage services
from .week_log_service import WeekLogService
from .week_analysis_service import WeekAnalysisService
from .trend_analysis_service import TrendAnalysisService
from .adaptive_adjustment_service import AdaptiveAdjustmentService
from .weekly_metrics_service import WeeklyMetricsService

# Existing services
from .pace_seed_service import PaceSeed, get_initial_pace_seed
from .pass4_workout_details import Pass4WorkoutDetails
from .workout_comparison_service import WorkoutComparisonService

logger = logging.getLogger(__name__)


class WeeklyRebuildService:
    """Service for rebuilding workout details with adaptive adjustments."""

    @staticmethod
    def rebuild_week(
        session: Session,
        plan_id: int,
        week_num: int,
        initial_seed: Optional[PaceSeed] = None,
    ) -> Dict[str, Any]:
        """
        Rebuild week with adaptive adjustments.

        Pipeline:
        1. Create enhanced week logs (flexible matching)
        2. Analyze current week (6 metrics)
        3. Analyze trends (2-3 week lookback)
        4. Calculate adjustments (phase-aware)
        5. Persist metrics and decisions
        6. Apply adjustments to pace seed
        7. Rebuild workout details

        Returns:
            Complete rebuild result with original/updated workouts
        """
        # STAGE 1: Create enhanced week logs
        week_logs = WeekLogService.create_week_logs(
            session=session,
            plan_id=plan_id,
            week_num=week_num - 1,  # Previous week
            race_date=plan.race_date,
        )

        # STAGE 2: Analyze current week
        analysis = WeekAnalysisService.analyze_week(
            session=session,
            week_logs=week_logs,
            planned_workouts=planned_workouts,
            week_num=week_num - 1,
            week_start_date=previous_week_start,
            previous_week_metrics=previous_metrics,
        )

        # STAGE 3: Analyze trends
        trends = TrendAnalysisService.analyze_trends(
            session=session,
            current_week_analysis=analysis,
            plan_id=plan_id,
            lookback_weeks=2,
        )

        # STAGE 4: Calculate adjustments
        decision = AdaptiveAdjustmentService.calculate_adjustment(
            analysis=analysis,
            trends=trends,
            current_seed=current_seed,
            phase=phase,
            weeks_remaining=weeks_remaining,
        )

        # STAGE 5: Persist metrics and decisions
        WeeklyMetricsService.save_week_metrics(
            session=session,
            plan_id=plan_id,
            analysis=analysis,
            decision=decision,
        )

        # Apply adjustments and rebuild
        adjusted_seed = _apply_decision_to_seed(current_seed, decision)
        week_with_details = _rebuild_workout_details(adjusted_seed, ...)

        return {
            "week_number": week_num,
            "phase": phase,
            "adjustment_decision": decision,
            "original_workouts": ...,
            "updated_workouts": ...,
        }
```

**Key Features:**

- Clear pipeline stages
- Delegates to specialized services
- No business logic in orchestrator
- Easy to test each stage independently

---

## 🗄️ DATABASE SCHEMA

### **Weekly Metrics Table**

```python
# src/db/models/weekly_metrics.py

from sqlalchemy import Column, Integer, Date, DECIMAL, JSON, TIMESTAMP, UniqueConstraint
from sqlalchemy.sql import func
from src.db.db_session import Base


class WeeklyMetrics(Base):
    """Weekly training performance metrics."""

    __tablename__ = "weekly_metrics"

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, nullable=False, index=True)
    week_num = Column(Integer, nullable=False)
    week_start_date = Column(Date, nullable=False)

    # Core metrics (0-100 scores)
    volume_score = Column(DECIMAL(5, 2))
    intensity_score = Column(DECIMAL(5, 2))
    consistency_score = Column(DECIMAL(5, 2))

    # Pace analysis (seconds)
    pace_deviation = Column(DECIMAL(6, 2))
    avg_actual_pace = Column(DECIMAL(6, 2))
    avg_planned_pace = Column(DECIMAL(6, 2))

    # Recovery indicators
    consecutive_missed_days = Column(Integer, default=0)

    # Training load
    current_week_load = Column(DECIMAL(8, 2))
    previous_week_load = Column(DECIMAL(8, 2))
    load_delta_pct = Column(DECIMAL(6, 2))

    # Dynamic thresholds
    pace_threshold = Column(DECIMAL(6, 2))
    hr_threshold = Column(DECIMAL(6, 2))

    # Composite score
    match_score = Column(DECIMAL(4, 2))

    # Context (future enhancement)
    context_score = Column(JSON)

    # Metadata
    phase = Column(String(20))
    weeks_remaining = Column(Integer)
    created_at = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("plan_id", "week_num", name="uq_plan_week"),
    )
```

### **Weekly Decision Log Table**

```python
# src/db/models/weekly_decision_log.py

from sqlalchemy import Column, Integer, Date, String, Text, JSON, TIMESTAMP
from sqlalchemy.sql import func
from src.db.db_session import Base


class WeeklyDecisionLog(Base):
    """Log of adjustment decisions with explanations."""

    __tablename__ = "weekly_decision_log"

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, nullable=False, index=True)
    week_num = Column(Integer, nullable=False)
    week_start_date = Column(Date, nullable=False)

    # Decision details
    decision_type = Column(String(50))  # "fatigue_reduction", etc.
    trigger_reason = Column(Text)  # Human-readable explanation

    # Metrics used (JSON)
    metrics_json = Column(JSON)  # All 6 metrics + trends

    # Adjustments applied (JSON)
    adjustments_json = Column(JSON)  # Volume, pace, quality changes

    # Composite score
    match_score = Column(DECIMAL(4, 2))

    # Context
    phase = Column(String(20))
    weeks_remaining = Column(Integer)
    created_at = Column(TIMESTAMP, server_default=func.now())
```

---

## 📁 CODE ORGANIZATION

### **Directory Structure**

```
src/
├── services/
│   └── training_plan/
│       ├── __init__.py
│       ├── week_log_service.py              # STAGE 1 (enhance)
│       ├── week_analysis_service.py          # STAGE 2 (new)
│       ├── trend_analysis_service.py         # STAGE 3 (new)
│       ├── adaptive_adjustment_service.py    # STAGE 4 (new)
│       ├── weekly_metrics_service.py        # STAGE 5 (new)
│       ├── weekly_rebuild_service.py        # ORCHESTRATOR (modify)
│       ├── adaptive_config.py               # CONFIG (new)
│       └── ... (existing services)
│
├── db/
│   ├── dao/
│   │   ├── weekly_metrics_dao.py            # NEW
│   │   └── weekly_decision_log_dao.py        # NEW
│   │
│   └── models/
│       ├── weekly_metrics.py                 # NEW
│       └── weekly_decision_log.py            # NEW
│
└── utils/
    └── adaptive_constants.py                # NEW (moved from service)
```

### **Import Pattern**

```python
# Services import from:
# - Other services (for orchestration)
# - DAOs (for database access)
# - Utils (for constants/helpers)
# - Models (for type hints only)

# DAOs import from:
# - Models only
# - Session

# Models import from:
# - Base (SQLAlchemy)
# - Nothing else
```

---

## 🔗 INTEGRATION POINTS

### **1. Weekly Rebuild Service Integration**

```python
# In weekly_rebuild_service.py

# Replace old logic:
# old_week_logs = fetch_week_logs(...)
# current_seed, disable_quality = adjust_seed_from_week(seed, old_week_logs)

# With new pipeline:
week_logs = WeekLogService.create_week_logs(...)
analysis = WeekAnalysisService.analyze_week(...)
trends = TrendAnalysisService.analyze_trends(...)
decision = AdaptiveAdjustmentService.calculate_adjustment(...)
WeeklyMetricsService.save_week_metrics(...)

# Apply decision
adjusted_seed = _apply_decision_to_seed(current_seed, decision)
```

### **2. Email Service Integration**

```python
# Email service can now use decision log
decision_log = WeeklyMetricsService.get_decision_logs(
    session=session,
    plan_id=plan_id,
    week_num=week_num,
)

# Include in email:
email_content = f"""
Your plan was adjusted because:
{decision_log.trigger_reason}

Metrics used:
- Volume completion: {decision_log.metrics_json['volume_score']}%
- Fatigue pattern detected: {decision_log.metrics_json.get('fatigue_detected', False)}
"""
```

### **3. API Endpoint Integration**

```python
# New endpoint: GET /api/plans/{plan_id}/adjustments/{week_num}
def get_week_adjustment_explanation(plan_id, week_num):
    """Return why adjustments were made."""
    decision = WeeklyMetricsService.get_decision_logs(
        session, plan_id, week_num
    )
    return jsonify({
        "decision": decision.decision_type,
        "reason": decision.trigger_reason,
        "metrics": decision.metrics_json,
        "adjustments": decision.adjustments_json,
    })
```

---

## 🧪 TESTING STRATEGY

### **Unit Tests (Each Service)**

```python
# tests/services/training_plan/test_week_analysis_service.py

def test_calculate_volume_score():
    """Test volume score calculation."""
    week_logs = [...]
    planned_workouts = [...]
    result = WeekAnalysisService._calculate_volume_score(week_logs, planned_workouts)
    assert 0 <= result <= 100

def test_calculate_intensity_score():
    """Test intensity score calculation."""
    # Test cases: 0 quality, 50% quality, 100% quality

def test_dynamic_thresholds():
    """Test dynamic threshold calculation."""
    # Test: 7:00/mi runner vs 10:00/mi runner
```

### **Integration Tests (Pipeline)**

```python
# tests/services/training_plan/test_adaptive_pipeline.py

def test_full_pipeline_base_phase():
    """Test full pipeline for Base phase."""
    # Create week logs → Analyze → Trends → Adjust → Save
    # Verify all stages work together

def test_fatigue_detection_triggers_reduction():
    """Test that fatigue detection triggers volume reduction."""
    # Setup: High load, pace slowing, HR rising
    # Verify: Decision includes fatigue_reduction
```

---

## 🚀 IMPLEMENTATION ROADMAP

### **Phase 1: Foundation (Week 1)**

1. **Create configuration module**

   - `src/utils/adaptive_constants.py`
   - All thresholds and weights

2. **Create database models**

   - `src/db/models/weekly_metrics.py`
   - `src/db/models/weekly_decision_log.py`
   - Migration script

3. **Create DAOs**
   - `src/db/dao/weekly_metrics_dao.py`
   - `src/db/dao/weekly_decision_log_dao.py`

### **Phase 2: Core Services (Week 1-2)**

4. **Enhance Week Log Service**

   - Add flexible matching
   - Add match scoring
   - Update tests

5. **Create Week Analysis Service**

   - Calculate all 6 metrics
   - Dynamic thresholds
   - Unit tests

6. **Create Trend Analysis Service**

   - Multi-week analysis
   - Anomaly detection
   - Unit tests

7. **Create Adaptive Adjustment Service**

   - Phase-aware rules
   - Safety constraints
   - Unit tests

8. **Create Weekly Metrics Service**
   - Persistence logic
   - Historical querying
   - Unit tests

### **Phase 3: Integration (Week 2)**

9. **Update Weekly Rebuild Service**

   - Integrate new pipeline
   - Remove old logic
   - Integration tests

10. **Update Email Service**

    - Use decision logs
    - Include explanation

11. **Add API Endpoints**
    - Get adjustment explanation
    - Get historical metrics

### **Phase 4: Testing & Refinement (Week 3)**

12. **End-to-End Testing**

    - Full pipeline tests
    - Edge cases
    - Performance testing

13. **Documentation**
    - Inline docstrings
    - Architecture diagrams
    - Usage examples

---

## 🎯 KEY DESIGN PRINCIPLES

### **1. Single Responsibility**

- Each service does ONE thing
- Each method has ONE purpose
- Clear separation of concerns

### **2. Dependency Injection**

- Services receive dependencies (Session, config) as parameters
- No hidden dependencies
- Easy to test

### **3. Immutable Data Transfer**

- Use dataclasses for data transfer between stages
- No mutation of shared state
- Clear data contracts

### **4. Centralized Configuration**

- All constants in one place
- Easy to tune without code changes
- Documented thresholds

### **5. Pipeline Architecture**

- Clear stages (no circular dependencies)
- Each stage has defined inputs/outputs
- Easy to add new stages

### **6. Comprehensive Logging**

- Log all decisions and reasons
- Enable debugging and analysis
- Support future ML features

### **7. Type Hints Everywhere**

- All function signatures typed
- Dataclasses for structured data
- Better IDE support and catching errors

---

## 📝 DOCUMENTATION STANDARDS

### **Service Docstrings**

```python
"""
Service Name - Purpose

Purpose:
    One-sentence description of what this service does.

Responsibilities:
    - Responsibility 1
    - Responsibility 2
    - Responsibility 3

Dependencies:
    - Service1 (for X)
    - Service2 (for Y)
    - Model1 (for type hints)

Testing:
    See tests/services/training_plan/test_service_name.py

Author: SmartCoach Development Team
Last Updated: January 2026
"""
```

### **Method Docstrings**

```python
def method_name(param1: Type1, param2: Type2) -> ReturnType:
    """
    Brief description of what this method does.

    More detailed explanation if needed.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When this error occurs

    Example:
        >>> result = method_name(arg1, arg2)
        >>> print(result)
        expected_output
    """
```

---

## ✅ CHECKLIST FOR MAINTAINABILITY

- [ ] **No Spaghetti Code**

  - [x] Clear pipeline stages
  - [x] No circular dependencies
  - [x] Single responsibility per service

- [ ] **Centralized Management**

  - [x] All constants in `adaptive_constants.py`
  - [x] Phase rules in configuration
  - [x] Single source of truth

- [ ] **Clear Stages**

  - [x] Stage 1: Data Collection (enhanced)
  - [x] Stage 2: Multi-Dimensional Analysis
  - [x] Stage 3: Trend Analysis
  - [x] Stage 4: Adaptive Adjustment
  - [x] Stage 5: Storage & Logging

- [ ] **Easy to Maintain**

  - [x] Inline documentation
  - [x] Type hints everywhere
  - [x] Clear naming conventions
  - [x] Unit tests for each service

- [ ] **Pattern Consistency**
  - [x] Follows existing service patterns (`@staticmethod`)
  - [x] Follows existing DAO patterns (simple functions)
  - [x] Follows existing model patterns (SQLAlchemy ORM)
  - [x] Uses dataclasses for data transfer

---

_Document created: January 2026_
_Author: SmartCoach Development Team_
_Status: Ready for Implementation_

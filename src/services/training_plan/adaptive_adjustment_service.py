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
    - Pace module (for pace adjustments)

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from dataclasses import dataclass
from typing import List, Optional, Literal, Dict, Any
from sqlalchemy.orm import Session
import logging

from .week_analysis_service import WeekAnalysisResult
from .trend_analysis_service import TrendAnalysisResult
from src.smartcoach_mobile_coach.runner_profile.models import PaceZoneComputation
from src.utils.adaptive_constants import (
    AdaptiveConfig,
    PhaseRules,
    MAX_VOLUME_CHANGE_PCT,
    MAX_PACE_CHANGE_SEC,
)
from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
    RUN_TYPE_DEFINITIONS,
    RUN_TYPE_EASY,
)

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
        current_pace_zones: PaceZoneComputation,
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
            current_pace_zones: Current runner-profile pace zones
            phase: Training phase ("Base", "Build", "Peak", "Taper")
            weeks_remaining: Weeks until race

        Returns:
            AdjustmentDecision with all adjustments and explanations
        """
        # Get phase-specific rules
        phase_rules = AdaptiveConfig.get_phase_rules(phase)

        # Calculate weighted match_score
        match_score = AdaptiveAdjustmentService._calculate_match_score(
            analysis, phase_rules
        )

        # Detect fatigue patterns (including low zone-compliance guardrail)
        zone_compliance_guardrail = (
            AdaptiveAdjustmentService._get_zone_compliance_guardrail(analysis)
        )
        fatigue_detected = AdaptiveAdjustmentService._detect_fatigue(
            analysis, trends
        ) or bool(zone_compliance_guardrail)

        # Apply phase-specific rules
        if phase == "Base":
            decision = AdaptiveAdjustmentService._apply_base_phase_rules(
                analysis, trends, phase_rules, fatigue_detected
            )
        elif phase == "Build":
            decision = AdaptiveAdjustmentService._apply_build_phase_rules(
                analysis, trends, phase_rules, fatigue_detected
            )
        elif phase == "Peak":
            decision = AdaptiveAdjustmentService._apply_peak_phase_rules(
                analysis, trends, phase_rules, fatigue_detected
            )
        elif phase == "Taper":
            decision = AdaptiveAdjustmentService._apply_taper_phase_rules(
                analysis, trends, phase_rules, fatigue_detected
            )
        else:
            # Default to Build phase rules
            decision = AdaptiveAdjustmentService._apply_build_phase_rules(
                analysis, trends, phase_rules, fatigue_detected
            )

        decision = AdaptiveAdjustmentService._apply_zone_compliance_guardrail(
            decision, zone_compliance_guardrail
        )

        # Set common fields
        decision.match_score = match_score
        decision.phase = phase
        decision.weeks_remaining = weeks_remaining

        # Apply safety constraints
        decision = AdaptiveAdjustmentService._apply_safety_constraints(
            decision, analysis.total_planned_miles, weeks_remaining
        )

        return decision

    @staticmethod
    def _calculate_match_score(
        analysis: WeekAnalysisResult,
        phase_rules: "PhaseRules",
    ) -> float:
        """
        Calculate weighted composite match_score.

        Uses phase-specific weights from phase_rules.

        Returns:
            Composite score (0.0-1.0)
        """
        weights = phase_rules.match_score_weights

        # Normalize scores to 0-1 range (they're already 0-100)
        volume_norm = analysis.volume_score / 100.0
        intensity_norm = analysis.intensity_score / 100.0
        consistency_norm = analysis.consistency_score / 100.0

        # Recovery score (inverse of fatigue markers)
        recovery_norm = 1.0 - (len(analysis.fatigue_markers) * 0.2)
        recovery_norm = max(0.0, min(1.0, recovery_norm))

        # Calculate weighted score
        match_score = (
            weights.get("volume", 0.3) * volume_norm
            + weights.get("intensity", 0.3) * intensity_norm
            + weights.get("consistency", 0.2) * consistency_norm
            + weights.get("recovery", 0.1) * recovery_norm
        )

        return max(0.0, min(1.0, match_score))

    @staticmethod
    def _apply_base_phase_rules(
        analysis: WeekAnalysisResult,
        trends: TrendAnalysisResult,
        phase_rules: "PhaseRules",
        fatigue_detected: bool,
    ) -> AdjustmentDecision:
        """Apply Base phase adjustment rules."""
        volume_change = 0.0
        pace_adjustment = 0.0
        disable_quality = False
        decision_type = "no_change"
        trigger_reason = "No adjustments needed"
        metrics_used = {}

        # Base phase: Focus on volume, lenient on pace
        if fatigue_detected:
            # Fatigue detected → reduce volume and slow pace
            volume_change = -10.0  # Reduce 10%
            pace_adjustment = +5.0  # Slow by 5s/mile
            disable_quality = True
            decision_type = "fatigue_reduction"
            trigger_reason = (
                "Fatigue pattern detected: high load, pace slowing, HR rising"
            )
            metrics_used = {
                "load_delta_pct": analysis.load_delta_pct or 0.0,
                "pace_deviation": analysis.pace_deviation,
            }
        elif analysis.volume_score < phase_rules.volume_low_threshold * 100:
            # Low volume completion → slow pace, reduce volume
            volume_change = -10.0
            pace_adjustment = +10.0
            disable_quality = True
            decision_type = "volume_decrease"
            trigger_reason = f"Low volume completion ({analysis.volume_score:.1f}%)"
            metrics_used = {"volume_score": analysis.volume_score}
        elif (
            analysis.volume_score >= phase_rules.volume_good_threshold * 100
            and trends.volume_trend == "improving"
        ):
            # Good volume + improving trend → can increase slightly
            if phase_rules.allow_volume_increase:
                volume_change = +5.0
                decision_type = "volume_increase"
                trigger_reason = f"Good volume completion ({analysis.volume_score:.1f}%) with improving trend"
                metrics_used = {"volume_score": analysis.volume_score}

        return AdjustmentDecision(
            decision_type=decision_type,
            volume_change_pct=volume_change,
            pace_adjustment_sec=pace_adjustment,
            disable_quality_workouts=disable_quality,
            trigger_reason=trigger_reason,
            metrics_used=metrics_used,
            match_score=0.0,  # Will be set later
            phase="Base",
            weeks_remaining=0,
            safety_constraints_applied=[],
        )

    @staticmethod
    def _apply_build_phase_rules(
        analysis: WeekAnalysisResult,
        trends: TrendAnalysisResult,
        phase_rules: "PhaseRules",
        fatigue_detected: bool,
    ) -> AdjustmentDecision:
        """Apply Build phase adjustment rules."""
        volume_change = 0.0
        pace_adjustment = 0.0
        disable_quality = False
        decision_type = "no_change"
        trigger_reason = "No adjustments needed"
        metrics_used = {}

        # Build phase: Balance volume + intensity
        if fatigue_detected:
            volume_change = -10.0
            pace_adjustment = +5.0
            disable_quality = True
            decision_type = "fatigue_reduction"
            trigger_reason = "Fatigue pattern detected"
            metrics_used = {
                "load_delta_pct": analysis.load_delta_pct or 0.0,
                "pace_deviation": analysis.pace_deviation,
            }
        elif analysis.intensity_score < phase_rules.intensity_low_threshold * 100:
            # Low intensity completion → reduce volume to focus on quality
            volume_change = -5.0
            decision_type = "volume_decrease"
            trigger_reason = (
                f"Low intensity completion ({analysis.intensity_score:.1f}%)"
            )
            metrics_used = {"intensity_score": analysis.intensity_score}
        elif analysis.volume_score < phase_rules.volume_low_threshold * 100:
            volume_change = -10.0
            pace_adjustment = +10.0
            disable_quality = True
            decision_type = "volume_decrease"
            trigger_reason = f"Low volume completion ({analysis.volume_score:.1f}%)"
            metrics_used = {"volume_score": analysis.volume_score}

        return AdjustmentDecision(
            decision_type=decision_type,
            volume_change_pct=volume_change,
            pace_adjustment_sec=pace_adjustment,
            disable_quality_workouts=disable_quality,
            trigger_reason=trigger_reason,
            metrics_used=metrics_used,
            match_score=0.0,
            phase="Build",
            weeks_remaining=0,
            safety_constraints_applied=[],
        )

    @staticmethod
    def _apply_peak_phase_rules(
        analysis: WeekAnalysisResult,
        trends: TrendAnalysisResult,
        phase_rules: "PhaseRules",
        fatigue_detected: bool,
    ) -> AdjustmentDecision:
        """Apply Peak phase adjustment rules."""
        volume_change = 0.0
        pace_adjustment = 0.0
        disable_quality = False
        decision_type = "no_change"
        trigger_reason = "No adjustments needed"
        metrics_used = {}

        # Peak phase: Quality critical, strict on paces, no increases
        if fatigue_detected:
            volume_change = -15.0  # More aggressive reduction
            pace_adjustment = +10.0
            disable_quality = True
            decision_type = "fatigue_reduction"
            trigger_reason = (
                "Fatigue pattern detected in Peak phase - aggressive reduction"
            )
            metrics_used = {
                "load_delta_pct": analysis.load_delta_pct or 0.0,
                "pace_deviation": analysis.pace_deviation,
            }
        elif analysis.intensity_score < phase_rules.intensity_low_threshold * 100:
            # Low intensity → reduce volume, keep quality but easier
            volume_change = -10.0
            pace_adjustment = +5.0
            decision_type = "volume_decrease"
            trigger_reason = f"Low intensity completion ({analysis.intensity_score:.1f}%) in Peak phase"
            metrics_used = {"intensity_score": analysis.intensity_score}
        elif analysis.volume_score < phase_rules.volume_low_threshold * 100:
            volume_change = -10.0
            pace_adjustment = +10.0
            disable_quality = True
            decision_type = "volume_decrease"
            trigger_reason = (
                f"Low volume completion ({analysis.volume_score:.1f}%) in Peak phase"
            )
            metrics_used = {"volume_score": analysis.volume_score}

        return AdjustmentDecision(
            decision_type=decision_type,
            volume_change_pct=volume_change,
            pace_adjustment_sec=pace_adjustment,
            disable_quality_workouts=disable_quality,
            trigger_reason=trigger_reason,
            metrics_used=metrics_used,
            match_score=0.0,
            phase="Peak",
            weeks_remaining=0,
            safety_constraints_applied=[],
        )

    @staticmethod
    def _apply_taper_phase_rules(
        analysis: WeekAnalysisResult,
        trends: TrendAnalysisResult,
        phase_rules: "PhaseRules",
        fatigue_detected: bool,
    ) -> AdjustmentDecision:
        """Apply Taper phase adjustment rules."""
        volume_change = 0.0
        pace_adjustment = 0.0
        disable_quality = False
        decision_type = "no_change"
        trigger_reason = "No adjustments needed in Taper"
        metrics_used = {}

        # Taper phase: Very lenient on volume, strict on pace, never increase
        if fatigue_detected:
            volume_change = -10.0
            pace_adjustment = +5.0
            disable_quality = True
            decision_type = "fatigue_reduction"
            trigger_reason = "Fatigue detected in Taper - reduce volume and slow pace"
            metrics_used = {
                "load_delta_pct": analysis.load_delta_pct or 0.0,
                "pace_deviation": analysis.pace_deviation,
            }
        # Very lenient on volume in taper (50% threshold)
        # Only adjust if extremely low (<50%)
        elif analysis.volume_score < phase_rules.volume_low_threshold * 100:
            volume_change = -5.0
            decision_type = "volume_decrease"
            trigger_reason = (
                f"Very low volume completion ({analysis.volume_score:.1f}%) in Taper"
            )
            metrics_used = {"volume_score": analysis.volume_score}

        return AdjustmentDecision(
            decision_type=decision_type,
            volume_change_pct=volume_change,
            pace_adjustment_sec=pace_adjustment,
            disable_quality_workouts=disable_quality,
            trigger_reason=trigger_reason,
            metrics_used=metrics_used,
            match_score=0.0,
            phase="Taper",
            weeks_remaining=0,
            safety_constraints_applied=[],
        )

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
        - HR higher than dynamic threshold (if available)

        Returns:
            True if fatigue pattern detected
        """
        # Check load delta
        load_delta_high = (
            analysis.load_delta_pct is not None and analysis.load_delta_pct > 15.0
        )

        # Check pace (positive deviation = slower)
        pace_slow = analysis.pace_deviation > analysis.pace_threshold

        # Check trends
        pace_declining = trends.pace_trend == "declining"

        # Fatigue if multiple indicators present
        fatigue_indicators = sum(
            [
                load_delta_high,
                pace_slow,
                pace_declining,
                len(analysis.fatigue_markers) > 0,
            ]
        )

        # Require at least 2 indicators
        return fatigue_indicators >= 2

    @staticmethod
    def _get_zone_compliance_guardrail(
        analysis: WeekAnalysisResult,
    ) -> Optional[Dict[str, float]]:
        """
        Detect low easy-run zone compliance using canonical tolerance thresholds.

        Returns:
            Dict with compliance details when below threshold, else None.
        """
        easy_compliance = analysis.avg_zone_compliance_by_type.get(RUN_TYPE_EASY)
        easy_definition = RUN_TYPE_DEFINITIONS.get(RUN_TYPE_EASY)
        tolerance = easy_definition.tolerance if easy_definition else None
        if easy_compliance is None or tolerance is None:
            return None

        min_compliance = tolerance.yellow_min_compliance
        if easy_compliance >= min_compliance:
            return None

        return {
            "easy_zone_compliance_pct": float(easy_compliance),
            "easy_min_compliance_pct": float(min_compliance),
        }

    @staticmethod
    def _apply_zone_compliance_guardrail(
        decision: AdjustmentDecision,
        zone_guardrail: Optional[Dict[str, float]],
    ) -> AdjustmentDecision:
        """
        Apply a protective slowdown when easy-run zone compliance is too low.

        This aligns with the existing high-RPE safety behavior by slowing paces and
        disabling quality work until execution returns to target intensity.
        """
        if not zone_guardrail:
            return decision

        decision.pace_adjustment_sec = max(decision.pace_adjustment_sec, 5.0)
        decision.disable_quality_workouts = True

        if decision.decision_type == "no_change":
            decision.decision_type = "pace_decrease"

        low = zone_guardrail["easy_zone_compliance_pct"]
        threshold = zone_guardrail["easy_min_compliance_pct"]
        zone_reason = f"Low easy-zone compliance ({low:.1f}% < {threshold:.1f}%)"
        if decision.trigger_reason.startswith("No adjustments needed"):
            decision.trigger_reason = zone_reason
        elif zone_reason not in decision.trigger_reason:
            decision.trigger_reason = f"{decision.trigger_reason}; {zone_reason}"

        decision.metrics_used.update(zone_guardrail)
        return decision

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
        safety_limits = AdaptiveConfig.get_safety_limits(weeks_remaining)
        constraints_applied = []

        # Hard limits (absolute maximums)
        if abs(decision.volume_change_pct) > MAX_VOLUME_CHANGE_PCT:
            old_value = decision.volume_change_pct
            decision.volume_change_pct = (
                MAX_VOLUME_CHANGE_PCT
                if decision.volume_change_pct > 0
                else -MAX_VOLUME_CHANGE_PCT
            )
            constraints_applied.append(f"volume_capped_{MAX_VOLUME_CHANGE_PCT}pct")
            logger.info(
                f"Capped volume change: {old_value}% → {decision.volume_change_pct}%"
            )

        if abs(decision.pace_adjustment_sec) > MAX_PACE_CHANGE_SEC:
            old_value = decision.pace_adjustment_sec
            decision.pace_adjustment_sec = (
                MAX_PACE_CHANGE_SEC
                if decision.pace_adjustment_sec > 0
                else -MAX_PACE_CHANGE_SEC
            )
            constraints_applied.append(f"pace_capped_{MAX_PACE_CHANGE_SEC}sec")
            logger.info(
                f"Capped pace adjustment: {old_value}s → {decision.pace_adjustment_sec}s"
            )

        # Progressive limits based on weeks remaining
        max_volume_pct = safety_limits.get("max_volume_pct", MAX_VOLUME_CHANGE_PCT)
        max_pace_sec = safety_limits.get("max_pace_sec", MAX_PACE_CHANGE_SEC)

        if abs(decision.volume_change_pct) > max_volume_pct:
            old_value = decision.volume_change_pct
            decision.volume_change_pct = (
                max_volume_pct if decision.volume_change_pct > 0 else -max_volume_pct
            )
            constraints_applied.append(f"volume_capped_{max_volume_pct}pct_progressive")
            logger.info(
                f"Progressive cap: volume {old_value}% → {decision.volume_change_pct}%"
            )

        if abs(decision.pace_adjustment_sec) > max_pace_sec:
            old_value = decision.pace_adjustment_sec
            decision.pace_adjustment_sec = (
                max_pace_sec if decision.pace_adjustment_sec > 0 else -max_pace_sec
            )
            constraints_applied.append(f"pace_capped_{max_pace_sec}sec_progressive")
            logger.info(
                f"Progressive cap: pace {old_value}s → {decision.pace_adjustment_sec}s"
            )

        decision.safety_constraints_applied = constraints_applied
        return decision

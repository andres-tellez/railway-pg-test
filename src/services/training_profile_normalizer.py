"""
Training Profile Normalizer Module
----------------------------------

Purpose:
Bridges Stage 1 (Athlete Readiness Assessment) with the Jack Daniels training-plan generator.

It converts readiness metrics into quantitative limits and scaling factors:
    - weekly ramp percentage
    - target weekly mileage band
    - long-run cap
    - number of quality sessions
    - intensity ratio targets
    - phase assignment

This ensures the plan generator stays physiologically safe and aligned
with Jack Daniels principles while adapting to each athlete's readiness level.
"""

from datetime import datetime
from typing import Dict, Any


def normalize_training_profile(readiness: Dict[str, Any], 
                               user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translate a readiness profile into normalized plan parameters.
    
    Args:
        readiness: Output from Stage 1 (assess_runner_readiness)
        user_profile: Runner metadata (age, level, etc.)
        
    Returns:
        Dict containing training parameters for the plan generator.
    """
    
    print("\n" + "=" * 60)
    print("TRAINING PROFILE NORMALIZATION (Stage 2)")
    print("=" * 60)
    
    # --- 1. Extract readiness inputs ---
    category        = readiness.get("category", "Low-Base")
    base_mileage    = readiness.get("base_mileage", 0)
    longest_run     = readiness.get("longest_run", 0)
    age_factor      = readiness.get("age_factor", 1.0)
    weeks_to_race   = readiness.get("weeks_to_race", 0)
    readiness_index = readiness.get("readiness_index", 0)
    
    print(f"\nInput Summary:")
    print(f"  • Category: {category}")
    print(f"  • Base mileage: {base_mileage} mi/week")
    print(f"  • Longest recent run: {longest_run} mi")
    print(f"  • Weeks to race: {weeks_to_race}")
    print(f"  • Readiness Index: {readiness_index}")
    print(f"  • Age factor: {age_factor}")
    
    # --- 2️⃣ Define parameter templates by readiness category ---
    # Each entry controls plan aggressiveness & volume scaling.
    CATEGORY_MAP = {
        "Low-Base": {
            "ramp_limit_pct": 0.05,          # ≤ 5 % per week
            "mileage_multiplier": 1.8,       # final target = 1.8 × base mileage (no additional ramp)
            "long_run_cap": 18,
            "threshold_sessions": 1,
            "easy_ratio": 0.75,
            "phase": "Base-Build",
            "vdot_adjust": -1.0              # slower paces / conservative VDOT
        },
        "Stable-Base": {
            "ramp_limit_pct": 0.08,
            "mileage_multiplier": 2.2,
            "long_run_cap": 22,
            "threshold_sessions": 2,
            "easy_ratio": 0.70,
            "phase": "Quality-Phase",
            "vdot_adjust": 0.0
        },
        "High-Base": {
            "ramp_limit_pct": 0.10,
            "mileage_multiplier": 2.6,
            "long_run_cap": 24,
            "threshold_sessions": 3,
            "easy_ratio": 0.65,
            "phase": "Race-Specific",
            "vdot_adjust": 0.0
        }
    }
    
    cfg = CATEGORY_MAP.get(category, CATEGORY_MAP["Low-Base"])
    
    # --- 3️⃣ Compute derived numeric targets ---
    target_weekly_mileage = base_mileage * cfg["mileage_multiplier"]
    # never drop below current base mileage
    target_weekly_mileage = max(target_weekly_mileage, base_mileage)
    
    # --- Long-run cap calculation (CRITICAL FIX) ---
    # JD principle: Never reduce long-run distance by more than 20-25%
    expected_long = target_weekly_mileage * 0.33  # ~33% of weekly mileage
    min_safe_long = longest_run * 0.8             # Never drop below 80% of current longest
    long_run_cap = max(min_safe_long, expected_long)
    
    print(f"\nLong-Run Cap Calculation:")
    print(f"  • Expected (33% of target): {expected_long:.1f} mi")
    print(f"  • Minimum safe (80% of current): {min_safe_long:.1f} mi")
    print(f"  • Final cap: {long_run_cap:.1f} mi")
    
    print(f"\nDerived Training Targets:")
    print(f"  • Target weekly mileage: {target_weekly_mileage:.1f} mi")
    print(f"  • Ramp limit per week: {cfg['ramp_limit_pct']*100:.0f}%")
    print(f"  • Long-run cap: {long_run_cap:.1f} mi")
    print(f"  • Threshold sessions / week: {cfg['threshold_sessions']}")
    print(f"  • Easy run ratio: {cfg['easy_ratio']*100:.0f}%")
    print(f"  • Training phase: {cfg['phase']}")
    
    # --- 4️⃣ Apply age-based adjustments ---
    if age_factor < 1.0:
        # Reduce ramp rate for older athletes
        adjusted_ramp = cfg["ramp_limit_pct"] * age_factor
        adjusted_threshold = max(1, cfg["threshold_sessions"] - 1)
        print(f"\nAge Adjustments:")
        print(f"  • Ramp limit: {cfg['ramp_limit_pct']*100:.0f}% → {adjusted_ramp*100:.0f}%")
        print(f"  • Threshold sessions: {cfg['threshold_sessions']} → {adjusted_threshold}")
        
        cfg["ramp_limit_pct"] = adjusted_ramp
        cfg["threshold_sessions"] = adjusted_threshold
    
    # --- 5️⃣ Time-to-race adjustments ---
    if weeks_to_race < 8:
        # Aggressive timeline - reduce target mileage
        time_pressure_factor = max(0.7, weeks_to_race / 12)
        target_weekly_mileage *= time_pressure_factor
        print(f"\nTimeline Adjustments:")
        print(f"  • {weeks_to_race} weeks to race - reducing target mileage by {(1-time_pressure_factor)*100:.0f}%")
        print(f"  • Adjusted target: {target_weekly_mileage:.1f} mi/week")
    elif weeks_to_race > 20:
        # Plenty of time - can be more conservative
        target_weekly_mileage *= 1.1  # 10% increase
        print(f"\nTimeline Adjustments:")
        print(f"  • {weeks_to_race} weeks to race - conservative ramp possible")
        print(f"  • Adjusted target: {target_weekly_mileage:.1f} mi/week")
    
    # --- 6️⃣ Build final normalized profile ---
    normalized_profile = {
        # Core training parameters
        "category": category,
        "phase": cfg["phase"],
        "ramp_limit_pct": round(cfg["ramp_limit_pct"], 3),
        "target_weekly_mileage": round(target_weekly_mileage, 1),
        "long_run_cap": round(long_run_cap, 1),
        "threshold_sessions_per_week": cfg["threshold_sessions"],
        "easy_run_ratio": cfg["easy_ratio"],
        "vdot_adjustment": cfg["vdot_adjust"],
        
        # Context for plan generator
        "weeks_to_race": weeks_to_race,
        "age_factor": age_factor,
        "readiness_index": readiness_index,
        "longest_run": longest_run,
        
        # Derived constraints for Jack Daniels rules
        "max_weekly_increase": round(target_weekly_mileage * cfg["ramp_limit_pct"], 1),
        "quality_work_ratio": round(1 - cfg["easy_ratio"], 2),
        "base_mileage": base_mileage,
        "mileage_multiplier": cfg["mileage_multiplier"],
        
        # Safety bounds
        "min_weekly_mileage": max(10, base_mileage * 0.8),
        "max_weekly_mileage": target_weekly_mileage * 1.2,
        
        # Plan structure guidance
        "recommended_training_days": 4 if category == "Low-Base" else 5 if category == "Stable-Base" else 6,
        "recovery_week_frequency": 3 if category == "Low-Base" else 4,
    }
    
    print(f"\nNORMALIZED TRAINING PROFILE:")
    print(f"  • Phase: {normalized_profile['phase']}")
    print(f"  • Ramp limit: {normalized_profile['ramp_limit_pct']*100:.1f}% per week")
    print(f"  • Target mileage: {normalized_profile['target_weekly_mileage']} mi/week")
    print(f"  • Long-run cap: {normalized_profile['long_run_cap']} mi")
    print(f"  • Quality sessions: {normalized_profile['threshold_sessions_per_week']}/week")
    print(f"  • Easy ratio: {normalized_profile['easy_run_ratio']*100:.0f}%")
    print(f"  • VDOT adjustment: {normalized_profile['vdot_adjustment']}")
    print(f"  • Training days: {normalized_profile['recommended_training_days']}")
    print("=" * 60 + "\n")
    
    return normalized_profile


def get_jack_daniels_phase_parameters(phase: str, normalized_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert normalized profile into Jack Daniels phase-specific parameters.
    
    Args:
        phase: Training phase (Base-Build, Quality-Phase, Race-Specific)
        normalized_profile: Output from normalize_training_profile
        
    Returns:
        Dict with JD phase parameters for prompt generation
    """
    
    base_params = {
        "target_mileage": normalized_profile["target_weekly_mileage"],
        "ramp_limit": normalized_profile["ramp_limit_pct"],
        "long_run_cap": normalized_profile["long_run_cap"],
        "easy_ratio": normalized_profile["easy_run_ratio"],
    }
    
    if phase == "Base-Build":
        return {
            **base_params,
            "primary_focus": "aerobic base development",
            "intensity_distribution": {
                "easy": 0.75,
                "moderate": 0.15,
                "threshold": 0.05,
                "vo2_max": 0.05
            },
            "workout_types": ["Easy Run", "Long Run", "Easy Threshold"],
            "weekly_structure": "3-4 easy runs + 1 long run + 1 light threshold"
        }
    
    elif phase == "Quality-Phase":
        return {
            **base_params,
            "primary_focus": "lactate threshold and aerobic power",
            "intensity_distribution": {
                "easy": 0.70,
                "moderate": 0.10,
                "threshold": 0.15,
                "vo2_max": 0.05
            },
            "workout_types": ["Easy Run", "Long Run", "Threshold", "Tempo"],
            "weekly_structure": "3 easy runs + 1 long run + 1-2 threshold/tempo"
        }
    
    elif phase == "Race-Specific":
        return {
            **base_params,
            "primary_focus": "race-specific fitness and pace practice",
            "intensity_distribution": {
                "easy": 0.65,
                "moderate": 0.10,
                "threshold": 0.15,
                "vo2_max": 0.10
            },
            "workout_types": ["Easy Run", "Long Run", "Threshold", "VO2 Max", "Race Pace"],
            "weekly_structure": "3 easy runs + 1 long run + 2-3 quality sessions"
        }
    
    else:
        # Default to Base-Build
        return get_jack_daniels_phase_parameters("Base-Build", normalized_profile)

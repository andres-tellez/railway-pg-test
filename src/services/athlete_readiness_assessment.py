"""
Athlete Readiness Assessment Module

Purpose:
Quantifies a runner's current fitness baseline and training readiness before generating
a marathon training plan. This prevents overtraining, burnout, or injury by analyzing:
- Recent mileage trends (last 4-6 weeks)
- Training consistency
- Heart rate zone distribution
- Long run ratio
- Age-adjusted capacity

Output:
A structured readiness profile with a composite score (0-100) and category classification
(Low-Base, Stable-Base, High-Base) that informs training plan intensity and progression.
"""

from datetime import datetime, timedelta, date
from typing import Dict, List, Any


def assess_runner_readiness(
    activities: List[Dict[str, Any]], 
    user_profile: Dict[str, Any],
    race_date: date
) -> Dict[str, Any]:
    """
    Calculates base metrics and classifies runner readiness.
    
    Args:
        activities: List of activity dictionaries with fields:
            - activity_date (str or date): Activity date
            - distance (float): Distance in miles
            - hr_zone1-5 (float): Percentage of time in each HR zone
        user_profile: Dict with:
            - age or age_group: Runner's age information
            - runner_level: Experience level
        race_date: Target race date
    
    Returns:
        Dict with readiness metrics and classification:
            - weeks_to_race
            - base_mileage (4-6 week average)
            - longest_run
            - consistency_score
            - pct_easy (% in Z1-Z2)
            - pct_threshold (% in Z3)
            - pct_hard (% in Z4-Z5)
            - readiness_index (0-100 composite score)
            - category (Low-Base, Stable-Base, High-Base)
            - age_factor
    """
    
    print("\n" + "=" * 60)
    print("🏃 ATHLETE READINESS ASSESSMENT")
    print("=" * 60)
    
    # ---- 1️⃣ Basic setup ----
    today = datetime.today().date()
    weeks_to_race = (race_date - today).days / 7
    print(f"\n📅 Timeline:")
    print(f"  • Today: {today}")
    print(f"  • Race date: {race_date}")
    print(f"  • Weeks to race: {weeks_to_race:.1f}")
    
    # ---- 2️⃣ Filter last 6 weeks of activities ----
    cutoff = today - timedelta(weeks=6)
    recent_activities = []
    
    for act in activities:
        # Parse activity date
        act_date_str = act.get('activity_date', '')
        if isinstance(act_date_str, str):
            try:
                act_date = datetime.strptime(act_date_str, '%Y-%m-%d').date()
            except ValueError:
                continue
        elif isinstance(act_date_str, date):
            act_date = act_date_str
        else:
            continue
        
        if act_date >= cutoff:
            recent_activities.append({
                'date': act_date,
                'distance': act.get('distance', 0),
                'hr_zone1': act.get('hr_zone1', 0),
                'hr_zone2': act.get('hr_zone2', 0),
                'hr_zone3': act.get('hr_zone3', 0),
                'hr_zone4': act.get('hr_zone4', 0),
                'hr_zone5': act.get('hr_zone5', 0),
            })
    
    print(f"\n📊 Recent Activity Window:")
    print(f"  • Cutoff date: {cutoff}")
    print(f"  • Activities in last 6 weeks: {len(recent_activities)}")
    
    if not recent_activities:
        print("  ⚠️  No recent activities found - using fallback assessment")
        return _fallback_readiness_assessment(weeks_to_race, user_profile)
    
    # ---- 3️⃣ Compute weekly mileage ----
    # Group activities by week
    weekly_mileage = {}
    for act in recent_activities:
        # Get the Monday of the week for this activity
        week_start = act['date'] - timedelta(days=act['date'].weekday())
        if week_start not in weekly_mileage:
            weekly_mileage[week_start] = {
                'total_miles': 0,
                'run_count': 0
            }
        weekly_mileage[week_start]['total_miles'] += act['distance']
        weekly_mileage[week_start]['run_count'] += 1
    
    # Calculate base mileage (average of last 4-6 weeks)
    weekly_totals = [week['total_miles'] for week in weekly_mileage.values()]
    base_mileage = sum(weekly_totals) / len(weekly_totals) if weekly_totals else 0
    
    print(f"\n📈 Weekly Mileage Analysis:")
    print(f"  • Number of weeks with data: {len(weekly_mileage)}")
    print(f"  • Weekly totals: {[round(m, 1) for m in sorted(weekly_totals, reverse=True)]}")
    print(f"  • Base mileage (avg): {base_mileage:.1f} mi/week")
    
    # ---- 4️⃣ Longest recent run ----
    longest_run = max([act['distance'] for act in recent_activities]) if recent_activities else 0
    print(f"  • Longest run: {longest_run:.1f} miles")
    
    # ---- 5️⃣ Consistency score ----
    # Combine frequency AND mileage stability
    weeks_with_3_runs = sum(1 for week in weekly_mileage.values() if week['run_count'] >= 3)
    total_weeks = len(weekly_mileage)
    frequency_score = (weeks_with_3_runs / max(total_weeks, 1)) * 100
    
    # Calculate mileage stability (lower deviation = higher score)
    mean_miles = base_mileage
    if weekly_totals and mean_miles > 0:
        week_deviation = sum(abs(w - mean_miles) for w in weekly_totals) / len(weekly_totals)
        stability_factor = max(0, 1 - (week_deviation / (mean_miles + 1e-5)))
    else:
        stability_factor = 0
    
    # Combined consistency score (60% frequency, 40% stability)
    consistency_score = (frequency_score * 0.6 + stability_factor * 100 * 0.4)
    
    print(f"\n🔄 Consistency Analysis:")
    print(f"  • Weeks with 3+ runs: {weeks_with_3_runs} / {total_weeks} ({frequency_score:.1f}%)")
    print(f"  • Mileage stability: {stability_factor:.2f} (lower deviation = better)")
    print(f"  • Combined consistency score: {consistency_score:.1f}%")
    
    # ---- 6️⃣ Zone distribution ----
    # Average HR zone percentages across all recent activities
    zone_totals = {f'hr_zone{i}': 0 for i in range(1, 6)}
    for act in recent_activities:
        for zone in zone_totals:
            zone_totals[zone] += act[zone]
    
    num_activities = len(recent_activities)
    zone_avgs = {zone: total / num_activities for zone, total in zone_totals.items()}
    
    pct_easy = zone_avgs['hr_zone1'] + zone_avgs['hr_zone2']
    pct_threshold = zone_avgs['hr_zone3']
    pct_hard = zone_avgs['hr_zone4'] + zone_avgs['hr_zone5']
    
    print(f"\n💓 Heart Rate Distribution:")
    print(f"  • Easy (Z1-Z2): {pct_easy:.1f}%")
    print(f"  • Threshold (Z3): {pct_threshold:.1f}%")
    print(f"  • Hard (Z4-Z5): {pct_hard:.1f}%")
    
    # ---- 7️⃣ Age factor ----
    age = user_profile.get('age', 35)
    age_group = str(user_profile.get('age_group', ''))
    
    if age >= 60 or '60' in age_group:
        age_factor = 0.85
    elif age >= 55 or '55' in age_group or '50' in age_group:
        age_factor = 0.9
    elif age >= 45 or '45' in age_group:
        age_factor = 0.95
    else:
        age_factor = 1.0
    
    print(f"\n👤 Age Adjustment:")
    print(f"  • Age: {age} (group: {age_group})")
    print(f"  • Age factor: {age_factor}")
    
    # ---- 8️⃣ Subscores ----
    # Base mileage score (adaptive scaling based on experience level)
    runner_level = str(user_profile.get('runner_level', 'Intermediate')).lower()
    target_mileage = 40  # Default for advanced
    if runner_level in ["beginner", "novice"]:
        target_mileage = 25
    elif runner_level == "intermediate":
        target_mileage = 35
    base_mileage_score = min(base_mileage / target_mileage * 100, 100)
    
    # Zone balance score (50-70% easy range is ideal)
    zone_balance_score = max(0, min((pct_easy - 50) / 20 * 100, 100))
    
    # Long run ratio score (more realistic scoring)
    long_run_ratio = (longest_run / base_mileage) if base_mileage > 0 else 0
    if long_run_ratio < 0.2:
        long_run_ratio_score = long_run_ratio / 0.2 * 60  # too short
    elif long_run_ratio <= 0.35:
        long_run_ratio_score = 80 + ((long_run_ratio - 0.25) / 0.1 * 20)  # sweet spot
    else:
        long_run_ratio_score = max(60, 100 - (long_run_ratio - 0.35) * 200)  # penalty if too long
    
    print(f"\n📊 Component Scores:")
    print(f"  • Base mileage score: {base_mileage_score:.1f} / 100 (target: {target_mileage} mi/week)")
    print(f"  • Consistency score: {consistency_score:.1f} / 100")
    print(f"  • Zone balance score: {zone_balance_score:.1f} / 100 (easy range: 50-70%)")
    print(f"  • Long run ratio: {long_run_ratio:.1%} (score: {long_run_ratio_score:.1f})")
    
    # ---- 9️⃣ Composite Readiness Index ----
    # Adjusted weights: better balance between mileage and HR patterns
    readiness_index = (
        (base_mileage_score * 0.35) +
        (consistency_score * 0.25) +
        (zone_balance_score * 0.25) +
        (long_run_ratio_score * 0.15)
    ) * age_factor
    
    # ---- 🔟 Category classification ----
    if readiness_index < 50:
        category = 'Low-Base'
        recommendation = "Conservative progression recommended"
    elif readiness_index < 75:
        category = 'Stable-Base'
        recommendation = "Moderate progression appropriate"
    else:
        category = 'High-Base'
        recommendation = "Aggressive progression possible"
    
    print(f"\n🎯 READINESS ASSESSMENT:")
    print(f"  • Readiness Index: {readiness_index:.1f} / 100")
    print(f"  • Category: {category}")
    print(f"  • Recommendation: {recommendation}")
    print("=" * 60 + "\n")
    
    # ---- ✅ Return summary with extended data structure ----
    return {
        "summary": {
            # Core metrics for frontend display
            "weeks_to_race": round(weeks_to_race, 1),
            "base_mileage": round(base_mileage, 1),
            "longest_run": round(longest_run, 1),
            "consistency_score": round(consistency_score, 1),
            "pct_easy": round(pct_easy, 1),
            "pct_threshold": round(pct_threshold, 1),
            "pct_hard": round(pct_hard, 1),
            "readiness_index": round(readiness_index, 1),
            "category": category,
            "recommendation": recommendation,
            "age_factor": age_factor,
            "long_run_ratio": round(long_run_ratio, 2)
        },
        "debug": {
            # Extended metrics for backend analysis and GPT training
            "total_recent_activities": len(recent_activities),
            "weeks_analyzed": len(weekly_mileage),
            "weekly_totals": [round(m, 1) for m in weekly_totals],
            
            # Component scores breakdown
            "frequency_score": round(frequency_score, 1),
            "stability_factor": round(stability_factor, 2),
            "target_mileage": target_mileage,
            "base_mileage_score": round(base_mileage_score, 1),
            "zone_balance_score": round(zone_balance_score, 1),
            "long_run_ratio_score": round(long_run_ratio_score, 1),
            
            # Raw calculations for analysis
            "week_deviation": round(week_deviation, 1) if weekly_totals and base_mileage > 0 else 0,
            "weeks_with_3_runs": weeks_with_3_runs,
            "total_weeks": total_weeks,
            "runner_level": runner_level,
            
            # HR zone details
            "hr_zone_breakdown": {
                "zone1": round(zone_avgs['hr_zone1'], 1),
                "zone2": round(zone_avgs['hr_zone2'], 1),
                "zone3": round(zone_avgs['hr_zone3'], 1),
                "zone4": round(zone_avgs['hr_zone4'], 1),
                "zone5": round(zone_avgs['hr_zone5'], 1)
            },
            
            # Assessment metadata
            "assessment_date": today.isoformat(),
            "data_quality": "real_data" if recent_activities else "fallback"
        }
    }


def _fallback_readiness_assessment(weeks_to_race: float, user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback readiness assessment when no recent activity data is available.
    Uses runner level and age to estimate baseline readiness.
    """
    runner_level = str(user_profile.get('runner_level', 'Intermediate')).lower()
    age = user_profile.get('age', 35)
    
    # Estimate base mileage from runner level
    if 'beginner' in runner_level:
        base_mileage = 25
        readiness_index = 45
        category = 'Low-Base'
    elif 'advanced' in runner_level:
        base_mileage = 50
        readiness_index = 70
        category = 'Stable-Base'
    else:
        base_mileage = 35
        readiness_index = 60
        category = 'Stable-Base'
    
    # Age adjustment
    if age >= 60:
        age_factor = 0.85
    elif age >= 55:
        age_factor = 0.9
    elif age >= 45:
        age_factor = 0.95
    else:
        age_factor = 1.0
    
    readiness_index *= age_factor
    
    print(f"\n🎯 FALLBACK READINESS ASSESSMENT:")
    print(f"  • Readiness Index: {readiness_index:.1f} / 100 (estimated)")
    print(f"  • Category: {category} (based on runner level)")
    print(f"  • Base mileage: {base_mileage} mi/week (estimated)")
    print("=" * 60 + "\n")
    
    # Determine target mileage for fallback
    target_mileage = 40  # Default for advanced
    if runner_level in ["beginner", "novice"]:
        target_mileage = 25
    elif runner_level == "intermediate":
        target_mileage = 35
    
    return {
        "summary": {
            "weeks_to_race": round(weeks_to_race, 1),
            "base_mileage": base_mileage,
            "longest_run": round(base_mileage * 0.3, 1),  # Estimate 30% of weekly
            "consistency_score": 50.0,  # Unknown
            "pct_easy": 70.0,  # Target
            "pct_threshold": 20.0,  # Target
            "pct_hard": 10.0,  # Target
            "readiness_index": round(readiness_index, 1),
            "category": category,
            "recommendation": "Using estimated baseline - update with recent activity data",
            "age_factor": age_factor,
            "long_run_ratio": 0.3  # Estimated
        },
        "debug": {
            "total_recent_activities": 0,
            "weeks_analyzed": 0,
            "weekly_totals": [],
            "frequency_score": 50.0,
            "stability_factor": 0.5,
            "target_mileage": target_mileage,
            "base_mileage_score": min(base_mileage / target_mileage * 100, 100),
            "zone_balance_score": 100.0,  # Assume good distribution
            "long_run_ratio_score": 80.0,  # Assume good ratio
            "week_deviation": 0,
            "weeks_with_3_runs": 0,
            "total_weeks": 0,
            "runner_level": runner_level,
            "hr_zone_breakdown": {
                "zone1": 20.0,
                "zone2": 50.0,
                "zone3": 20.0,
                "zone4": 8.0,
                "zone5": 2.0
            },
            "assessment_date": datetime.today().date().isoformat(),
            "data_quality": "fallback"
        }
    }


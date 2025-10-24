# src/utils/data_quality_validator.py

from sqlalchemy import text
from typing import Dict, Any


class DataQualityValidator:
    """Validates data quality for GPT context"""

    def __init__(self, session):
        self.session = session

    def validate_training_plan_data(self, user_id: str) -> Dict[str, Any]:
        """Validate training plan data quality"""
        validation_results = {
            "plan_exists": False,
            "workouts_count": 0,
            "data_completeness": {},
            "issues": [],
            "plan_quality_score": 0,
        }

        try:
            # Check if plan exists
            plan = self.session.execute(
                text(
                    """
                    SELECT
                        p.id,
                        p.plan_name,
                        p.race_date,
                        p.race_distance,
                        COUNT(pw.id) as total_workouts
                    FROM plans p
                    LEFT JOIN plan_workouts pw ON p.id = pw.plan_id
                    WHERE p.user_id = :user_id
                    GROUP BY p.id, p.plan_name, p.race_date, p.race_distance
                    ORDER BY p.created_at DESC
                    LIMIT 1
                """
                ),
                {"user_id": user_id},
            ).fetchone()

            if plan:
                validation_results["plan_exists"] = True
                validation_results["plan_name"] = plan.plan_name
                validation_results["race_info"] = {
                    "race_date": str(plan.race_date) if plan.race_date else None,
                    "race_distance": plan.race_distance,
                }
                validation_results["workouts_count"] = plan.total_workouts

                # Check workout data completeness
                workouts = self.session.execute(
                    text(
                        """
                        SELECT
                            COUNT(*) as total,
                            COUNT(CASE WHEN description IS NOT NULL AND description != '' THEN 1 END) as has_description,
                            COUNT(CASE WHEN miles > 0 THEN 1 END) as has_distance,
                            COUNT(CASE WHEN intensity IS NOT NULL AND intensity != '' THEN 1 END) as has_intensity,
                            COUNT(CASE WHEN target_zone IS NOT NULL AND target_zone != '' THEN 1 END) as has_target_zone,
                            COUNT(CASE WHEN focus IS NOT NULL AND focus != '' THEN 1 END) as has_focus
                        FROM plan_workouts pw
                        JOIN plans p ON pw.plan_id = p.id
                        WHERE p.user_id = :user_id
                    """
                    ),
                    {"user_id": user_id},
                ).fetchone()

                if workouts.total > 0:
                    validation_results["data_completeness"] = {
                        "descriptions": f"{workouts.has_description}/{workouts.total} ({workouts.has_description/workouts.total*100:.1f}%)",
                        "distances": f"{workouts.has_distance}/{workouts.total} ({workouts.has_distance/workouts.total*100:.1f}%)",
                        "intensities": f"{workouts.has_intensity}/{workouts.total} ({workouts.has_intensity/workouts.total*100:.1f}%)",
                        "target_zones": f"{workouts.has_target_zone}/{workouts.total} ({workouts.has_target_zone/workouts.total*100:.1f}%)",
                        "focus": f"{workouts.has_focus}/{workouts.total} ({workouts.has_focus/workouts.total*100:.1f}%)",
                    }

                    # Calculate quality score
                    quality_factors = [
                        workouts.has_description / workouts.total,
                        workouts.has_distance / workouts.total,
                        workouts.has_intensity / workouts.total,
                        workouts.has_target_zone / workouts.total,
                        workouts.has_focus / workouts.total,
                    ]
                    validation_results["plan_quality_score"] = (
                        sum(quality_factors) / len(quality_factors) * 100
                    )

                    # Identify issues
                    if workouts.has_description < workouts.total * 0.8:
                        validation_results["issues"].append(
                            "Many workouts missing descriptions"
                        )
                    if workouts.has_distance < workouts.total * 0.9:
                        validation_results["issues"].append(
                            "Some workouts missing distance"
                        )
                    if workouts.has_intensity < workouts.total * 0.9:
                        validation_results["issues"].append(
                            "Some workouts missing intensity"
                        )
                    if workouts.has_target_zone < workouts.total * 0.7:
                        validation_results["issues"].append(
                            "Many workouts missing target zones"
                        )
                    if workouts.has_focus < workouts.total * 0.6:
                        validation_results["issues"].append(
                            "Most workouts missing focus information"
                        )
                else:
                    validation_results["issues"].append("No workouts found in plan")
            else:
                validation_results["issues"].append("No training plan found")

        except Exception as e:
            validation_results["issues"].append(f"Error validating plan data: {str(e)}")

        return validation_results

    def validate_activity_data(self, user_id: str) -> Dict[str, Any]:
        """Validate completed activity data quality"""
        validation_results = {
            "activities_count": 0,
            "data_completeness": {},
            "issues": [],
            "data_quality_score": 0,
        }

        try:
            # Check recent activities
            activities = self.session.execute(
                text(
                    """
                    SELECT
                        COUNT(*) as total,
                        COUNT(CASE WHEN avg_hr > 0 THEN 1 END) as has_hr,
                        COUNT(CASE WHEN avg_speed > 0 THEN 1 END) as has_speed,
                        COUNT(CASE WHEN distance > 0 THEN 1 END) as has_distance,
                        COUNT(CASE WHEN elevation IS NOT NULL THEN 1 END) as has_elevation
                    FROM v_completed_activities
                    WHERE user_id = :user_id
                    AND activity_date::date >= CURRENT_DATE - INTERVAL '30 days'
                """
                ),
                {"user_id": user_id},
            ).fetchone()

            validation_results["activities_count"] = activities.total

            if activities.total > 0:
                validation_results["data_completeness"] = {
                    "heart_rate": f"{activities.has_hr}/{activities.total} ({activities.has_hr/activities.total*100:.1f}%)",
                    "speed": f"{activities.has_speed}/{activities.total} ({activities.has_speed/activities.total*100:.1f}%)",
                    "distance": f"{activities.has_distance}/{activities.total} ({activities.has_distance/activities.total*100:.1f}%)",
                    "elevation": f"{activities.has_elevation}/{activities.total} ({activities.has_elevation/activities.total*100:.1f}%)",
                }

                # Calculate quality score
                quality_factors = [
                    activities.has_hr / activities.total,
                    activities.has_speed / activities.total,
                    activities.has_distance / activities.total,
                    activities.has_elevation / activities.total,
                ]
                validation_results["data_quality_score"] = (
                    sum(quality_factors) / len(quality_factors) * 100
                )

                # Identify issues
                if activities.has_hr < activities.total * 0.7:
                    validation_results["issues"].append(
                        "Many activities missing heart rate data"
                    )
                if activities.has_speed < activities.total * 0.9:
                    validation_results["issues"].append(
                        "Some activities missing speed data"
                    )
                if activities.has_distance < activities.total * 0.95:
                    validation_results["issues"].append(
                        "Some activities missing distance data"
                    )
                if activities.has_elevation < activities.total * 0.5:
                    validation_results["issues"].append(
                        "Many activities missing elevation data"
                    )
            else:
                validation_results["issues"].append("No recent activities found")

        except Exception as e:
            validation_results["issues"].append(
                f"Error validating activity data: {str(e)}"
            )

        return validation_results

"""
Plan Comparison Utilities

Tools to compare plan generation outputs from v1 and v2 endpoints
to ensure refactored code produces identical results.
"""

import json
from typing import Dict, Any, List, Optional
from deepdiff import DeepDiff


def normalize_plan_response(response_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize plan response for comparison by removing fields that can legitimately differ.

    Removes:
    - Date fields (week_start_date, week_label) that depend on generation time
    - Metadata fields that are reference data
    """
    normalized = json.loads(json.dumps(response_data))  # Deep copy

    if "draft" not in normalized:
        return normalized

    draft = normalized["draft"]

    # Normalize generated_plan
    if "generated_plan" in draft:
        gp = draft["generated_plan"]

        # Remove date-dependent fields from weeks
        for week in gp.get("weeks", []):
            week.pop("week_start_date", None)
            week.pop("week_label", None)

        # Normalize race_metadata dates (keep structure but remove time-dependent fields)
        if "race_metadata" in gp:
            rm = gp["race_metadata"]
            # Keep race_date but normalize format
            if "start_date" in rm:
                rm.pop("start_date", None)
            if "start_date_label" in rm:
                rm.pop("start_date_label", None)

    # Normalize plan_request (reference data, can differ)
    draft.pop("plan_request", None)

    return normalized


def compare_week(week1: Dict[str, Any], week2: Dict[str, Any]) -> List[str]:
    """
    Compare two week objects and return list of differences.

    Returns:
        List of difference descriptions, empty if identical
    """
    differences = []

    # Compare core fields
    fields_to_compare = ["week_number", "phase", "long_run_miles", "weekly_mileage"]

    for field in fields_to_compare:
        val1 = week1.get(field)
        val2 = week2.get(field)
        if val1 != val2:
            differences.append(f"{field}: {val1} vs {val2}")

    # Compare workouts
    workouts1 = week1.get("workouts", [])
    workouts2 = week2.get("workouts", [])

    if len(workouts1) != len(workouts2):
        differences.append(f"Workout count: {len(workouts1)} vs {len(workouts2)}")
    else:
        # Sort workouts by day for comparison
        workouts1_sorted = sorted(workouts1, key=lambda w: w.get("day", ""))
        workouts2_sorted = sorted(workouts2, key=lambda w: w.get("day", ""))

        for i, (w1, w2) in enumerate(zip(workouts1_sorted, workouts2_sorted)):
            # Compare workout fields
            workout_fields = ["day", "distance_miles", "workout_type"]
            for field in workout_fields:
                val1 = w1.get(field)
                val2 = w2.get(field)
                if val1 != val2:
                    differences.append(
                        f"Week {week1.get('week_number')} workout {i} {field}: {val1} vs {val2}"
                    )

    return differences


def compare_plan_outputs(
    v1_response: Dict[str, Any], v2_response: Dict[str, Any], normalize: bool = True
) -> Dict[str, Any]:
    """
    Compare two plan responses and return detailed comparison results.

    Args:
        v1_response: Response from v1 endpoint
        v2_response: Response from v2 endpoint
        normalize: Whether to normalize responses before comparison

    Returns:
        Dict with:
        - "identical": bool - Whether responses are identical
        - "differences": List[str] - List of difference descriptions
        - "week_differences": Dict[int, List[str]] - Week-by-week differences
        - "validation_match": bool - Whether validation results match
        - "time_assessment_match": bool - Whether time assessments match
    """
    if normalize:
        v1_normalized = normalize_plan_response(v1_response)
        v2_normalized = normalize_plan_response(v2_response)
    else:
        v1_normalized = v1_response
        v2_normalized = v2_response

    differences = []
    week_differences = {}

    # Extract draft data
    v1_draft = v1_normalized.get("draft", {})
    v2_draft = v2_normalized.get("draft", {})

    # Compare generated_plan
    v1_weeks = v1_draft.get("generated_plan", {}).get("weeks", [])
    v2_weeks = v2_draft.get("generated_plan", {}).get("weeks", [])

    if len(v1_weeks) != len(v2_weeks):
        differences.append(f"Week count differs: {len(v1_weeks)} vs {len(v2_weeks)}")
        return {
            "identical": False,
            "differences": differences,
            "week_differences": {},
            "validation_match": False,
            "time_assessment_match": False,
        }

    # Compare each week
    for i, (v1_week, v2_week) in enumerate(zip(v1_weeks, v2_weeks)):
        week_num = v1_week.get("week_number", i + 1)
        week_diff = compare_week(v1_week, v2_week)
        if week_diff:
            week_differences[week_num] = week_diff
            differences.extend([f"Week {week_num}: {d}" for d in week_diff])

    # Compare validation
    v1_valid = v1_draft.get("validation", {})
    v2_valid = v2_draft.get("validation", {})
    validation_match = v1_valid.get("valid") == v2_valid.get("valid") and len(
        v1_valid.get("violations", [])
    ) == len(v2_valid.get("violations", []))

    if not validation_match:
        differences.append("Validation results differ")

    # Compare time assessment (code should match)
    v1_time = v1_draft.get("time_assessment")
    v2_time = v2_draft.get("time_assessment")
    time_assessment_match = (v1_time is None and v2_time is None) or (
        v1_time is not None
        and v2_time is not None
        and v1_time.get("code") == v2_time.get("code")
    )

    if not time_assessment_match:
        differences.append("Time assessment differs")

    return {
        "identical": len(differences) == 0,
        "differences": differences,
        "week_differences": week_differences,
        "validation_match": validation_match,
        "time_assessment_match": time_assessment_match,
    }


def compare_with_deepdiff(
    v1_response: Dict[str, Any], v2_response: Dict[str, Any], normalize: bool = True
) -> Optional[DeepDiff]:
    """
    Compare responses using DeepDiff library for detailed diff.

    Returns:
        DeepDiff object if differences found, None if identical
    """
    if normalize:
        v1_normalized = normalize_plan_response(v1_response)
        v2_normalized = normalize_plan_response(v2_response)
    else:
        v1_normalized = v1_response
        v2_normalized = v2_response

    # Exclude paths that can differ
    exclude_paths = [
        "root['draft']['generated_plan']['weeks'][*]['week_start_date']",
        "root['draft']['generated_plan']['weeks'][*]['week_label']",
        "root['draft']['generated_plan']['race_metadata']['start_date']",
        "root['draft']['generated_plan']['race_metadata']['start_date_label']",
        "root['draft']['plan_request']",
    ]

    diff = DeepDiff(
        v1_normalized,
        v2_normalized,
        ignore_order=True,
        exclude_paths=exclude_paths,
        verbose_level=2,
    )

    if diff:
        return diff
    return None

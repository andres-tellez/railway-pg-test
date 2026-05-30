"""Runner profile public API for plan generation, storage, and mobile zones."""

from src.smartcoach_mobile_coach.runner_profile.plan_placement import (
    placement_display,
    placement_focus_tag,
    placement_wu_cd_mi,
    role_to_taxonomy,
    validate_persisted_run_type_key,
    infer_placement_role_from_label,
    infer_run_type_key_from_workout_label,
    recognize_run_type_key_from_workout_label,
)
from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
    normalize_run_type_key,
    resolve_run_type,
)
from src.smartcoach_mobile_coach.runner_profile.plan_workout_taxonomy import (
    athlete_label_for_plan_workout,
    canonical_run_type_for_taxonomy,
    get_detail_archetype,
    get_workout_definition,
    is_quality_workout,
    pace_zone_key_for_taxonomy,
    placement_role_for_taxonomy,
    resolve_taxonomy_and_placement,
    taxonomy_pace_guidance,
    taxonomy_short_label,
    validate_weekly_template,
    workout_display_label,
)

__all__ = [
    "WORKOUT_DEFINITIONS",
    "get_runner_pace_zones_for_plan_generation",
    "get_runner_pace_band_for_run_type",
    "get_runner_pace_zone_key_for_run_type",
    "get_runner_profile",
    "get_runner_training_pace_recommendations",
    "get_runner_zone_string_for_run_type",
    "get_workout_definition",
    "athlete_label_for_plan_workout",
    "canonical_run_type_for_taxonomy",
    "get_detail_archetype",
    "infer_placement_role_from_label",
    "infer_run_type_key_from_workout_label",
    "is_quality_workout",
    "normalize_run_type_key",
    "pace_band_seconds_for_run_type",
    "pace_zone_key_for_taxonomy",
    "placement_display",
    "placement_focus_tag",
    "placement_role_for_taxonomy",
    "placement_wu_cd_mi",
    "recognize_run_type_key_from_workout_label",
    "refresh_runner_profile",
    "resolve_run_type",
    "resolve_taxonomy_and_placement",
    "role_to_taxonomy",
    "runner_pace_ranges_payload",
    "taxonomy_pace_guidance",
    "taxonomy_short_label",
    "validate_persisted_run_type_key",
    "validate_weekly_template",
    "workout_display_label",
]

_SERVICE_EXPORTS = frozenset(
    {
        "get_runner_pace_zones_for_plan_generation",
        "get_runner_pace_band_for_run_type",
        "get_runner_pace_zone_key_for_run_type",
        "get_runner_profile",
        "get_runner_training_pace_recommendations",
        "get_runner_zone_string_for_run_type",
        "pace_band_seconds_for_run_type",
        "refresh_runner_profile",
        "runner_pace_ranges_payload",
    }
)


def __getattr__(name: str):
    if name in _SERVICE_EXPORTS:
        from src.smartcoach_mobile_coach.runner_profile import service

        return getattr(service, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

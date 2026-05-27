"""Tests for weekly template validation against runner_profile taxonomy."""

from __future__ import annotations

import pytest

from src.smartcoach_mobile_coach.runner_profile.plan_workout_taxonomy import (
    WORKOUT_TYPES,
    validate_weekly_template,
)


def test_weekly_templates_import_validates_against_taxonomy():
    """Importing weekly_templates runs SSOT validation without error."""
    import src.services.training_plan.v2.workout_taxonomy.weekly_templates as wt

    assert wt.WEEKLY_TEMPLATES["marathon"][4]["Build"][-1] == "long_run"


def test_validate_weekly_template_accepts_known_taxonomy_keys():
    template = ["tempo", "easy", "steady", "long_run"]
    validate_weekly_template(
        template,
        frequency=4,
        context="test",
    )


@pytest.mark.parametrize("bad_type", ["vo2", "unknown", "endurance"])
def test_validate_weekly_template_rejects_unknown_keys(bad_type):
    template = ["easy", bad_type, "easy", "long_run"]
    with pytest.raises(AssertionError, match="Unknown workout type"):
        validate_weekly_template(template, frequency=4, context="test")


def test_validate_weekly_template_requires_long_run_anchor():
    with pytest.raises(AssertionError, match="must end with 'long_run'"):
        validate_weekly_template(
            ["easy", "easy", "tempo", "easy"],
            frequency=4,
            context="test",
        )


def test_validate_weekly_template_requires_frequency_length():
    with pytest.raises(AssertionError, match="Template length"):
        validate_weekly_template(
            ["easy", "long_run"],
            frequency=4,
            context="test",
        )


def test_all_template_keys_are_subset_of_workout_types():
    from src.services.training_plan.v2.workout_taxonomy.weekly_templates import (
        SCENARIO_OVERRIDES,
        WEEKLY_TEMPLATES,
    )

    seen: set[str] = set()
    for race_dict in WEEKLY_TEMPLATES.values():
        for freq_dict in race_dict.values():
            for template in freq_dict.values():
                seen.update(template)
    for scenario_dict in SCENARIO_OVERRIDES.values():
        for race_dict in scenario_dict.values():
            for freq_dict in race_dict.values():
                for template in freq_dict.values():
                    seen.update(template)
    assert seen.issubset(WORKOUT_TYPES)

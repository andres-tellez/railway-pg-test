from __future__ import annotations

from src.coaching_intelligence.contracts.deficits import DEFICITS_SCHEMA, Deficits
from src.coaching_intelligence.policy.suggestions import (
    _proposed_marathon_clock_after_pace_buffer,
    derive_suggestions,
)
from src.coaching_intelligence.time_clock import format_clock_seconds


def test_format_clock_seconds():
    assert format_clock_seconds(3661) == "1:01:01"
    assert format_clock_seconds(61) == "1:01"


def test_proposed_marathon_clock_adds_pace_buffer_over_distance():
    # 4:00:00 marathon + 10 sec/mi * 26.2 mi ~= 262 s -> 4:04:22
    assert (
        _proposed_marathon_clock_after_pace_buffer(
            target_time="4:00:00",
            pace_deficit_sec_per_mi=10.0,
        )
        == "4:04:22"
    )


def test_derive_suggestions_sets_proposed_value_when_allowed():
    deficits = Deficits(
        schema_version=DEFICITS_SCHEMA,
        pace_deficit_sec_per_mi=10.0,
    )
    plan = {"target_time": "3:30:00"}
    out = derive_suggestions(deficits, plan, allowed_user_actions=[])
    adjust = [x for x in out if x.id == "adjust_goal"]
    assert len(adjust) == 1
    assert adjust[0].proposed_value == "3:34:22"


def test_derive_suggestions_skips_proposed_value_when_target_time_unparsed():
    deficits = Deficits(
        schema_version=DEFICITS_SCHEMA,
        pace_deficit_sec_per_mi=10.0,
    )
    plan = {"target_time": "soon"}
    out = derive_suggestions(deficits, plan, allowed_user_actions=[])
    adjust = [x for x in out if x.id == "adjust_goal"]
    assert len(adjust) == 1
    assert adjust[0].proposed_value is None

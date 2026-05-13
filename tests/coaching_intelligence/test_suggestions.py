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
    # 4:00:00 marathon + 10 sec/mi * 26.2 mi ~= 262 s -> 4:05:00 after 5-min rounding
    assert (
        _proposed_marathon_clock_after_pace_buffer(
            target_time="4:00:00",
            pace_deficit_sec_per_mi=10.0,
        )
        == "4:05:00"
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
    assert adjust[0].proposed_value == "3:35:00"


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


def test_no_suggestion_when_all_deficits_zero():
    deficits = Deficits(schema_version=DEFICITS_SCHEMA)
    plan = {
        "race_distance": "Marathon",
        "race_date": "2099-01-01",
        "primary_goal": "Target Time",
        "target_time": "4:00:00",
        "training_days": ["Mon", "Tue", "Wed", "Thu"],
    }
    out = derive_suggestions(deficits, plan, allowed_user_actions=[])
    assert out == []


def test_adjust_goal_suggestion_proposes_realistic_time_for_thin_baseline():
    """Thin baseline + aggressive goal yields softer proposed marathon clock."""
    from src.coaching_intelligence.policy.deficits import compute_deficits
    from src.coaching_intelligence.policy.demand import compute_demand_score
    from src.coaching_intelligence.time_clock import parse_clock_seconds

    activity = {
        "avg_miles_per_week_approx": 15.0,
        "longest_run_miles": 8.0,
        "pace_reliability": "high",
        "typical_easy_pace_sec_per_mi": 530.0,
    }
    plan = {
        "race_distance": "Marathon",
        "race_date": "2099-12-01",
        "primary_goal": "Target Time",
        "target_time": "3:15:00",
        "training_days": ["Mon", "Wed", "Fri", "Sat"],
    }
    goal_pace_secs = parse_clock_seconds("3:15:00")
    assert goal_pace_secs is not None
    pace_per_mi = float(goal_pace_secs) / 26.2
    ds = compute_demand_score(pace_per_mi, "Marathon")
    deficits = compute_deficits(
        activity,
        plan,
        demand_score=ds,
        goal_marathon_pace_sec_per_mi=pace_per_mi,
        weeks_to_race=20.0,
    )
    assert deficits.pace_deficit_sec_per_mi is not None
    assert deficits.pace_deficit_sec_per_mi > 5.0
    out = derive_suggestions(deficits, plan, allowed_user_actions=[])
    adj = [x for x in out if x.id == "adjust_goal"]
    assert len(adj) == 1
    pv = adj[0].proposed_value
    assert pv is not None
    pv_sec = parse_clock_seconds(pv)
    assert pv_sec is not None
    assert pv_sec > goal_pace_secs

"""Unit tests for SmartCoach run payload mapping."""

from types import SimpleNamespace

import pytest

from src.services.smartcoach_run_mapper import build_smartcoach_run


def _split(
    lap_index: int,
    moving_time: int,
    distance: float,
    elapsed_time: int | None = None,
    hr: float | None = 140.0,
):
    return SimpleNamespace(
        lap_index=lap_index,
        moving_time=moving_time,
        elapsed_time=elapsed_time,
        distance=distance,
        average_heartrate=hr,
    )


def test_build_run_single_split_hr_and_snap():
    activity = SimpleNamespace(
        moving_time=600,
        elapsed_time=620,
        distance=2000.0,
        type="Run",
    )
    splits = [_split(0, 580, 1800.0, hr=150.0)]
    run = build_smartcoach_run(activity, splits)
    assert run["duration_seconds"] == 600
    assert run["samples"][0] == {"elapsed_seconds": 0, "distance_meters": 0.0}
    assert run["samples"][-1]["elapsed_seconds"] == 600
    assert run["samples"][-1]["distance_meters"] == 2000.0
    assert run["samples"][-1]["heart_rate"] == 150


def test_build_run_omits_hr_if_any_split_missing():
    activity = SimpleNamespace(moving_time=300, elapsed_time=300, distance=1000.0)
    splits = [
        _split(0, 150, 500.0, hr=140.0),
        _split(1, 150, 500.0, hr=None),
    ]
    run = build_smartcoach_run(activity, splits)
    for sample in run["samples"]:
        assert "heart_rate" not in sample


def test_build_run_includes_hr_when_all_splits_have_hr():
    activity = SimpleNamespace(moving_time=300, elapsed_time=300, distance=1000.0)
    splits = [
        _split(0, 150, 500.0, hr=140.0),
        _split(1, 150, 500.0, hr=142.0),
    ]
    run = build_smartcoach_run(activity, splits)
    assert "heart_rate" not in run["samples"][0]
    assert run["samples"][1]["heart_rate"] == 140
    assert run["samples"][2]["heart_rate"] == 142


def test_rejects_split_sum_over_duration():
    activity = SimpleNamespace(moving_time=100, elapsed_time=100, distance=400.0)
    splits = [_split(0, 200, 400.0)]
    with pytest.raises(ValueError, match="more than activity moving_time"):
        build_smartcoach_run(activity, splits)


def test_rejects_empty_splits():
    activity = SimpleNamespace(moving_time=100, elapsed_time=100, distance=400.0)
    with pytest.raises(ValueError, match="No split rows"):
        build_smartcoach_run(activity, [])

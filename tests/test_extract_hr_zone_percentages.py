import pytest
from src.services.activity_service import extract_hr_zone_percentages


def test_extract_hr_zone_percentages_normal():
    zones_data = [
        {
            "type": "heartrate",
            "distribution_buckets": [
                {"time": 100},
                {"time": 200},
                {"time": 300},
                {"time": 400},
                {"time": 0},
            ],
        }
    ]
    expected = [10.0, 20.0, 30.0, 40.0, 0.0]
    result = extract_hr_zone_percentages(zones_data)
    assert result == expected


def test_extract_hr_zone_percentages_zero_total():
    zones_data = [
        {
            "type": "heartrate",
            "distribution_buckets": [
                {"time": 0},
                {"time": 0},
                {"time": 0},
                {"time": 0},
                {"time": 0},
            ],
        }
    ]
    result = extract_hr_zone_percentages(zones_data)
    assert result == [0.0, 0.0, 0.0, 0.0, 0.0]


def test_extract_hr_zone_percentages_no_heartrate():
    zones_data = [{"type": "something_else", "distribution_buckets": []}]
    result = extract_hr_zone_percentages(zones_data)
    assert result == [0.0, 0.0, 0.0, 0.0, 0.0]


def test_extract_hr_zone_percentages_malformed_input():
    result = extract_hr_zone_percentages(None)
    assert result == [0.0, 0.0, 0.0, 0.0, 0.0]

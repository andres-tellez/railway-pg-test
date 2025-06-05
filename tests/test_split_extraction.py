# tests/test_split_extraction.py

from src.services.split_extraction import extract_splits

def test_extract_splits():
    sample_activity = {
        "id": 123,
        "splits_metric": [
            {
                "split": 1,
                "distance": 1000.0,
                "elapsed_time": 300,
                "average_speed": 3.33
            }
        ]
    }

    splits = extract_splits(sample_activity)

    assert len(splits) == 1

    expected = {
        "activity_id": 123,
        "lap_index": 1,
        "distance": 1000.0,
        "elapsed_time": 300,
        "moving_time": None,
        "average_speed": 3.33,
        "max_speed": None,
        "start_index": None,
        "end_index": None,
        "split": True
    }

    # Compare each key individually
    for key in expected:
        assert splits[0][key] == expected[key]


def test_extract_splits_empty():
    sample_activity = {
        "id": 456,
        "splits_metric": None
    }

    splits = extract_splits(sample_activity)
    assert splits == []


def test_extract_splits_no_splits_metric():
    sample_activity = {
        "id": 789
    }

    splits = extract_splits(sample_activity)
    assert splits == []

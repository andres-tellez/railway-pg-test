# tests/test_data/sample_activities.py

SAMPLE_ACTIVITY_JSON = {
    "id": 99999,
    "activity_id": 99999,
    "external_id": "external_99999",  # required field
    "name": "Mock Run",
    "type": "Run",
    "distance": 5000.0,
    "moving_time": 1500,
    "elapsed_time": 1600,
    "total_elevation_gain": 50.0,
    "average_speed": 3.5,
    "max_speed": 4.0,
    "suffer_score": 30,
    "average_heartrate": 150,
    "max_heartrate": 170,
    "calories": 400,
    "start_date": "2025-06-01T08:00:00Z",  # <--- ADD THIS LINE
    "splits_metric": [
        {
            "lap_index": 1,
            "distance": 1000,
            "elapsed_time": 300,
            "moving_time": 295,
            "average_speed": 3.33,
            "max_speed": 3.5,
            "start_index": 0,
            "end_index": 299,
            "split": 1,
            "average_heartrate": 145,
            "pace_zone": 2
        }
    ]
}

SAMPLE_HR_ZONE_RESPONSE = {
    "heart_rate": {
        "custom_zones": [
            {"score": 0.1},
            {"score": 0.2},
            {"score": 0.3},
            {"score": 0.25},
            {"score": 0.15}
        ]
    }
}

SAMPLE_STREAMS_RESPONSE = {
    "distance": {"data": [0.0, 500.0, 1000.0]},
    "time": {"data": [0, 150, 300]},
    "velocity_smooth": {"data": [3.2, 3.4, 3.3]},
    "heartrate": {"data": [130, 140, 150]}
}

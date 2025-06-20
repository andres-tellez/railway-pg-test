import pytest
from unittest.mock import patch, MagicMock
import src.scripts.main_pipeline as main_pipeline

def test_main_pipeline_calls_full_ingestion(monkeypatch):
    test_args = ["main_pipeline.py", "--athlete_id", "123"]
    monkeypatch.setattr("sys.argv", test_args)

    mock_session = MagicMock()
    mock_ingestion = patch("src.scripts.main_pipeline.run_full_ingestion_and_enrichment").start()
    patch("src.scripts.main_pipeline.get_session", return_value=mock_session).start()

    with pytest.raises(SystemExit):
        main_pipeline.main()

    mock_ingestion.assert_called_once_with(mock_session, 123, lookback_days=30, batch_size=10)
    patch.stopall()

def test_main_pipeline_calls_specific_activity(monkeypatch):
    test_args = ["main_pipeline.py", "--athlete_id", "123", "--activity_id", "456"]
    monkeypatch.setattr("sys.argv", test_args)

    mock_session = MagicMock()
    mock_specific = patch("src.scripts.main_pipeline.ingest_specific_activity").start()
    patch("src.scripts.main_pipeline.get_session", return_value=mock_session).start()

    with pytest.raises(SystemExit):
        main_pipeline.main()

    mock_specific.assert_called_once_with(mock_session, 123, 456)
    patch.stopall()

def test_main_pipeline_calls_between_dates(monkeypatch):
    test_args = [
        "main_pipeline.py", "--athlete_id", "123",
        "--start_date", "2025-01-01", "--end_date", "2025-01-05"
    ]
    monkeypatch.setattr("sys.argv", test_args)

    mock_session = MagicMock()
    mock_between = patch("src.scripts.main_pipeline.ingest_between_dates").start()
    patch("src.scripts.main_pipeline.get_session", return_value=mock_session).start()

    with pytest.raises(SystemExit):
        main_pipeline.main()

    called_args = mock_between.call_args[0]
    assert called_args[0] == mock_session
    assert called_args[1] == 123
    assert str(called_args[2].date()) == "2025-01-01"
    assert str(called_args[3].date()) == "2025-01-05"
    patch.stopall()

def test_main_pipeline_handles_exception(monkeypatch):
    test_args = ["main_pipeline.py", "--athlete_id", "123"]
    monkeypatch.setattr("sys.argv", test_args)

    mock_session = MagicMock()
    patch("src.scripts.main_pipeline.get_session", return_value=mock_session).start()
    patch("src.scripts.main_pipeline.run_full_ingestion_and_enrichment", side_effect=Exception("fail")).start()

    with pytest.raises(SystemExit):
        main_pipeline.main()

    patch.stopall()

import types
import pytest
from unittest.mock import patch, MagicMock
import src.scripts.main_pipeline as main_pipeline


def test_main_pipeline_calls_full_ingestion(monkeypatch):
    test_args = ["main_pipeline.py", "--athlete_id", "123"]
    monkeypatch.setattr("sys.argv", test_args)

    # Mock token with concrete expires_at attribute
    mock_token = types.SimpleNamespace(expires_at=9999999999)

    # Mock query chain to return the token
    mock_filter = MagicMock()
    mock_filter.first.return_value = mock_token
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_filter

    mock_session = MagicMock()
    mock_session.query.return_value = mock_query

    patch_get_session = patch("src.scripts.main_pipeline.get_session", return_value=mock_session)
    patch_get_session.start()

    patch_get_tokens_sa = patch("src.scripts.main_pipeline.get_tokens_sa", return_value=mock_token)
    patch_get_tokens_sa.start()

    # Patch run_full_ingestion_and_enrichment to MagicMock
    mock_ingestion = patch("src.scripts.main_pipeline.run_full_ingestion_and_enrichment").start()

    # PATCH refresh_token_if_expired to a no-op to avoid MagicMock expires_at issue
    patch_refresh_token = patch("src.scripts.main_pipeline.refresh_token_if_expired", return_value=None)
    patch_refresh_token.start()

    with pytest.raises(SystemExit):
        main_pipeline.main()

    mock_ingestion.assert_called_once()
    args, kwargs = mock_ingestion.call_args
    assert args[0] == mock_session
    assert args[1] == 123
    assert kwargs.get("lookback_days", 30) == 30
    assert kwargs.get("batch_size", 10) == 10

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

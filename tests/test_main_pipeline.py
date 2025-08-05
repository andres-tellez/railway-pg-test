# tests/test_main_pipeline.py

import types
import pytest
from unittest.mock import patch, MagicMock
import src.scripts.main_pipeline as main_pipeline


def test_main_pipeline_calls_full_ingestion(monkeypatch):
    test_args = ["main_pipeline.py", "--athlete_id", "123", "--lookback_days", "30"]
    monkeypatch.setattr("sys.argv", test_args)

    mock_token = types.SimpleNamespace(expires_at=9999999999)

    mock_filter = MagicMock()
    mock_filter.first.return_value = mock_token
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_filter

    mock_session = MagicMock()
    mock_session.query.return_value = mock_query

    patch_get_session = patch(
        "src.scripts.main_pipeline.get_session", return_value=mock_session
    )
    patch_get_tokens_sa = patch(
        "src.scripts.main_pipeline.get_tokens_sa", return_value=mock_token
    )
    patch_ingestion = patch(
        "src.scripts.main_pipeline.run_full_ingestion_and_enrichment"
    )
    patch_refresh_token = patch(
        "src.scripts.main_pipeline.refresh_token_if_expired", return_value=None
    )

    mock_get_session = patch_get_session.start()
    mock_get_tokens = patch_get_tokens_sa.start()
    mock_ingest = patch_ingestion.start()
    patch_refresh_token.start()

    try:
        with pytest.raises(SystemExit):
            main_pipeline.main()

        mock_ingest.assert_called_once()
        args, kwargs = mock_ingest.call_args
        assert args[0] == mock_session
        assert args[1] == 123
        assert kwargs["lookback_days"] == 30
        assert kwargs["batch_size"] == 10
    finally:
        patch.stopall()


def test_main_pipeline_calls_specific_activity(monkeypatch):
    test_args = ["main_pipeline.py", "--athlete_id", "123", "--activity_id", "456"]
    monkeypatch.setattr("sys.argv", test_args)

    session_mock = MagicMock()
    patch_get_session = patch(
        "src.scripts.main_pipeline.get_session", return_value=session_mock
    )
    patch_specific = patch("src.scripts.main_pipeline.ingest_specific_activity")

    mock_get_session = patch_get_session.start()
    mock_ingest = patch_specific.start()

    try:
        with pytest.raises(SystemExit):
            main_pipeline.main()

        mock_ingest.assert_called_once()
        args = mock_ingest.call_args[0]
        assert args[0] == session_mock
        assert args[1] == 123
        assert args[2] == 456
    finally:
        patch.stopall()


def test_main_pipeline_calls_between_dates(monkeypatch):
    test_args = [
        "main_pipeline.py",
        "--athlete_id",
        "123",
        "--start_date",
        "2025-01-01",
        "--end_date",
        "2025-01-05",
    ]
    monkeypatch.setattr("sys.argv", test_args)

    session_mock = MagicMock()
    patch_get_session = patch(
        "src.scripts.main_pipeline.get_session", return_value=session_mock
    )
    patch_between = patch("src.scripts.main_pipeline.ingest_between_dates")

    mock_get_session = patch_get_session.start()
    mock_ingest = patch_between.start()

    try:
        with pytest.raises(SystemExit):
            main_pipeline.main()

        args = mock_ingest.call_args[0]
        assert args[0] == session_mock
        assert args[1] == 123
        assert str(args[2].date()) == "2025-01-01"
        assert str(args[3].date()) == "2025-01-05"
    finally:
        patch.stopall()


def test_main_pipeline_handles_exception(monkeypatch):
    test_args = ["main_pipeline.py", "--athlete_id", "123"]
    monkeypatch.setattr("sys.argv", test_args)

    patch_get_session = patch(
        "src.scripts.main_pipeline.get_session", return_value=MagicMock()
    )
    patch_ingest = patch(
        "src.scripts.main_pipeline.run_full_ingestion_and_enrichment",
        side_effect=Exception("fail"),
    )

    patch_get_session.start()
    patch_ingest.start()

    try:
        with pytest.raises(SystemExit):
            main_pipeline.main()
    finally:
        patch.stopall()

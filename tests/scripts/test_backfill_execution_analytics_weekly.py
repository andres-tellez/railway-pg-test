"""Backfill script uses centralized weekly reconcile."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import scripts.backfill_execution_analytics as backfill_mod


@patch("scripts.backfill_execution_analytics.ensure_user_weekly_insights")
@patch("scripts.backfill_execution_analytics._backfill_user")
@patch("scripts.backfill_execution_analytics.sessionmaker")
@patch("scripts.backfill_execution_analytics.create_engine")
@patch.dict("os.environ", {"PROD_DATABASE_URL": "postgresql://test"}, clear=False)
def test_main_user_id_path_calls_reconciler(
    mock_engine, mock_sessionmaker, mock_backfill_user, mock_ensure
):
    mock_backfill_user.return_value = 2
    mock_ensure.return_value = {
        "summary": {"generated": 3, "skipped": 4, "errors": 0},
    }
    session = MagicMock()
    mock_sessionmaker.return_value.return_value = session

    with patch.object(
        backfill_mod.argparse.ArgumentParser,
        "parse_args",
        return_value=MagicMock(
            prod=True,
            staging=False,
            user_id="149cd9b1-20a8-41b8-a514-b688b4dca868",
            force_all=False,
            lookback_days=None,
            skip_weekly_insights=False,
            weekly_weeks=6,
        ),
    ):
        backfill_mod.main()

    mock_ensure.assert_called_once_with(
        session,
        "149cd9b1-20a8-41b8-a514-b688b4dca868",
        weeks=6,
        include_current_week=True,
    )


@patch("scripts.backfill_execution_analytics.ensure_user_weekly_insights")
@patch("scripts.backfill_execution_analytics._backfill_user")
@patch("scripts.backfill_execution_analytics.sessionmaker")
@patch("scripts.backfill_execution_analytics.create_engine")
@patch.dict(
    "os.environ",
    {"STAGING_DATABASE_URL": "postgresql://staging-host/railway"},
    clear=False,
)
def test_main_staging_uses_staging_database_url(
    mock_engine, mock_sessionmaker, mock_backfill_user, mock_ensure
):
    mock_backfill_user.return_value = 0
    mock_ensure.return_value = {"summary": {"generated": 0, "skipped": 0, "errors": 0}}
    session = MagicMock()
    mock_sessionmaker.return_value.return_value = session

    with patch.object(
        backfill_mod.argparse.ArgumentParser,
        "parse_args",
        return_value=MagicMock(
            prod=False,
            staging=True,
            user_id="149cd9b1-20a8-41b8-a514-b688b4dca868",
            force_all=False,
            lookback_days=None,
            skip_weekly_insights=True,
            weekly_weeks=6,
        ),
    ):
        backfill_mod.main()

    mock_engine.assert_called_once()
    assert mock_engine.call_args[0][0] == "postgresql://staging-host/railway"


def test_resolve_database_target_rejects_prod_and_staging():
    import pytest

    with pytest.raises(SystemExit):
        backfill_mod._resolve_database_target(prod=True, staging=True)

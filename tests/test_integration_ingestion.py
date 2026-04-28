"""Legacy integration tests for removed ingest_specific_activity flow."""

import pytest

pytestmark = pytest.mark.skip(
    reason=(
        "Obsolete: ingest_specific_activity and prior DB/session fixtures no longer "
        "match ingestion_orchestrator_service; tests archived to keep collection clean."
    )
)


def test_placeholder_obsolete_integration_ingestion():
    assert False, "unreachable"

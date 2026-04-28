"""Legacy tests for old ingestion orchestrator entrypoints."""

import pytest

pytestmark = pytest.mark.skip(
    reason=(
        "Obsolete: ingest_specific_activity / ingest_between_dates are not exported "
        "from ingestion_orchestrator_service (replaced by run_full_ingestion_and_enrichment); "
        "tests archived to keep collection clean."
    )
)


def test_placeholder_obsolete_ingestion_orchestrator():
    assert False, "unreachable"

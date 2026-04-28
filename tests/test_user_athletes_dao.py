"""Legacy DAO tests targeting removed ``Athlete`` model and old create_link API."""

import pytest

pytestmark = pytest.mark.skip(
    reason=(
        "Obsolete: src.db.models.athletes and auth0-style user_id fixtures do not match "
        "current user_athletes_dao (UUID user_identity + UserAthleteLink); "
        "tests archived to keep collection clean."
    )
)


def test_placeholder_obsolete_user_athletes_dao():
    assert False, "unreachable"

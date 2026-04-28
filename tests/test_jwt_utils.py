"""Legacy tests for removed ``src.utils.jwt_utils`` (Auth0 handling is in auth0_jwt)."""

import pytest

pytestmark = pytest.mark.skip(
    reason=(
        "Obsolete: src.utils.jwt_utils was removed; use src.utils.auth0_jwt with new tests; "
        "this module archived to keep collection clean."
    )
)


def test_placeholder_obsolete_jwt_utils():
    assert False, "unreachable"

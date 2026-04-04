"""
Unit tests for email_verification claim parsing (used by user_identity_dao).

Run without the repo's SQLite session autouse fixture (models use JSONB):
  pytest tests/test_user_identity_dao_verified_email.py -v --no-cov --noconftest
"""

import pytest

from src.utils.email_verification import is_email_verified_claim


@pytest.mark.parametrize(
    "val,expected",
    [
        (True, True),
        (False, False),
        (None, False),
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("false", False),
        ("", False),
        ("  ", False),
        (0, False),
        ([], False),
    ],
)
def test_is_email_verified_claim(val, expected):
    assert is_email_verified_claim(val) is expected

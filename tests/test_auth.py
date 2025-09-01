import pytest

# 🚨 Skipped: all tests in this file referenced HS256 SECRET_KEY auth.
pytestmark = pytest.mark.skip(
    reason="Legacy HS256 / password login removed. All auth uses Auth0 RS256 now."
)

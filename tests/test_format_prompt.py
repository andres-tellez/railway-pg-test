"""Legacy tests for ``format_prompt`` removed from ``src.utils.gpt_ops``."""

import pytest

pytestmark = pytest.mark.skip(
    reason=(
        "Obsolete: format_prompt is not defined in gpt_ops (module migrated); "
        "tests archived to keep collection clean."
    )
)


def test_placeholder_obsolete_format_prompt():
    assert False, "unreachable"

"""Legacy tests for removed ``PromptBuilderService`` (module no longer in tree)."""

import pytest

pytestmark = pytest.mark.skip(
    reason=(
        "Obsolete: src.services.training_plan.prompt_builder_service was removed; "
        "tests archived to keep collection clean."
    )
)


def test_placeholder_obsolete_prompt_builder_service():
    assert False, "unreachable"

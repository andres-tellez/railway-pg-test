"""Client flag: structured_input_only (deterministic chip turns)."""

from __future__ import annotations

from src.smartcoach_mobile_coach.routes import _coerce_structured_input_only


def test_coerce_structured_input_only_true():
    assert _coerce_structured_input_only({"structured_input_only": True}) is True
    assert _coerce_structured_input_only({"structuredInputOnly": "yes"}) is True
    assert _coerce_structured_input_only({"structured_input_only": "1"}) is True


def test_coerce_structured_input_only_false():
    assert _coerce_structured_input_only({}) is False
    assert _coerce_structured_input_only({"structured_input_only": False}) is False

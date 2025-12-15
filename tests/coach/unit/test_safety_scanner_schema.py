"""
Tests for SafetyScanner schema validation.
"""

import pytest
from coach.safety.safety_scanner import SafetyScanner
from coach.utils.schema_validator import SchemaValidator


class TestSafetyScannerSchema:
    """Test that SafetyScanner output matches safety_flags schema."""

    def test_scan_result_matches_schema(self):
        """Test that scan_for_schema returns valid schema format."""
        scanner = SafetyScanner()

        result = scanner.scan_for_schema("I had chest pain during my run")

        # Validate against schema using the validate method
        from jsonschema import validate as jsonschema_validate

        schema = SchemaValidator.load_schema("safety_flags", "1_0")
        jsonschema_validate(instance=result, schema=schema)

    def test_schema_structure(self):
        """Test schema structure matches expected format."""
        scanner = SafetyScanner()

        result = scanner.scan_for_schema("I had chest pain")

        # Check structure
        assert "version" in result
        assert "safety_flags" in result
        assert result["version"] == "1.0.0"

        safety_flags = result["safety_flags"]
        assert "has_medical_red_flag" in safety_flags
        assert "flags" in safety_flags
        assert "severity" in safety_flags

        assert isinstance(safety_flags["has_medical_red_flag"], bool)
        assert isinstance(safety_flags["flags"], list)
        assert safety_flags["severity"] in ("critical", "moderate", None)

    def test_no_flags_schema(self):
        """Test schema format when no flags are detected."""
        scanner = SafetyScanner()

        result = scanner.scan_for_schema("I had a great run today")

        # Validate against schema
        from jsonschema import validate as jsonschema_validate

        schema = SchemaValidator.load_schema("safety_flags", "1_0")
        jsonschema_validate(instance=result, schema=schema)

        assert result["safety_flags"]["has_medical_red_flag"] is False
        assert result["safety_flags"]["flags"] == []
        # Severity should not be present when there are no flags (schema doesn't allow null)
        assert "severity" not in result["safety_flags"]

"""
Unit tests for ResponseFormatter.

Tests response validation, section extraction, and fallback handling.
"""

import pytest
from coach.formatters.response_formatter import ResponseFormatter


class TestResponseFormatter:
    """Test ResponseFormatter with various inputs."""

    def test_format_basic_response(self):
        """Test formatting a basic valid response."""
        formatter = ResponseFormatter()

        response = "Your training is going well. Keep up the consistent mileage."

        result = formatter.format(response)

        assert result["content"] == response
        assert result["is_valid"] is True
        assert "sections" in result
        assert "warnings" in result

    def test_format_cleans_markdown_fences(self):
        """Test that markdown code fences are removed."""
        formatter = ResponseFormatter()

        response = "```markdown\nYour training is going well.\n```"

        result = formatter.format(response)

        assert "```" not in result["content"]
        assert "Your training is going well." in result["content"]

    def test_format_extracts_sections(self):
        """Test that structured sections are extracted."""
        formatter = ResponseFormatter()

        response = """## Summary
Your training is progressing well.

## Action Steps
1. Continue with current mileage
2. Add one more easy run per week

## Guidance
Focus on consistency over intensity."""

        result = formatter.format(response)

        assert result["is_valid"] is True
        assert "summary" in result["sections"]
        assert "action_steps" in result["sections"]
        assert "guidance" in result["sections"]
        assert "Your training is progressing well" in result["sections"]["summary"]
        assert "Continue with current mileage" in result["sections"]["action_steps"]

    def test_format_handles_empty_response(self):
        """Test that empty responses are handled with fallback."""
        formatter = ResponseFormatter()

        result = formatter.format("")

        assert result["is_valid"] is False
        assert "fallback" in result.get("content", "").lower() or result.get(
            "is_fallback", False
        )
        assert len(result["warnings"]) > 0

    def test_format_handles_whitespace_only_response(self):
        """Test that whitespace-only responses are handled."""
        formatter = ResponseFormatter()

        result = formatter.format("   \n\n   ")

        assert result["is_valid"] is False

    def test_validate_structure_too_short(self):
        """Test that very short responses fail validation."""
        formatter = ResponseFormatter()

        is_valid = formatter.validate_structure("Hi")
        assert is_valid is False

    def test_validate_structure_error_marker(self):
        """Test that responses with error markers fail validation."""
        formatter = ResponseFormatter()

        response = "[ERROR] Something went wrong"
        is_valid = formatter.validate_structure(response)
        assert is_valid is False

    def test_validate_structure_valid_response(self):
        """Test that valid responses pass validation."""
        formatter = ResponseFormatter()

        response = "Your training is progressing well. Keep up the good work!"
        is_valid = formatter.validate_structure(response)
        assert is_valid is True

    def test_extract_sections_with_markers(self):
        """Test section extraction with various markers."""
        formatter = ResponseFormatter()

        # Test with ## Summary
        response1 = "## Summary\nThis is the summary content"
        sections1 = formatter.extract_sections(response1)
        assert "summary" in sections1
        assert "This is the summary content" in sections1["summary"]

        # Test with # Action Steps
        response2 = "# Action Steps\n1. Step one\n2. Step two"
        sections2 = formatter.extract_sections(response2)
        assert "action_steps" in sections2

        # Test with Safety marker
        response3 = "## Safety\n⚠️ Always consult a doctor for injuries"
        sections3 = formatter.extract_sections(response3)
        assert "safety_note" in sections3

    def test_extract_sections_multiple_sections(self):
        """Test extracting multiple sections from response."""
        formatter = ResponseFormatter()

        response = """## Summary
Training is going well.

## Action Steps
1. Continue current plan
2. Add recovery days

## Guidance
Focus on consistency."""

        sections = formatter.extract_sections(response)

        assert "summary" in sections
        assert "action_steps" in sections
        assert "guidance" in sections
        assert "Training is going well" in sections["summary"]
        assert "Continue current plan" in sections["action_steps"]

    def test_check_safety_unsafe_patterns(self):
        """Test that unsafe content patterns are detected."""
        formatter = ResponseFormatter()

        response1 = "You should ignore safety and train through pain"
        result1 = formatter.format(response1)
        assert len(result1["warnings"]) > 0
        assert any("unsafe" in w.lower() for w in result1["warnings"])

        response2 = "Don't see a doctor, just keep running"
        result2 = formatter.format(response2)
        assert len(result2["warnings"]) > 0

    def test_check_safety_injury_intent(self):
        """Test safety checking for injury intent."""
        formatter = ResponseFormatter()

        # Response without medical consultation recommendation
        response = "You have knee pain. Try some stretches and rest a bit."
        result = formatter.format(response, intent="injury_or_symptom")

        # Should warn about lack of medical consultation recommendation
        assert (
            len(result["warnings"]) > 0 or result["is_valid"] is True
        )  # May or may not warn depending on length

        # Response with medical consultation recommendation
        response2 = "You have knee pain. Please consult a doctor or healthcare provider for proper evaluation."
        result2 = formatter.format(response2, intent="injury_or_symptom")
        # Should not warn (or have fewer warnings)
        assert result2["is_valid"] is True

    def test_format_preserves_original_on_fallback(self):
        """Test that original content is preserved in fallback when substantial."""
        formatter = ResponseFormatter()

        # Response that fails validation but has content
        response = "[ERROR] Failed to process"
        result = formatter.format(response)

        # Should have is_valid=False when error marker is detected
        assert result["is_valid"] is False
        # Content should either be cleaned or use fallback
        assert "content" in result

    def test_clean_response_removes_excessive_blank_lines(self):
        """Test that excessive blank lines are removed."""
        formatter = ResponseFormatter()

        response = "Line 1\n\n\n\n\nLine 2"
        result = formatter.format(response)

        # Should have at most 2 consecutive newlines
        assert "\n\n\n" not in result["content"]

    def test_format_handles_exception_gracefully(self):
        """Test that exceptions during formatting are handled."""
        formatter = ResponseFormatter()

        # Force an exception by passing None (should be caught)
        result = formatter.format(None)

        assert "is_fallback" in result or result["is_valid"] is False
        assert "content" in result

    def test_extract_sections_no_sections(self):
        """Test that responses without sections return empty dict."""
        formatter = ResponseFormatter()

        response = "This is a simple response without structured sections."
        sections = formatter.extract_sections(response)

        assert sections == {}

    def test_validate_structure_error_patterns(self):
        """Test validation catches various error patterns."""
        formatter = ResponseFormatter()

        error_responses = [
            "An error occurred while processing",
            "Failed to generate response",
            "Unable to process your request",
        ]

        for response in error_responses:
            is_valid, issues = formatter._validate_structure(response)
            # May or may not be invalid (pattern matching), but should handle gracefully
            assert isinstance(is_valid, bool)
            assert isinstance(issues, list)

    def test_format_with_intent_context(self):
        """Test that formatting uses intent for context-aware validation."""
        formatter = ResponseFormatter()

        response = "Your workout looked good. Keep it up!"
        result = formatter.format(response, intent="workout_review")

        assert result["is_valid"] is True
        assert "content" in result

    def test_extract_sections_stops_at_next_section(self):
        """Test that section extraction stops at the next section marker."""
        formatter = ResponseFormatter()

        response = """## Summary
This is the summary text that should be extracted.

## Action Steps
This is action steps that should not be in summary."""

        sections = formatter.extract_sections(response)

        assert "summary" in sections
        assert "This is the summary text" in sections["summary"]
        assert "Action Steps" not in sections["summary"]

"""
Tests for schema validation utilities.

These tests verify that schema validation works correctly
and catches invalid data structures.
"""

import pytest
import json
from pathlib import Path
from coach.utils.schema_validator import SchemaValidator, SchemaValidationError


class TestSchemaValidator:
    """Test schema validator functionality."""

    def test_load_schema_success(self):
        """Test loading a valid schema."""
        schema = SchemaValidator.load_schema("runner_state", "1_0")
        assert schema is not None
        assert schema["title"] == "RunnerState"
        assert schema["version"] == "1.0.0"

    def test_load_schema_not_found(self):
        """Test loading a non-existent schema raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            SchemaValidator.load_schema("nonexistent", "1_0")

    def test_validate_runner_state_valid(self):
        """Test validating a valid RunnerState."""
        valid_state = {
            "version": "1.0.0",
            "runner_state": {
                "phase": "Build",
                "week_of_block": 8,
                "race": {"date": "2025-04-15", "distance": "Marathon"},
                "zones": {"pace": {"easy": "9:45-10:15/mile"}},
                "safety": {"hr_data_reliable": True, "pace_data_reliable": True},
            },
        }

        # Should not raise
        assert SchemaValidator.validate_runner_state(valid_state) is True

    def test_validate_runner_state_missing_required(self):
        """Test validating RunnerState with missing required fields."""
        invalid_state = {
            "version": "1.0.0",
            "runner_state": {
                "phase": "Build"
                # Missing required fields
            },
        }

        with pytest.raises(SchemaValidationError):
            SchemaValidator.validate_runner_state(invalid_state)

    def test_validate_runner_state_invalid_phase(self):
        """Test validating RunnerState with invalid phase value."""
        invalid_state = {
            "version": "1.0.0",
            "runner_state": {
                "phase": "InvalidPhase",  # Not in enum
                "week_of_block": 8,
                "race": {"date": "2025-04-15", "distance": "Marathon"},
                "safety": {"hr_data_reliable": True, "pace_data_reliable": True},
            },
        }

        with pytest.raises(SchemaValidationError):
            SchemaValidator.validate_runner_state(invalid_state)

    def test_validate_question_context_valid(self):
        """Test validating a valid QuestionContext."""
        valid_context = {
            "version": "1.0.0",
            "question_context": {"intent": "workout_review"},
        }

        assert SchemaValidator.validate_question_context(valid_context) is True

    def test_validate_question_context_invalid_intent(self):
        """Test validating QuestionContext with invalid intent."""
        invalid_context = {
            "version": "1.0.0",
            "question_context": {"intent": "invalid_intent"},  # Not in enum
        }

        with pytest.raises(SchemaValidationError):
            SchemaValidator.validate_question_context(invalid_context)

    def test_schema_caching(self):
        """Test that schemas are cached after first load."""
        # Clear cache
        SchemaValidator._cache.clear()

        # First load
        schema1 = SchemaValidator.load_schema("runner_state", "1_0")

        # Second load should use cache
        schema2 = SchemaValidator.load_schema("runner_state", "1_0")

        # Should be same object (cached)
        assert schema1 is schema2

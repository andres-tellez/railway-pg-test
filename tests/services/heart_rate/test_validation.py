"""
Tests for HR Zone Validation Utilities
"""

import pytest
from src.services.heart_rate.validation import (
    validate_activities_shape,
    validate_numeric_type,
)


class TestValidation:
    """Test validation utilities."""

    def test_validate_activities_shape_none(self):
        """Test that None activities is invalid."""
        is_valid, error_msg = validate_activities_shape(None)

        assert is_valid is False
        assert "cannot be None" in error_msg

    def test_validate_activities_shape_not_list(self):
        """Test that non-list is invalid."""
        is_valid, error_msg = validate_activities_shape("not a list")

        assert is_valid is False
        assert "must be a list" in error_msg

    def test_validate_activities_shape_empty_list(self):
        """Test that empty list is invalid."""
        is_valid, error_msg = validate_activities_shape([])

        assert is_valid is False
        assert "cannot be empty" in error_msg

    def test_validate_activities_shape_valid(self):
        """Test that valid list passes."""
        activities = [{"max_heartrate": 180, "moving_time": 1200}]

        is_valid, error_msg = validate_activities_shape(activities)

        assert is_valid is True
        assert error_msg is None

    def test_validate_numeric_type_int(self):
        """Test that int is valid."""
        is_valid, error_msg = validate_numeric_type(180, "hrmax")

        assert is_valid is True
        assert error_msg is None

    def test_validate_numeric_type_float(self):
        """Test that float is valid."""
        is_valid, error_msg = validate_numeric_type(180.5, "hrmax")

        assert is_valid is True
        assert error_msg is None

    def test_validate_numeric_type_string(self):
        """Test that string is invalid."""
        is_valid, error_msg = validate_numeric_type("180", "hrmax")

        assert is_valid is False
        assert "must be numeric" in error_msg

    def test_validate_numeric_type_none(self):
        """Test that None is invalid."""
        is_valid, error_msg = validate_numeric_type(None, "hrmax")

        assert is_valid is False
        assert "must be numeric" in error_msg

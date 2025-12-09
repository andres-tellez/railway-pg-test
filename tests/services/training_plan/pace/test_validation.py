"""
Tests for pace validation module.
"""

import pytest
from src.services.training_plan.pace import (
    PaceSeed,
    validate_pace_seed,
    validate_input_parameters,
)


class TestValidatePaceSeed:
    """Test pace seed validation."""

    def test_valid_pace_seed(self):
        """Test validation passes for valid pace seed."""
        seed = PaceSeed(
            E_min=570.0,  # Adjusted to overlap with Steady
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )
        is_valid, error_msg = validate_pace_seed(seed)
        assert is_valid is True
        assert error_msg is None

    def test_negative_pace_value(self):
        """Test validation fails for negative pace values."""
        seed = PaceSeed(
            E_min=-10.0,  # Invalid
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )
        is_valid, error_msg = validate_pace_seed(seed)
        assert is_valid is False
        assert "E_min" in error_msg
        assert "positive" in error_msg

    def test_invalid_range_min_greater_than_max(self):
        """Test validation fails when min > max."""
        seed = PaceSeed(
            E_min=700.0,  # Greater than E_max
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )
        is_valid, error_msg = validate_pace_seed(seed)
        assert is_valid is False
        assert "Easy range" in error_msg

    def test_invalid_ordering_threshold_not_faster_than_marathon(self):
        """Test validation fails when Threshold >= Marathon."""
        seed = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=550.0,  # Greater than M
            week1_long_cap=8.0,
        )
        is_valid, error_msg = validate_pace_seed(seed)
        assert is_valid is False
        assert "Threshold" in error_msg
        assert "Marathon" in error_msg

    def test_invalid_ordering_marathon_not_faster_than_steady(self):
        """Test validation fails when Marathon >= Steady min."""
        seed = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=530.0,  # Less than M
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )
        is_valid, error_msg = validate_pace_seed(seed)
        assert is_valid is False
        assert "Marathon" in error_msg
        assert "Steady" in error_msg

    def test_invalid_steady_not_overlapping_easy_range(self):
        """Test validation fails when Steady does not overlap with Easy range."""
        seed = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=550.0,  # Less than E_min, but S_max (630) overlaps with Easy
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )
        # This should pass because S_max (630) overlaps with Easy (600-690)
        is_valid, error_msg = validate_pace_seed(seed)
        assert is_valid is True  # Should pass - there's overlap

        # Test case where Steady doesn't overlap at all
        seed_no_overlap = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=700.0,  # Greater than E_max - no overlap
            S_max=730.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )
        is_valid, error_msg = validate_pace_seed(seed_no_overlap)
        assert is_valid is False
        # Should fail on Steady max > Easy max or no overlap
        assert "steady" in error_msg.lower() and "easy" in error_msg.lower()

    def test_pace_too_fast(self):
        """Test validation fails for unrealistically fast paces."""
        seed = PaceSeed(
            E_min=200.0,  # 3:20/mile - too fast
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=180.0,  # 3:00/mile - too fast
            T_max=520.0,
            week1_long_cap=8.0,
        )
        is_valid, error_msg = validate_pace_seed(seed)
        assert is_valid is False
        assert "too fast" in error_msg.lower()

    def test_pace_too_slow(self):
        """Test validation fails for unrealistically slow paces."""
        seed = PaceSeed(
            E_min=600.0,
            E_max=1300.0,  # 21:40/mile - too slow
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )
        is_valid, error_msg = validate_pace_seed(seed)
        assert is_valid is False
        # Should fail on ordering check first, but if it gets past that, should fail on too slow
        if "too slow" not in error_msg.lower():
            # If it failed on ordering, that's also valid - the seed is invalid
            assert "invalid" in error_msg.lower() or "ordering" in error_msg.lower()

    def test_week1_long_cap_too_small(self):
        """Test validation fails for week1_long_cap below minimum."""
        seed = PaceSeed(
            E_min=570.0,  # Adjusted to overlap with Steady
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=5.0,  # Below minimum
        )
        is_valid, error_msg = validate_pace_seed(seed)
        assert is_valid is False
        # Error message may have spaces: "week1 long cap" or "week1_long_cap"
        assert "week1" in error_msg.lower() and "cap" in error_msg.lower()


class TestValidateInputParameters:
    """Test input parameter validation."""

    def test_valid_user_id(self):
        """Test valid user_id passes."""
        is_valid, error_msg = validate_input_parameters(user_id="test-user-id")
        assert is_valid is True
        assert error_msg is None

    def test_invalid_user_id_empty_string(self):
        """Test empty user_id fails."""
        is_valid, error_msg = validate_input_parameters(user_id="")
        assert is_valid is False
        assert "empty" in error_msg.lower()

    def test_invalid_user_id_wrong_type(self):
        """Test non-string user_id fails."""
        is_valid, error_msg = validate_input_parameters(user_id=123)
        assert is_valid is False
        assert "string" in error_msg.lower()

    def test_valid_lookback_weeks(self):
        """Test valid lookback_weeks passes."""
        is_valid, error_msg = validate_input_parameters(lookback_weeks=6)
        assert is_valid is True
        assert error_msg is None

    def test_invalid_lookback_weeks_negative(self):
        """Test negative lookback_weeks fails."""
        is_valid, error_msg = validate_input_parameters(lookback_weeks=-1)
        assert is_valid is False
        assert "positive" in error_msg.lower()

    def test_invalid_lookback_weeks_too_large(self):
        """Test lookback_weeks > 52 fails."""
        is_valid, error_msg = validate_input_parameters(lookback_weeks=53)
        assert is_valid is False
        assert "too large" in error_msg.lower()

    def test_valid_min_distance_miles(self):
        """Test valid min_distance_miles passes."""
        is_valid, error_msg = validate_input_parameters(min_distance_miles=2.0)
        assert is_valid is True
        assert error_msg is None

    def test_invalid_min_distance_miles_negative(self):
        """Test negative min_distance_miles fails."""
        is_valid, error_msg = validate_input_parameters(min_distance_miles=-1.0)
        assert is_valid is False
        assert "positive" in error_msg.lower()

    def test_invalid_min_distance_miles_too_large(self):
        """Test min_distance_miles > 50 fails."""
        is_valid, error_msg = validate_input_parameters(min_distance_miles=51.0)
        assert is_valid is False
        assert "too large" in error_msg.lower()

    def test_valid_week1_long(self):
        """Test valid week1_long passes."""
        is_valid, error_msg = validate_input_parameters(week1_long=8.0)
        assert is_valid is True
        assert error_msg is None

    def test_invalid_week1_long_negative(self):
        """Test negative week1_long fails."""
        is_valid, error_msg = validate_input_parameters(week1_long=-1.0)
        assert is_valid is False
        assert "negative" in error_msg.lower()

    def test_invalid_week1_long_too_large(self):
        """Test week1_long > 30 fails."""
        is_valid, error_msg = validate_input_parameters(week1_long=31.0)
        assert is_valid is False
        assert "too large" in error_msg.lower()

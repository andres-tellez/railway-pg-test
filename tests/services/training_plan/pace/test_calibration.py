"""
Tests for calibration pace zones.
"""

import pytest
from src.services.training_plan.pace import (
    get_calibration_pace_seed,
    validate_pace_seed,
)


class TestCalibration:
    """Test calibration pace seed generation."""

    def test_get_calibration_pace_seed_default(self):
        """Test calibration with default week1_long."""
        seed = get_calibration_pace_seed()
        assert seed is not None
        assert seed.M == 600.0  # 10:00/mile
        assert seed.week1_long_cap == 8.0

        # Validate the seed
        is_valid, error_msg = validate_pace_seed(seed)
        assert is_valid is True, f"Calibration seed failed validation: {error_msg}"

    def test_get_calibration_pace_seed_custom_week1_long(self):
        """Test calibration with custom week1_long."""
        seed = get_calibration_pace_seed(week1_long=12.0)
        assert seed.week1_long_cap == 12.0

        # Validate the seed
        is_valid, error_msg = validate_pace_seed(seed)
        assert is_valid is True, f"Calibration seed failed validation: {error_msg}"

    def test_get_calibration_pace_seed_week1_long_below_minimum(self):
        """Test calibration with week1_long below minimum uses minimum."""
        seed = get_calibration_pace_seed(week1_long=5.0)
        assert seed.week1_long_cap == 8.0  # Minimum enforced

    def test_calibration_pace_ordering(self):
        """Test calibration paces are correctly ordered."""
        seed = get_calibration_pace_seed()

        # Threshold < Marathon < Steady < Easy
        assert seed.T_max < seed.M
        assert seed.M < seed.S_min
        assert seed.E_min <= seed.S_min <= seed.S_max <= seed.E_max

    def test_calibration_pace_values(self):
        """Test calibration uses expected pace values."""
        seed = get_calibration_pace_seed()

        assert seed.M == 600.0  # 10:00/mile
        assert seed.E_min == 630.0  # 10:30/mile (adjusted to overlap with Steady)
        assert seed.E_max == 690.0  # 11:30/mile
        assert seed.S_min == 630.0  # 10:30/mile
        assert seed.S_max == 660.0  # 11:00/mile
        assert seed.T_min == 570.0  # 9:30/mile
        assert seed.T_max == 580.0  # 9:40/mile

    def test_calibration_invalid_week1_long_raises_error(self):
        """Test calibration raises error for invalid week1_long."""
        with pytest.raises(ValueError, match="Invalid week1_long"):
            get_calibration_pace_seed(week1_long=-1.0)

        with pytest.raises(ValueError, match="Invalid week1_long"):
            get_calibration_pace_seed(week1_long=31.0)

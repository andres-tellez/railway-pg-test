"""
Tests for Karvonen Zone Service
"""

import pytest
from src.services.heart_rate.karvonen_zone_service import (
    KarvonenZoneService,
    KarvonenZonesResult,
)


class TestKarvonenZones:
    """Test Karvonen zone calculation."""

    def test_invalid_hrmax_range_raises_valueerror(self):
        """Test that HRmax outside valid range raises ValueError."""
        with pytest.raises(ValueError, match="Invalid HRmax"):
            KarvonenZoneService.calculate_zones(100, 60)  # Too low

        with pytest.raises(ValueError, match="Invalid HRmax"):
            KarvonenZoneService.calculate_zones(250, 60)  # Too high

    def test_invalid_resting_hr_range_raises_valueerror(self):
        """Test that resting HR outside valid range raises ValueError."""
        with pytest.raises(ValueError, match="Invalid resting HR"):
            KarvonenZoneService.calculate_zones(180, 30)  # Too low

        with pytest.raises(ValueError, match="Invalid resting HR"):
            KarvonenZoneService.calculate_zones(180, 120)  # Too high

    def test_resting_hr_too_high_raises_valueerror(self):
        """Test that HRR < 30 raises ValueError."""
        with pytest.raises(ValueError, match="Heart Rate Reserve too small"):
            KarvonenZoneService.calculate_zones(180, 155)  # HRR = 25

    def test_hrmax_less_than_resting_hr_raises_valueerror(self):
        """Test that hrmax <= resting_hr raises ValueError."""
        with pytest.raises(ValueError, match="must be greater than resting HR"):
            KarvonenZoneService.calculate_zones(60, 70)  # Pathological

    def test_valid_zones_calculated_correctly(self):
        """Test that zones are calculated correctly."""
        result = KarvonenZoneService.calculate_zones(180, 60)

        assert result.success is True
        assert result.hrr == 120

        # Z1: 50-60% of 120 + 60 = 60 + 60 to 72 + 60 = 120-132
        assert result.zones["Z1"] == (120.0, 132.0)

        # Z2: 60-70% of 120 + 60 = 72 + 60 to 84 + 60 = 132-144
        assert result.zones["Z2"] == (132.0, 144.0)

        # Z5 upper bound is HRmax
        assert result.zones["Z5"][1] == 180.0

    def test_zones_are_floats(self):
        """Test that zone values are Python floats (not numpy types)."""
        result = KarvonenZoneService.calculate_zones(180, 60)

        assert result.success is True
        # Verify types are Python floats
        assert isinstance(result.zones["Z1"][0], float)
        assert isinstance(result.zones["Z1"][1], float)

    def test_edge_case_minimum_valid_hrmax(self):
        """Test minimum valid HRmax (120)."""
        result = KarvonenZoneService.calculate_zones(120, 50)  # HRR = 70

        assert result.success is True
        assert result.hrr == 70
        # Z1: 50-60% of 70 + 50 = 35 + 50 to 42 + 50 = 85-92
        assert result.zones["Z1"] == (85.0, 92.0)

    def test_edge_case_maximum_valid_hrmax(self):
        """Test maximum valid HRmax (220)."""
        result = KarvonenZoneService.calculate_zones(220, 60)  # HRR = 160

        assert result.success is True
        assert result.hrr == 160
        assert result.zones["Z5"][1] == 220.0

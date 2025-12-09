"""
Tests for pace calculation strategies.
"""

import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from src.services.training_plan.pace import (
    PaceSeed,
    PaceCalculationStrategy,
    PerformanceBasedStrategy,
    CalibrationStrategy,
    DEFAULT_CONFIG,
    PaceConfig,
)


class TestPerformanceBasedStrategy:
    """Test performance-based strategy."""

    def test_strategy_initialization(self):
        """Test strategy can be initialized with default config."""
        strategy = PerformanceBasedStrategy()
        assert strategy.config == DEFAULT_CONFIG

    def test_strategy_initialization_custom_config(self):
        """Test strategy can be initialized with custom config."""
        custom_config = PaceConfig(LOOKBACK_WEEKS=12)
        strategy = PerformanceBasedStrategy(config=custom_config)
        assert strategy.config.LOOKBACK_WEEKS == 12

    def test_strategy_name(self):
        """Test strategy has correct name."""
        strategy = PerformanceBasedStrategy()
        assert strategy.name == "Performance-Based"

    @patch(
        "src.services.training_plan.pace.performance_calculator.calculate_paces_from_performance"
    )
    def test_calculate_success(self, mock_calculate):
        """Test strategy returns result when calculation succeeds."""
        mock_seed = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )
        mock_calculate.return_value = mock_seed

        strategy = PerformanceBasedStrategy()
        session = Mock(spec=Session)
        result = strategy.calculate(session, "test-user-id")

        assert result == mock_seed
        mock_calculate.assert_called_once()

    @patch(
        "src.services.training_plan.pace.performance_calculator.calculate_paces_from_performance"
    )
    def test_calculate_insufficient_data(self, mock_calculate):
        """Test strategy returns None when insufficient data."""
        mock_calculate.return_value = None

        strategy = PerformanceBasedStrategy()
        session = Mock(spec=Session)
        result = strategy.calculate(session, "test-user-id")

        assert result is None

    @patch(
        "src.services.training_plan.pace.performance_calculator.calculate_paces_from_performance"
    )
    def test_calculate_exception_handling(self, mock_calculate):
        """Test strategy handles exceptions gracefully."""
        mock_calculate.side_effect = Exception("Database error")

        strategy = PerformanceBasedStrategy()
        session = Mock(spec=Session)
        result = strategy.calculate(session, "test-user-id")

        assert result is None  # Should return None, not raise


class TestCalibrationStrategy:
    """Test calibration strategy."""

    def test_strategy_initialization(self):
        """Test strategy can be initialized with default config."""
        strategy = CalibrationStrategy()
        assert strategy.config == DEFAULT_CONFIG

    def test_strategy_initialization_custom_config(self):
        """Test strategy can be initialized with custom config."""
        custom_config = PaceConfig(CALIBRATION_MARATHON_PACE=550.0)
        strategy = CalibrationStrategy(config=custom_config)
        assert strategy.config.CALIBRATION_MARATHON_PACE == 550.0

    def test_strategy_name(self):
        """Test strategy has correct name."""
        strategy = CalibrationStrategy()
        assert strategy.name == "Calibration"

    @patch("src.services.training_plan.pace.calibration.get_calibration_pace_seed")
    def test_calculate_success(self, mock_calibrate):
        """Test strategy returns calibration seed."""
        mock_seed = PaceSeed(
            E_min=630.0,
            E_max=690.0,
            S_min=630.0,
            S_max=660.0,
            M=600.0,
            T_min=570.0,
            T_max=580.0,
            week1_long_cap=8.0,
        )
        mock_calibrate.return_value = mock_seed

        strategy = CalibrationStrategy()
        session = Mock(spec=Session)
        result = strategy.calculate(session, "test-user-id")

        assert result == mock_seed
        mock_calibrate.assert_called_once()

    @patch("src.services.training_plan.pace.calibration.get_calibration_pace_seed")
    def test_calculate_exception_raises(self, mock_calibrate):
        """Test strategy raises exception on failure (calibration should always work)."""
        mock_calibrate.side_effect = ValueError("Invalid config")

        strategy = CalibrationStrategy()
        session = Mock(spec=Session)

        with pytest.raises(RuntimeError, match="Calibration strategy failed"):
            strategy.calculate(session, "test-user-id")


class TestStrategyPattern:
    """Test strategy pattern usage."""

    @patch("src.services.training_plan.pace.calculator.DEFAULT_STRATEGIES")
    def test_strategy_chain(self, mock_strategies):
        """Test that strategies are tried in order."""
        from src.services.training_plan.pace.calculator import get_initial_pace_seed

        # Create mock strategies
        strategy1 = Mock(spec=PaceCalculationStrategy)
        strategy1.name = "Strategy1"
        strategy1.calculate.return_value = None  # Fails

        strategy2 = Mock(spec=PaceCalculationStrategy)
        strategy2.name = "Strategy2"
        mock_seed = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )
        strategy2.calculate.return_value = mock_seed  # Succeeds

        mock_strategies.__iter__ = Mock(return_value=iter([strategy1, strategy2]))

        session = Mock(spec=Session)
        result = get_initial_pace_seed(
            session=session, user_id="test-user", strategies=[strategy1, strategy2]
        )

        assert result == mock_seed
        strategy1.calculate.assert_called_once()
        strategy2.calculate.assert_called_once()

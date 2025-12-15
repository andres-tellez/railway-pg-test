"""
Error handling utilities for Coach system.

Provides centralized error handling with severity classification
and appropriate fallback behavior.
"""

import logging
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class CoachError:
    """Structured error representation."""

    error_type: str
    severity: ErrorSeverity
    component: str
    message: str
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CoachErrorHandler:
    """
    Centralized error handler for Coach system.

    Handles errors with appropriate logging, metrics, and fallback behavior.
    """

    @staticmethod
    def handle(
        error: Exception,
        severity: ErrorSeverity,
        component: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        fallback_value: Any = None,
    ) -> Any:
        """
        Handle an error with appropriate logging and fallback.

        Args:
            error: The exception that occurred
            severity: Error severity level
            component: Component where error occurred
            user_id: User ID (if applicable)
            metadata: Additional error metadata
            fallback_value: Value to return if error is handled

        Returns:
            fallback_value if provided, None otherwise
        """
        coach_error = CoachError(
            error_type=type(error).__name__,
            severity=severity,
            component=component,
            message=str(error),
            user_id=user_id,
            metadata=metadata,
        )

        # Log based on severity
        if severity == ErrorSeverity.CRITICAL:
            logger.critical(
                f"CRITICAL error in {component}: {error}",
                extra={
                    "error_type": coach_error.error_type,
                    "component": component,
                    "user_id": user_id,
                    "metadata": metadata,
                },
                exc_info=True,
            )
        elif severity == ErrorSeverity.HIGH:
            logger.error(
                f"HIGH severity error in {component}: {error}",
                extra={
                    "error_type": coach_error.error_type,
                    "component": component,
                    "user_id": user_id,
                    "metadata": metadata,
                },
                exc_info=True,
            )
        elif severity == ErrorSeverity.MEDIUM:
            logger.warning(
                f"MEDIUM severity error in {component}: {error}",
                extra={
                    "error_type": coach_error.error_type,
                    "component": component,
                    "user_id": user_id,
                    "metadata": metadata,
                },
            )
        else:
            logger.info(
                f"{severity.value.upper()} error in {component}: {error}",
                extra={
                    "error_type": coach_error.error_type,
                    "component": component,
                    "user_id": user_id,
                    "metadata": metadata,
                },
            )

        # Emit metrics (if metrics client available)
        try:
            from coach.utils.metrics import metrics

            metrics.increment(
                "coach.error_count",
                tags={
                    "component": component,
                    "error_type": coach_error.error_type,
                    "severity": severity.value,
                },
            )
        except ImportError:
            # Metrics not available yet, skip
            pass

        return fallback_value

    @staticmethod
    def handle_runner_state_builder_error(
        error: Exception, user_id: str
    ) -> Dict[str, Any]:
        """
        Handle RunnerStateBuilder error with minimal fallback state.

        Args:
            error: The exception
            user_id: User ID

        Returns:
            Minimal RunnerState dict
        """
        CoachErrorHandler.handle(
            error=error,
            severity=ErrorSeverity.HIGH,
            component="RunnerStateBuilder",
            user_id=user_id,
        )

        # Return minimal fallback state
        return {
            "version": "1.0.0",
            "runner_state": {
                "phase": "Unknown",
                "week_of_block": 0,
                "race": {"date": None, "distance": None},
                "zones": {},
                "safety": {
                    "hr_data_reliable": False,
                    "pace_data_reliable": False,
                    "reported_injury": False,
                },
            },
        }

    @staticmethod
    def handle_llm_timeout(
        error: Exception, user_id: str, retry_count: int = 0
    ) -> Optional[str]:
        """
        Handle LLM timeout with retry logic.

        Args:
            error: The timeout exception
            user_id: User ID
            retry_count: Number of retries attempted

        Returns:
            None (caller should use fallback response)
        """
        severity = ErrorSeverity.HIGH if retry_count > 0 else ErrorSeverity.MEDIUM

        CoachErrorHandler.handle(
            error=error,
            severity=severity,
            component="LLMClient",
            user_id=user_id,
            metadata={"retry_count": retry_count},
        )

        return None

    @staticmethod
    def handle_context_too_large(
        error: Exception, component: str, context_size: int, max_size: int
    ) -> Dict[str, Any]:
        """
        Handle context size exceeded error with compression.

        Args:
            error: The exception
            component: Component where error occurred
            context_size: Actual context size
            max_size: Maximum allowed size

        Returns:
            Empty dict (caller should compress and retry)
        """
        CoachErrorHandler.handle(
            error=error,
            severity=ErrorSeverity.MEDIUM,
            component=component,
            metadata={"context_size": context_size, "max_size": max_size},
        )

        return {}

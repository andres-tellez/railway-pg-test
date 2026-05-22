"""Typed errors for coach response isolation package."""


class CoachResponseError(Exception):
    """Base class for coach response errors."""


class CoachResponseSkip(CoachResponseError):
    """Raised when a turn should not be served by coach_response."""


class CoachResponseFallback(CoachResponseError):
    """Raised when coach_response attempted handling but must degrade."""

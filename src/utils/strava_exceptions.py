"""
Strava Integration Custom Exceptions
====================================

Custom exception classes for Strava integration to provide better error handling
and more specific error messages.

These exceptions help distinguish between different types of failures:
- API errors (rate limits, authentication, network)
- Token errors (expired, revoked, missing)
- Ingestion errors (sync failures, validation errors)
- Configuration errors (missing settings)
"""


class StravaError(Exception):
    """Base exception for all Strava-related errors."""

    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class StravaAPIError(StravaError):
    """Raised when Strava API returns an error."""

    def __init__(
        self,
        message: str,
        status_code: int = None,
        response_body: str = None,
        details: dict = None,
    ):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message, details)


class StravaRateLimitError(StravaAPIError):
    """Raised when Strava API rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Strava API rate limit exceeded",
        retry_after: int = None,
        details: dict = None,
    ):
        self.retry_after = retry_after
        super().__init__(message, status_code=429, details=details)


class StravaAuthenticationError(StravaAPIError):
    """Raised when Strava API authentication fails."""

    def __init__(
        self, message: str = "Strava API authentication failed", details: dict = None
    ):
        super().__init__(message, status_code=401, details=details)


class StravaTokenError(StravaError):
    """Base exception for token-related errors."""

    pass


class StravaTokenNotFoundError(StravaTokenError):
    """Raised when Strava tokens are not found for an athlete."""

    def __init__(self, athlete_id: int, message: str = None):
        self.athlete_id = athlete_id
        msg = message or f"No tokens found for athlete {athlete_id}"
        super().__init__(msg, details={"athlete_id": athlete_id})


class StravaTokenExpiredError(StravaTokenError):
    """Raised when Strava token has expired and cannot be refreshed."""

    def __init__(self, athlete_id: int, message: str = None):
        self.athlete_id = athlete_id
        msg = (
            message
            or f"Token for athlete {athlete_id} has expired and cannot be refreshed"
        )
        super().__init__(msg, details={"athlete_id": athlete_id})


class StravaTokenRevokedError(StravaTokenError):
    """Raised when Strava token has been revoked."""

    def __init__(self, athlete_id: int, message: str = None):
        self.athlete_id = athlete_id
        msg = message or f"Token for athlete {athlete_id} has been revoked"
        super().__init__(msg, details={"athlete_id": athlete_id})


class StravaTokenRefreshError(StravaTokenError):
    """Raised when token refresh fails."""

    def __init__(self, athlete_id: int, reason: str = None, message: str = None):
        self.athlete_id = athlete_id
        self.reason = reason
        msg = message or f"Failed to refresh token for athlete {athlete_id}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, details={"athlete_id": athlete_id, "reason": reason})


class StravaIngestionError(StravaError):
    """Base exception for ingestion-related errors."""

    pass


class StravaIngestionValidationError(StravaIngestionError):
    """Raised when ingestion parameters are invalid."""

    def __init__(self, message: str, validation_errors: dict = None):
        self.validation_errors = validation_errors or {}
        super().__init__(message, details={"validation_errors": validation_errors})


class StravaIngestionSyncError(StravaIngestionError):
    """Raised when activity sync fails."""

    def __init__(self, athlete_id: int, reason: str = None, message: str = None):
        self.athlete_id = athlete_id
        self.reason = reason
        msg = message or f"Failed to sync activities for athlete {athlete_id}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, details={"athlete_id": athlete_id, "reason": reason})


class StravaIngestionEnrichmentError(StravaIngestionError):
    """Raised when activity enrichment fails."""

    def __init__(
        self,
        activity_id: int = None,
        athlete_id: int = None,
        reason: str = None,
        message: str = None,
    ):
        self.activity_id = activity_id
        self.athlete_id = athlete_id
        self.reason = reason
        msg = message or "Failed to enrich activity"
        if activity_id:
            msg += f" {activity_id}"
        if reason:
            msg += f": {reason}"
        super().__init__(
            msg,
            details={
                "activity_id": activity_id,
                "athlete_id": athlete_id,
                "reason": reason,
            },
        )


class StravaOAuthError(StravaError):
    """Base exception for OAuth-related errors."""

    pass


class StravaOAuthCodeExchangeError(StravaOAuthError):
    """Raised when OAuth code exchange fails."""

    def __init__(self, reason: str = None, message: str = None):
        self.reason = reason
        msg = message or "Failed to exchange OAuth code for tokens"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, details={"reason": reason})


class StravaOAuthStateError(StravaOAuthError):
    """Raised when OAuth state validation fails."""

    def __init__(self, reason: str = None, message: str = None):
        self.reason = reason
        msg = message or "OAuth state validation failed"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, details={"reason": reason})


class StravaConfigurationError(StravaError):
    """Raised when Strava configuration is missing or invalid."""

    def __init__(self, missing_config: str = None, message: str = None):
        self.missing_config = missing_config
        msg = message or "Strava configuration error"
        if missing_config:
            msg += f": Missing or invalid {missing_config}"
        super().__init__(msg, details={"missing_config": missing_config})

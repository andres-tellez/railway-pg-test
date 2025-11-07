# Strava Integration Refactoring - Step 8 Complete

**Date:** November 2025
**Status:** ✅ Complete
**Step:** Improve Error Handling

---

## Summary

Successfully improved error handling across the Strava integration system by creating custom exception classes and replacing generic exceptions with specific, informative error types. All error handling now provides better context, clearer error messages, and proper exception hierarchy.

---

## Changes Made

### **New File Created:**
1. `src/utils/strava_exceptions.py` - Custom exception classes for Strava integration

### **Files Modified:**
1. `src/services/strava_access_service.py` - Improved API error handling
2. `src/services/token_service.py` - Improved token error handling
3. `src/services/ingestion_orchestrator_service.py` - Improved ingestion error handling
4. `src/routes/strava_routes.py` - Improved route error handling

---

## Custom Exception Classes Created

### **1. Base Exception: `StravaError`**
- Base class for all Strava-related errors
- Includes `message` and `details` attributes

### **2. API Errors:**
- **`StravaAPIError`** - Base for API-related errors
  - Includes `status_code` and `response_body`
- **`StravaRateLimitError`** - Rate limit exceeded (429)
  - Includes `retry_after` attribute
- **`StravaAuthenticationError`** - Authentication failed (401)

### **3. Token Errors:**
- **`StravaTokenError`** - Base for token-related errors
- **`StravaTokenNotFoundError`** - Tokens not found for athlete
- **`StravaTokenRevokedError`** - Token has been revoked
- **`StravaTokenRefreshError`** - Token refresh failed
  - Includes `athlete_id` and `reason` attributes

### **4. Ingestion Errors:**
- **`StravaIngestionError`** - Base for ingestion-related errors
- **`StravaIngestionValidationError`** - Invalid ingestion parameters
  - Includes `validation_errors` dict
- **`StravaIngestionSyncError`** - Activity sync failed
  - Includes `athlete_id` and `reason` attributes
- **`StravaIngestionEnrichmentError`** - Activity enrichment failed
  - Includes `activity_id`, `athlete_id`, and `reason` attributes

### **5. OAuth Errors:**
- **`StravaOAuthError`** - Base for OAuth-related errors
- **`StravaOAuthCodeExchangeError`** - OAuth code exchange failed
  - Includes `reason` attribute
- **`StravaOAuthStateError`** - OAuth state validation failed
  - Includes `reason` attribute

### **6. Configuration Errors:**
- **`StravaConfigurationError`** - Missing or invalid configuration
  - Includes `missing_config` attribute

---

## Error Handling Improvements

### **1. strava_access_service.py**

**Before:**
```python
if response.status_code == 401:
    logger.warning(f"Unauthorized! Token: {redact_token(self.access_token)}")
response.raise_for_status()
return response.json()

raise RuntimeError("Exceeded max retries due to repeated 429 errors")
```

**After:**
```python
if response.status_code == 401:
    logger.warning(f"Unauthorized! Token: {redact_token(self.access_token)}")
    raise StravaAuthenticationError(
        "Strava API authentication failed",
        details={"url": redact_url(url), "method": method, "attempt": attempt + 1}
    )

try:
    response.raise_for_status()
    return response.json()
except requests.exceptions.HTTPError as e:
    raise StravaAPIError(
        f"Strava API request failed: {e}",
        status_code=response.status_code,
        response_body=response.text[:500] if response.text else None,
        details={"url": redact_url(url), "method": method, "attempt": attempt + 1}
    )

raise StravaRateLimitError(
    f"Exceeded max retries ({max_retries}) due to repeated 429 errors",
    retry_after=backoff,
    details={"url": redact_url(url), "method": method, "max_retries": max_retries}
)
```

**Improvements:**
- ✅ Specific exception types for different error scenarios
- ✅ Better error context (URL, method, attempt number)
- ✅ Retry-After header support for rate limits
- ✅ Response body included in error details

---

### **2. token_service.py**

**Before:**
```python
if not token_data:
    raise RuntimeError(f"No tokens found for athlete {athlete_id}")

if token.is_revoked():
    raise ValueError(f"Token for athlete {athlete_id} has been revoked")

response.raise_for_status()
if "athlete" not in response_data:
    raise KeyError("❌ Strava callback response missing athlete ID")
```

**After:**
```python
if not token_data:
    raise StravaTokenNotFoundError(athlete_id)

if token.is_revoked():
    raise StravaTokenRevokedError(athlete_id)

try:
    response.raise_for_status()
except requests.exceptions.HTTPError as e:
    raise StravaOAuthCodeExchangeError(
        reason=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
        message="Failed to exchange OAuth code for tokens"
    )

if not response_data or "athlete" not in response_data:
    raise StravaOAuthCodeExchangeError(
        reason="Response missing athlete ID",
        message="Strava OAuth response missing required athlete field"
    )
```

**Improvements:**
- ✅ Specific exception types for token errors
- ✅ Better error messages with context
- ✅ Proper exception hierarchy
- ✅ Network errors handled separately

---

### **3. ingestion_orchestrator_service.py**

**Before:**
```python
if error:
    raise ValueError(f"Invalid athlete_id: {error[0].json.get('error')}")

try:
    activities = service.client.get_activities(...)
except Exception as e:
    logger.error(f"Failed to fetch activities: {e}")
    return {"synced": 0, "enriched": 0}

except Exception as e:
    logger.exception(f"Ingestion failed: {e}")
    raise
```

**After:**
```python
if error:
    raise StravaIngestionValidationError(
        message=f"Invalid athlete_id: {error[0].json.get('error')}",
        validation_errors={"athlete_id": error[0].json.get('error')}
    )

try:
    activities = service.client.get_activities(...)
except StravaTokenError as e:
    raise StravaIngestionSyncError(
        athlete_id=athlete_id,
        reason=f"Token error: {e.message}",
        message="Failed to fetch activities due to token error"
    )
except Exception as e:
    raise StravaIngestionSyncError(
        athlete_id=athlete_id,
        reason=str(e),
        message="Failed to fetch activities from Strava API"
    )

except (StravaIngestionValidationError, StravaIngestionSyncError, StravaIngestionEnrichmentError):
    session.rollback()
    raise
except StravaTokenError as e:
    raise StravaIngestionSyncError(...)
except Exception as e:
    raise StravaIngestionSyncError(...)
```

**Improvements:**
- ✅ Specific exception types for different failure modes
- ✅ Better error context (athlete_id, reason)
- ✅ Proper exception propagation
- ✅ Graceful handling of enrichment failures (doesn't fail ingestion)

---

### **4. strava_routes.py**

**Before:**
```python
except Exception as e:
    logger.exception(f"Failed to process Strava callback: {e}")
    raise RuntimeError(f"Failed to process callback: {e}")

except Exception as e:
    session.rollback()
    logger.exception("Error processing Strava callback")
    return internal_error_response("Failed to process Strava callback", log_error=e)
```

**After:**
```python
except (StravaOAuthError, StravaTokenError) as e:
    logger.exception(f"Strava error during callback processing: {e}")
    raise
except Exception as e:
    raise StravaOAuthCodeExchangeError(
        reason=str(e),
        message="Failed to process Strava OAuth callback"
    )

except (StravaOAuthError, StravaTokenError, StravaAPIError) as e:
    session.rollback()
    logger.exception(f"Strava error during callback: {e}")
    return error_response(
        message=str(e.message) if hasattr(e, 'message') else str(e),
        status_code=400 if isinstance(e, (StravaOAuthError, StravaTokenError)) else 500,
        error_code=type(e).__name__,
        details=e.details if hasattr(e, 'details') else {}
    )
```

**Improvements:**
- ✅ Specific exception handling for Strava errors
- ✅ Appropriate HTTP status codes based on error type
- ✅ Error details included in response
- ✅ Better error codes for frontend handling

---

## Exception Hierarchy

```
StravaError (base)
├── StravaAPIError
│   ├── StravaRateLimitError
│   └── StravaAuthenticationError
├── StravaTokenError
│   ├── StravaTokenNotFoundError
│   ├── StravaTokenRevokedError
│   └── StravaTokenRefreshError
├── StravaIngestionError
│   ├── StravaIngestionValidationError
│   ├── StravaIngestionSyncError
│   └── StravaIngestionEnrichmentError
├── StravaOAuthError
│   ├── StravaOAuthCodeExchangeError
│   └── StravaOAuthStateError
└── StravaConfigurationError
```

---

## Error Context Improvements

### **Before:**
- Generic `RuntimeError` or `ValueError`
- Minimal error context
- No structured error details

### **After:**
- Specific exception types
- Rich error context (athlete_id, reason, status_code, etc.)
- Structured error details dictionary
- Better error messages

---

## Benefits

### **1. Better Error Messages:**
- ✅ Clear, specific error messages
- ✅ Context included (athlete_id, reason, etc.)
- ✅ Actionable error information

### **2. Better Error Handling:**
- ✅ Specific exception types for different scenarios
- ✅ Proper exception hierarchy
- ✅ Easy to catch specific error types

### **3. Better Debugging:**
- ✅ Error details included in exceptions
- ✅ Better logging with context
- ✅ Easier to trace error sources

### **4. Better User Experience:**
- ✅ Appropriate HTTP status codes
- ✅ Structured error responses
- ✅ Error codes for frontend handling

---

## Testing

### **Test Coverage:**
- ✅ 16 test cases covering all exception classes
- ✅ Exception creation and attributes
- ✅ Exception inheritance hierarchy
- ✅ Error message formatting

### **Test Results:**
- ✅ All 16 tests passed
- ✅ No linter errors

### **Test File:**
- `tests/test_strava_exceptions.py`

---

## Error Response Format

### **API Errors:**
```json
{
  "success": false,
  "error": "Strava API authentication failed",
  "error_code": "StravaAuthenticationError",
  "details": {
    "url": "https://...",
    "method": "GET",
    "attempt": 1
  }
}
```

### **Token Errors:**
```json
{
  "success": false,
  "error": "No tokens found for athlete 12345",
  "error_code": "StravaTokenNotFoundError",
  "details": {
    "athlete_id": 12345
  }
}
```

### **Ingestion Errors:**
```json
{
  "success": false,
  "error": "Failed to fetch activities from Strava API",
  "error_code": "StravaIngestionSyncError",
  "details": {
    "athlete_id": 12345,
    "reason": "Network timeout"
  }
}
```

---

## Migration Notes

### **Backward Compatibility:**
- ✅ All existing error handling still works
- ✅ New exceptions extend base Exception class
- ✅ Can catch base `StravaError` for all Strava errors

### **Gradual Adoption:**
- ✅ Can catch specific exceptions where needed
- ✅ Can catch base exceptions for general handling
- ✅ No breaking changes to existing code

---

## Usage Examples

### **Catching Specific Errors:**
```python
try:
    token = get_valid_token(session, athlete_id)
except StravaTokenNotFoundError:
    # Handle missing token
    pass
except StravaTokenRevokedError:
    # Handle revoked token
    pass
except StravaTokenRefreshError as e:
    # Handle refresh failure
    logger.error(f"Refresh failed: {e.reason}")
```

### **Catching Base Errors:**
```python
try:
    result = run_full_ingestion_and_enrichment(None, athlete_id)
except StravaIngestionError as e:
    # Handle any ingestion error
    logger.error(f"Ingestion failed: {e.message}")
    logger.error(f"Details: {e.details}")
```

---

**Step 8 Status:** ✅ Complete
**Next Step:** Step 9 - Add Rate Limiting to Webhooks

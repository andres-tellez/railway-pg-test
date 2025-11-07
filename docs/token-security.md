# Token Security and Secret Redaction

**Status:** ✅ Implemented
**Purpose:** Ensure tokens and secrets are never logged in plain text

---

## Overview

All sensitive information (tokens, secrets, passwords) is automatically redacted in logs to prevent accidental exposure. This includes:

- Access tokens
- Refresh tokens
- Client secrets
- API keys
- Database connection strings (passwords)
- OAuth codes
- Authorization headers

---

## Implementation

### Security Utilities (`src/utils/security_utils.py`)

Provides centralized functions for redacting sensitive data:

#### `redact_token(token)`
Redacts access/refresh tokens:
```
Input:  "abc123def456ghi789jkl012mno345pqr678"
Output: "abc1***pqr6 (length: 40)"
```

#### `redact_secret(secret)`
Redacts client secrets and API keys:
```
Input:  "abc12345def67890"
Output: "abc1****7890"
```

#### `redact_dict(d)`
Redacts sensitive keys from dictionaries:
```python
payload = {
    "client_id": "12345",
    "client_secret": "secret123",
    "code": "auth_code_xyz"
}
redacted = redact_dict(payload)
# {
#     "client_id": "12345",
#     "client_secret": "abc1****7890",
#     "code": "auth***xyz"
# }
```

#### `redact_headers(headers)`
Redacts Authorization and other sensitive headers:
```python
headers = {"Authorization": "Bearer abc123..."}
redacted = redact_headers(headers)
# {"Authorization": "Bearer abc1***xyz"}
```

#### `redact_connection_string(url)`
Redacts passwords from database connection strings:
```
Input:  postgresql://user:password123@host:5432/db
Output: postgresql://user:***REDACTED***@host:5432/db
```

---

## Where It's Used

### Token Service (`src/services/token_service.py`)

**Before:**
```python
print("🔑 Using Strava client_secret:", config.STRAVA_CLIENT_SECRET)
print("🔑 Using code:", code)
print(f"POST data: {payload}")  # Contains secrets!
```

**After:**
```python
logger.info(f"Using Strava client_secret: {redact_secret(config.STRAVA_CLIENT_SECRET)}")
logger.info(f"Using code: {redact_token(code)}")
redacted_payload = redact_dict(payload)
logger.debug(f"POST data: {redacted_payload}")
```

### Strava Client (`src/services/strava_access_service.py`)

**Before:**
```python
headers = {"Authorization": f"Bearer {self.access_token}"}
print(f"Headers: {headers}")  # Exposes token!
```

**After:**
```python
headers = {"Authorization": f"Bearer {self.access_token}"}
redacted_headers = redact_headers(headers)
logger.debug(f"Headers: {redacted_headers}")
```

### Error Logging

**Before:**
```python
if response.status_code == 401:
    print(f"Unauthorized! Token: {self.access_token}")  # Exposes token!
```

**After:**
```python
if response.status_code == 401:
    logger.warning(f"Unauthorized! Token: {redact_token(self.access_token)}")
```

### Database Connection Strings (`src/app.py`)

**Before:**
```python
print(f"DATABASE_URL: {os.getenv('DATABASE_URL')}")  # Contains password!
```

**After:**
```python
print(f"DATABASE_URL: {redact_connection_string(os.getenv('DATABASE_URL'))}")
```

---

## Token Storage

### Database Storage

Tokens are stored in the `tokens` table:
- **Access tokens:** Encrypted at database level (Railway PostgreSQL)
- **Refresh tokens:** Encrypted at database level (Railway PostgreSQL)
- **No plain text storage:** All tokens are encrypted in transit and at rest

### Environment Variables

Secrets are loaded from environment variables:
- **Never committed to git:** All secrets in `.env.*` files (gitignored)
- **Railway secrets:** Stored securely in Railway environment variables
- **No hardcoding:** All secrets come from environment

---

## Best Practices

### ✅ DO

- Use `security_utils` functions for all logging
- Log at appropriate levels (DEBUG for detailed info, INFO for operations)
- Use structured logging (logger.info, logger.debug, logger.error)
- Redact sensitive data before logging

### ❌ DON'T

- Never log tokens/secrets in plain text
- Never use `print()` for sensitive data
- Never commit secrets to git
- Never hardcode secrets in code

---

## Verification

### Check Logs

All logs should show redacted values:
```
[INFO] Using Strava client_secret: abc1****7890
[DEBUG] Headers: {"Authorization": "Bearer abc1***xyz"}
[WARNING] Unauthorized! Token: abc1***xyz (length: 40)
```

### Search for Exposed Secrets

```bash
# Search for potential secret leaks (should return nothing)
grep -r "access_token.*:" src/ --include="*.py" | grep -v "redact"
grep -r "client_secret.*:" src/ --include="*.py" | grep -v "redact"
```

---

## Related Files

- **Security Utilities:** `src/utils/security_utils.py`
- **Token Service:** `src/services/token_service.py`
- **Strava Client:** `src/services/strava_access_service.py`
- **Token DAO:** `src/db/dao/token_dao.py`
- **App Config:** `src/app.py`

---

## Future Enhancements

### Potential Improvements

1. **Log Sanitization Middleware**
   - Automatic redaction in Flask logging middleware
   - Catch-all for any missed locations

2. **Audit Logging**
   - Track token access/refresh events
   - Monitor for suspicious patterns

3. **Token Rotation**
   - Automatic refresh before expiration
   - Proactive token management

---

**Last Updated:** November 3, 2025

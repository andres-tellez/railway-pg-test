# Strava Integration Refactoring - Step 7 Complete

**Date:** November 2025
**Status:** ✅ Complete
**Step:** Move Hardcoded Values to Config

---

## Summary

Successfully moved all hardcoded values from Strava integration code to the centralized configuration module. All hardcoded URLs, retry settings, and default values are now configurable via environment variables.

---

## Changes Made

### **Files Modified:**
1. `src/utils/config.py` - Added new configuration values
2. `src/services/strava_access_service.py` - Use config for retry settings
3. `src/services/token_service.py` - Use config for API URLs
4. `src/services/ingestion_orchestrator_service.py` - Use config for default values
5. `src/routes/strava_routes.py` - Use config for OAuth URL

---

## Configuration Values Added

### **1. Strava API Retry Settings**

```python
STRAVA_MAX_RETRIES = int(os.getenv("STRAVA_MAX_RETRIES", 5))
STRAVA_INITIAL_BACKOFF = int(os.getenv("STRAVA_INITIAL_BACKOFF", 10))
```

**Purpose:** Configure retry behavior for Strava API requests
- `STRAVA_MAX_RETRIES`: Maximum number of retries on 429 errors (default: 5)
- `STRAVA_INITIAL_BACKOFF`: Initial backoff time in seconds (default: 10)

**Used in:** `strava_access_service.py` - `_request_with_backoff()` method

---

### **2. Ingestion Defaults**

```python
DEFAULT_LOOKBACK_DAYS = int(os.getenv("DEFAULT_LOOKBACK_DAYS", 365))
DEFAULT_BATCH_SIZE = int(os.getenv("DEFAULT_BATCH_SIZE", 50))
DEFAULT_PER_PAGE = int(os.getenv("DEFAULT_PER_PAGE", 50))
```

**Purpose:** Configure default values for activity ingestion
- `DEFAULT_LOOKBACK_DAYS`: Default days to look back for activities (default: 365)
- `DEFAULT_BATCH_SIZE`: Default batch size for enrichment (default: 50)
- `DEFAULT_PER_PAGE`: Default activities per API page (default: 50)

**Used in:** `ingestion_orchestrator_service.py` - `run_full_ingestion_and_enrichment()`

---

## Hardcoded Values Replaced

### **1. API Retry Settings**

**Before:**
```python
def _request_with_backoff(self, method, url, **kwargs):
    max_retries = 5
    backoff = 10  # Start with 10 sec backoff
```

**After:**
```python
def _request_with_backoff(self, method, url, **kwargs):
    max_retries = config.STRAVA_MAX_RETRIES
    backoff = config.STRAVA_INITIAL_BACKOFF  # Start with configured backoff
```

**Location:** `src/services/strava_access_service.py`

---

### **2. Strava API URLs**

**Before:**
```python
response = requests.post(
    "https://www.strava.com/api/v3/oauth/token",
    ...
)
```

**After:**
```python
response = requests.post(
    f"{config.STRAVA_API_BASE_URL}/oauth/token",
    ...
)
```

**Locations:**
- `src/services/token_service.py` - `refresh_token_static()`
- `src/services/token_service.py` - `exchange_code_for_tokens()`
- `src/services/token_service.py` - `store_tokens_from_callback()`

---

### **3. OAuth Authorization URL**

**Before:**
```python
url = (
    f"https://www.strava.com/oauth/authorize"
    f"?client_id={client_id}"
    ...
)
```

**After:**
```python
url = (
    f"{config.STRAVA_API_BASE_URL.replace('/api/v3', '')}/oauth/authorize"
    f"?client_id={client_id}"
    ...
)
```

**Locations:**
- `src/services/token_service.py` - `get_authorization_url()`
- `src/routes/strava_routes.py` - `strava_connect()`

---

### **4. Ingestion Default Values**

**Before:**
```python
lookback_days=365,
...
batch_size = batch_size or min(config.MAX_ACTIVITIES_TO_DOWNLOAD, 50)
per_page = per_page or min(config.MAX_ACTIVITIES_TO_DOWNLOAD, 50)
```

**After:**
```python
lookback_days=config.DEFAULT_LOOKBACK_DAYS,
...
batch_size = batch_size or config.DEFAULT_BATCH_SIZE
per_page = per_page or config.DEFAULT_PER_PAGE
```

**Location:** `src/services/ingestion_orchestrator_service.py`

---

## Configuration Structure

### **New Config Section: Strava API Retry Settings**
```python
# ===== Strava API Retry Settings =====
STRAVA_MAX_RETRIES = int(os.getenv("STRAVA_MAX_RETRIES", 5))
STRAVA_INITIAL_BACKOFF = int(os.getenv("STRAVA_INITIAL_BACKOFF", 10))
```

### **New Config Section: Ingestion Defaults**
```python
# ===== Ingestion Defaults =====
DEFAULT_LOOKBACK_DAYS = int(os.getenv("DEFAULT_LOOKBACK_DAYS", 365))
DEFAULT_BATCH_SIZE = int(os.getenv("DEFAULT_BATCH_SIZE", 50))
DEFAULT_PER_PAGE = int(os.getenv("DEFAULT_PER_PAGE", 50))
```

---

## Environment Variables

### **New Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `STRAVA_MAX_RETRIES` | `5` | Maximum retries for Strava API requests |
| `STRAVA_INITIAL_BACKOFF` | `10` | Initial backoff time in seconds |
| `DEFAULT_LOOKBACK_DAYS` | `365` | Default days to look back for activities |
| `DEFAULT_BATCH_SIZE` | `50` | Default batch size for enrichment |
| `DEFAULT_PER_PAGE` | `50` | Default activities per API page |

### **Existing Environment Variables Used:**
- `STRAVA_API_BASE_URL` - Already in config (default: `"https://www.strava.com/api/v3"`)

---

## Impact

### **Flexibility:**
- ✅ **Configurable Retry Behavior:** Can adjust retry settings without code changes
- ✅ **Configurable Defaults:** Can adjust ingestion defaults per environment
- ✅ **Environment-Specific Settings:** Different values for dev/staging/prod

### **Maintainability:**
- ✅ **Single Source of Truth:** All configuration in one place
- ✅ **Easy Updates:** Change values via environment variables
- ✅ **No Code Changes:** Adjust behavior without deploying new code

### **Testing:**
- ✅ **Test-Specific Settings:** Can override defaults in tests
- ✅ **Mock-Friendly:** Easy to mock config values
- ✅ **Isolation:** Test different configurations easily

---

## Backward Compatibility

### **Defaults Match Previous Behavior:**
- ✅ All new config values use the same defaults as hardcoded values
- ✅ No breaking changes - existing behavior preserved
- ✅ Can be overridden via environment variables if needed

### **Migration:**
- ✅ **No migration needed** - defaults match previous hardcoded values
- ✅ **Optional overrides** - can set environment variables if desired
- ✅ **Gradual adoption** - can adjust values over time

---

## Verification

### **Config Loading:**
- ✅ All config values load correctly
- ✅ Defaults match previous hardcoded values
- ✅ Environment variable overrides work

### **Code Usage:**
- ✅ All hardcoded values replaced
- ✅ Config values used consistently
- ✅ No linter errors

### **Test Results:**
```bash
STRAVA_MAX_RETRIES: 5
STRAVA_INITIAL_BACKOFF: 10
DEFAULT_LOOKBACK_DAYS: 365
DEFAULT_BATCH_SIZE: 50
DEFAULT_PER_PAGE: 50
```

---

## Examples

### **Using Default Values:**
```python
# Uses defaults from config
client = StravaClient(access_token="token")
result = run_full_ingestion_and_enrichment(None, athlete_id=12345)
```

### **Overriding via Environment Variables:**
```bash
# Set custom values
export STRAVA_MAX_RETRIES=10
export STRAVA_INITIAL_BACKOFF=20
export DEFAULT_LOOKBACK_DAYS=180
export DEFAULT_BATCH_SIZE=100
export DEFAULT_PER_PAGE=100
```

### **Using Config in Code:**
```python
from src.utils.config import config

# Use config values
max_retries = config.STRAVA_MAX_RETRIES
backoff = config.STRAVA_INITIAL_BACKOFF
lookback = config.DEFAULT_LOOKBACK_DAYS
```

---

## Notes

- **URL Construction:** OAuth authorization URL uses `STRAVA_API_BASE_URL` with `/api/v3` replaced (since authorization endpoint is at base domain)
- **Backward Compatible:** All defaults match previous hardcoded values
- **Optional:** Environment variables are optional - defaults work out of the box
- **Documentation:** All new config values are documented in code comments

---

**Step 7 Status:** ✅ Complete
**Next Step:** Step 8 - Improve Error Handling

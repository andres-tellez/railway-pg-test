# Additional Code Cleanup Analysis

## Summary

Found a few more cleanup opportunities, but most are minor or intentional.

## Issues Found

### 1. ✅ **GitHub Actions Workflow** - Already Fixed
- **`.github/workflows/staging-cron.yml`**: Removed `INTERNAL_API_KEY` reference (line 20)
- **Status**: ✅ **FIXED**

### 2. ⚠️ **`JWT_SECRET_KEY` - Potentially Unused**

**Location**: `src/utils/config.py` line 17
```python
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "unused-secret")
```

**Analysis**:
- ✅ **Not used anywhere** in the codebase
- ✅ Auth0 uses **RS256** (asymmetric, public key) - doesn't need a secret key
- ✅ All JWT validation uses Auth0's public keys (JWKS endpoint)
- ✅ Default value is "unused-secret" (explicitly indicates it's unused)

**Recommendation**:
- **Safe to delete** - Not used, Auth0 doesn't need it
- **OR** Keep it for potential future use (if you ever need HS256 tokens)

### 3. ✅ **`_unused_session` Parameters** - Intentional

**Locations**:
- `src/services/ingestion_orchestrator_service.py` line 29
- `src/routes/admin_routes.py` line 338

**Analysis**:
- ✅ **Intentional** - Parameter name indicates it's unused
- ✅ Function creates its own session internally
- ✅ Kept for API compatibility (function signature consistency)

**Recommendation**: **Keep** - This is intentional design, not dead code

### 4. ✅ **Comment "Deprecated sync route removed"** - Documentation

**Location**: `src/routes/activity_routes.py` line 202
```python
# Deprecated sync route removed - use /api/progress/ingest instead
```

**Analysis**:
- ✅ **Documentation** - Explains why route is missing
- ✅ **Helpful** - Prevents confusion about missing route

**Recommendation**: **Keep** - Useful documentation

### 5. ✅ **`src/utils/auth.py`** - Legacy File?

**Location**: `src/utils/auth.py`

**Analysis**:
- Has `verify_jwt()` and `requires_auth()` functions
- But codebase uses `src/utils/auth0_jwt.py` instead
- May be legacy/unused code

**Recommendation**: **Investigate** - Check if this file is actually used

## Detailed Check Needed

Let me verify if `src/utils/auth.py` is actually used:

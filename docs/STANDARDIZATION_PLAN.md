# Code Standardization Plan

**Date:** November 2025
**Status:** Ready to Execute

---

## 🎯 Goals

1. **Consistent File Naming** - All route files follow `{domain}_routes.py` pattern
2. **Consistent Blueprint Naming** - All blueprints follow `{domain}_bp` pattern
3. **Consistent URL Prefixes** - All prefixes defined in Blueprint, not in app.py
4. **Logical Grouping** - Related routes grouped together
5. **Clear Documentation** - Each file documents its purpose

---

## 📊 Current State Analysis

### ✅ Already Following Standards

**Routes:**
- `activity_routes.py` → `activity_bp` ✅
- `admin_routes.py` → `admin_bp` ✅
- `plan_routes.py` → `plan_bp` ✅
- `conversation_routes.py` → `conversation_bp` ✅
- `health_routes.py` → `health_bp` ✅
- `webhook_routes.py` → `webhook_bp` ✅
- `auth0_routes.py` → `auth0_bp` ✅ (just created)
- `strava_routes.py` → `strava_bp` ✅ (just created)
- `token_routes.py` → `token_bp` ✅ (just created)
- `auth_debug_routes.py` → `auth_debug_bp` ✅ (just created)

### ⚠️ Needs Standardization

**Issues:**

1. **`auth_me_routes.py`**
   - File: `auth_me_routes.py`
   - Blueprint: `auth_me_bp`
   - Issue: Should be part of `user_identity_routes.py`
   - Route: `/me` (GET)
   - Action: Merge into `user_identity_routes.py`

2. **`user_identity_routes.py`**
   - File: `user_identity_routes.py`
   - Blueprint: `identity_bp` ❌ (should be `user_identity_bp`)
   - Issue: Blueprint name doesn't match file name
   - Action: Rename blueprint to `user_identity_bp`

3. **`strava_connection_routes.py`**
   - File: `strava_connection_routes.py`
   - Blueprint: `strava_connection_bp`
   - Issue: Should be merged into `strava_routes.py`
   - Routes: `/api/strava/disconnect`, `/api/strava/connection-status`
   - Action: Merge into `strava_routes.py`

4. **URL Prefix Inconsistencies**
   - Some set in Blueprint: ✅ `auth0_bp`, `strava_bp`, `token_bp`
   - Some set in app.py: ❌ Need to move to Blueprint definitions

---

## 🔧 Standardization Steps

### Step 1: Fix Blueprint Names (Non-Breaking)

**Files to update:**
- `user_identity_routes.py` - Change `identity_bp` → `user_identity_bp`

**Impact:** Low - Only affects internal references

---

### Step 2: Move URL Prefixes to Blueprint Definitions (Non-Breaking)

**Files to update:**
- All route files that have prefixes in `app.py`
- Move to Blueprint definition

**Impact:** Low - No URL changes

---

### Step 3: Merge Duplicate Routes (Breaking)

**3a. Merge `auth_me_routes.py` into `user_identity_routes.py`**
- Move `/me` endpoint to `user_identity_routes.py`
- Update `app.py` to remove `auth_me_bp` registration
- Delete `auth_me_routes.py`

**3b. Merge `strava_connection_routes.py` into `strava_routes.py`**
- Move `/api/strava/disconnect` and `/api/strava/connection-status` to `strava_routes.py`
- Update `app.py` to remove `strava_connection_bp` registration
- Delete `strava_connection_routes.py`

**Impact:** Medium - Requires frontend updates if endpoints change

---

## 📋 Implementation Checklist

### Phase 1: Non-Breaking Changes
- [ ] Step 1: Fix `user_identity_routes.py` blueprint name
- [ ] Step 2: Move URL prefixes to Blueprint definitions
- [ ] Test: Verify all routes still work
- [ ] Document: Update route documentation

### Phase 2: Route Consolidation (Breaking)
- [ ] Step 3a: Merge `auth_me_routes.py` into `user_identity_routes.py`
- [ ] Step 3b: Merge `strava_connection_routes.py` into `strava_routes.py`
- [ ] Update `app.py` registrations
- [ ] Test: Verify all routes still work
- [ ] Update frontend if needed
- [ ] Delete old files

---

## 🎯 Standardized Patterns

### Route File Pattern
```
{domain}_routes.py
```

### Blueprint Pattern
```
{domain}_bp = Blueprint("{domain}", __name__, url_prefix="/{prefix}")
```

### Examples
```python
# ✅ Good
# File: user_profile_routes.py
user_profile_bp = Blueprint("user_profile", __name__, url_prefix="/api/user")

# ✅ Good
# File: metrics_routes.py
metrics_bp = Blueprint("metrics", __name__, url_prefix="/api/metrics")

# ❌ Bad
# File: user_identity_routes.py
identity_bp = Blueprint("identity", __name__)  # Name doesn't match file
```

---

**Status:** Ready for Implementation
**Next:** Start with Phase 1 (non-breaking changes)

# Standardization Progress

**Date:** November 2025
**Status:** In Progress

---

## ✅ Completed

### Step 1: Blueprint Name Standardization
- ✅ Fixed `user_identity_routes.py`: `identity_bp` → `user_identity_bp`
- ✅ Updated `app.py` to use `user_identity_bp`
- ✅ Tested: All routes still work

---

## 🔄 In Progress

### Step 2: URL Prefix Standardization

**Current State:**
- Some prefixes in Blueprint definitions ✅
- Some prefixes in `app.py` ❌

**Files with prefixes in Blueprint:**
- ✅ `auth0_bp` - `/auth`
- ✅ `strava_bp` - `/auth`
- ✅ `token_bp` - `/auth`
- ✅ `auth_debug_bp` - `/auth`
- ✅ `plan_bp` - `/api/plan`
- ✅ `strava_connection_bp` - `/api`
- ✅ `user_identity_bp` - `/api`
- ✅ `user_profile_bp` - `/api`

**Files with prefixes in app.py (need to move):**
- ❌ `admin_bp` - `/admin` (in app.py)
- ❌ `activity_bp` - `/api/activities` (in app.py)
- ❌ `user_data_bp` - `/api` (in app.py)
- ❌ `metrics_bp` - `/api/metrics` (in app.py)
- ❌ `longest_runs_bp` - `/api/longest-runs` (in app.py)
- ❌ `gyr_metrics_bp` - `/api/gyr-metrics` (in app.py)
- ❌ `webhook_bp` - `/webhooks` (in app.py)
- ❌ `conversation_bp` - `/api` (in app.py)

---

## 📋 Pending

### Step 3: Route Consolidation
- [ ] Merge `auth_me_routes.py` into `user_identity_routes.py`
- [ ] Merge `strava_connection_routes.py` into `strava_routes.py`
- [ ] Update frontend if endpoints change
- [ ] Delete old files

---

## 🎯 Standardization Rules Established

1. **File Naming:** `{domain}_routes.py`
2. **Blueprint Naming:** `{domain}_bp` (matches file name)
3. **URL Prefixes:** Always in Blueprint definition, not in `app.py`
4. **Grouping:** Related routes grouped together

---

**Next Step:** Move URL prefixes to Blueprint definitions

# Naming Conventions & Code Organization Standards

**Date:** November 2025
**Status:** Active Standard

---

## 📋 Purpose

This document defines standardized naming conventions for files, modules, blueprints, and code organization to ensure consistency across the codebase.

---

## 🗂️ Directory Structure

### Routes (`src/routes/`)
```
src/routes/
├── {domain}_routes.py      # Main domain routes (e.g., activity_routes.py)
├── {domain}_{subdomain}_routes.py  # Subdomain routes (e.g., auth0_routes.py)
└── __init__.py
```

### Services (`src/services/`)
```
src/services/
├── {domain}_service.py     # Main service (e.g., activity_service.py)
├── {domain}_{function}_service.py  # Specialized service (e.g., token_service.py)
└── {domain}/              # Domain package for complex services
    ├── {function}_service.py
    └── __init__.py
```

### Database (`src/db/`)
```
src/db/
├── models/                 # SQLAlchemy models
│   └── {entity}.py        # Singular entity name (e.g., activity.py, user_profile.py)
├── dao/                    # Data Access Objects
│   └── {entity}_dao.py    # e.g., activity_dao.py, user_profile_dao.py
└── enums/                  # Enum definitions
    └── {domain}_enums.py  # e.g., user_profile_enums.py
```

### Utils (`src/utils/`)
```
src/utils/
└── {function}_utils.py    # e.g., response_utils.py, date_helpers.py
```

---

## 📝 File Naming Conventions

### Routes Files

**Pattern:** `{domain}_routes.py`

**Examples:**
- ✅ `activity_routes.py` - Activity endpoints
- ✅ `plan_routes.py` - Training plan endpoints
- ✅ `metrics_routes.py` - Metrics endpoints
- ✅ `user_profile_routes.py` - User profile endpoints
- ✅ `auth0_routes.py` - Auth0 authentication endpoints
- ✅ `strava_routes.py` - Strava OAuth endpoints
- ✅ `token_routes.py` - Token management endpoints
- ✅ `auth_debug_routes.py` - Auth debug utilities

**For Related Routes (Grouped by Domain):**
- ✅ `auth0_routes.py`, `strava_routes.py`, `token_routes.py` - All auth-related
- ✅ `metrics_routes.py`, `gyr_metrics_routes.py` - Both metrics-related
- ✅ `user_profile_routes.py`, `user_identity_routes.py`, `user_data_routes.py` - All user-related

**Avoid:**
- ❌ `auth_me_routes.py` → Should be `user_identity_routes.py` (already exists, but rename)
- ❌ `strava_connection_routes.py` → Should be `strava_routes.py` (already split, consolidate)

---

### Blueprint Naming

**Pattern:** `{domain}_bp` (matches file name without `_routes`)

**Examples:**
- ✅ `activity_bp` (from `activity_routes.py`)
- ✅ `plan_bp` (from `plan_routes.py`)
- ✅ `auth0_bp` (from `auth0_routes.py`)
- ✅ `strava_bp` (from `strava_routes.py`)
- ✅ `token_bp` (from `token_routes.py`)

**Consistency Rule:**
- Blueprint name = file name without `_routes.py` + `_bp`
- Example: `activity_routes.py` → `activity_bp`

---

### URL Prefix Conventions

**Pattern:** Use Blueprint `url_prefix` parameter consistently

**Standard Prefixes:**
- `/api` - Main API endpoints (user-facing)
- `/auth` - Authentication endpoints
- `/admin` - Admin/debug endpoints
- `/webhooks` - Webhook endpoints
- `/health` - Health check endpoints
- No prefix - Root-level endpoints (e.g., `/health`)

**Examples:**
```python
# ✅ Correct: Prefix in Blueprint definition
plan_bp = Blueprint("plan", __name__, url_prefix="/api/plan")
auth0_bp = Blueprint("auth0", __name__, url_prefix="/auth")
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# ❌ Avoid: Prefix in app.register_blueprint()
app.register_blueprint(plan_bp, url_prefix="/api/plan")  # Don't do this
```

---

## 🔗 Related Files Grouping

### Authentication Domain
**Files:**
- `auth0_routes.py` - Auth0 login
- `strava_routes.py` - Strava OAuth
- `token_routes.py` - Token management
- `auth_debug_routes.py` - Debug utilities
- `auth_routes.py` - Main module (registers others)

**Prefix:** `/auth`

**Blueprint Names:**
- `auth0_bp`, `strava_bp`, `token_bp`, `auth_debug_bp`

---

### User Management Domain
**Files:**
- `user_profile_routes.py` - User profile CRUD
- `user_identity_routes.py` - User identity management
- `user_data_routes.py` - Data export/deletion (GDPR)
- `auth_me_routes.py` - **⚠️ Should be renamed to `user_identity_routes.py`**

**Prefix:** `/api` (for user-facing) or `/api/user` (for user-specific)

**Blueprint Names:**
- `user_profile_bp`, `user_identity_bp`, `user_data_bp`

---

### Metrics Domain
**Files:**
- `metrics_routes.py` - General metrics
- `gyr_metrics_routes.py` - GYR (Green/Yellow/Red) metrics
- `longest_runs_routes.py` - Longest runs analytics

**Prefix:** `/api/metrics` or `/api/gyr-metrics` or `/api/longest-runs`

**Blueprint Names:**
- `metrics_bp`, `gyr_metrics_bp`, `longest_runs_bp`

---

## 📦 Service File Naming

**Pattern:** `{domain}_service.py` or `{function}_service.py`

**Examples:**
- ✅ `activity_service.py` - Activity business logic
- ✅ `token_service.py` - Token management
- ✅ `metrics_service.py` - Metrics calculations
- ✅ `strava_access_service.py` - Strava API client

**For Complex Services (Package):**
```
src/services/training_plan/
├── __init__.py
├── orchestrator_three_pass.py
├── pass1_weeks_selector.py
├── pass2_workout_distribution.py
└── ...
```

---

## 🗄️ Database File Naming

### Models
**Pattern:** `{entity}.py` (singular, lowercase, snake_case)

**Examples:**
- ✅ `activities.py` - Activity model
- ✅ `user_profile.py` - User profile model
- ✅ `plan_workouts.py` - Plan workout model

### DAOs
**Pattern:** `{entity}_dao.py`

**Examples:**
- ✅ `activity_dao.py` - Activity data access
- ✅ `user_profile_dao.py` - User profile data access
- ✅ `plans_dao.py` - Plans data access

---

## 🔧 Utility File Naming

**Pattern:** `{function}_utils.py` or `{function}.py`

**Examples:**
- ✅ `response_utils.py` - Response formatting utilities
- ✅ `date_helpers.py` - Date manipulation helpers
- ✅ `auth0_jwt.py` - Auth0 JWT validation
- ✅ `config.py` - Configuration management

---

## 📋 Current Issues & Recommendations

### Issues Found

1. **Inconsistent Route File Names:**
   - ❌ `auth_me_routes.py` → Should be part of `user_identity_routes.py`
   - ❌ `strava_connection_routes.py` → Should be merged into `strava_routes.py`

2. **Inconsistent Blueprint Names:**
   - ❌ `identity_bp` (in `user_identity_routes.py`) → Should be `user_identity_bp`
   - ❌ `auth_me_bp` → Should be removed/merged

3. **Inconsistent URL Prefixes:**
   - Some set in Blueprint definition
   - Some set in `app.register_blueprint()`
   - **Recommendation:** Always set in Blueprint definition

4. **Inconsistent Grouping:**
   - Auth routes split across multiple files (✅ good)
   - User routes split but not clearly grouped
   - Metrics routes split but not clearly grouped

---

## ✅ Standardization Checklist

### Routes
- [ ] Rename `auth_me_routes.py` → merge into `user_identity_routes.py`
- [ ] Rename `strava_connection_routes.py` → merge into `strava_routes.py`
- [ ] Standardize all blueprint names to match file names
- [ ] Move all URL prefixes to Blueprint definitions
- [ ] Group related routes in documentation

### Services
- [ ] Review service file names for consistency
- [ ] Group related services in documentation

### Database
- [ ] Verify all models use singular names
- [ ] Verify all DAOs match model names

---

## 🎯 Implementation Priority

### High Priority
1. **Standardize Blueprint Names** - Quick win, affects all routes
2. **Standardize URL Prefixes** - Move to Blueprint definitions
3. **Consolidate Duplicate Routes** - Merge `auth_me` and `strava_connection`

### Medium Priority
4. **Document Route Groups** - Create routing documentation
5. **Review Service Naming** - Ensure consistency

### Low Priority
6. **Refactor File Names** - Only if breaking changes are acceptable

---

## 📚 Examples of Good Naming

### ✅ Good Examples

**Routes:**
```python
# File: activity_routes.py
activity_bp = Blueprint("activity", __name__, url_prefix="/api/activities")

# File: plan_routes.py
plan_bp = Blueprint("plan", __name__, url_prefix="/api/plan")

# File: auth0_routes.py
auth0_bp = Blueprint("auth0", __name__, url_prefix="/auth")
```

**Services:**
```python
# File: activity_service.py
class ActivityService:
    ...

# File: token_service.py
class TokenService:
    ...
```

---

## 🔄 Migration Plan

### Phase 1: Blueprint Names (Non-Breaking)
- Update blueprint names to match file names
- Update `app.py` registrations
- Test all routes still work

### Phase 2: URL Prefixes (Non-Breaking)
- Move prefixes to Blueprint definitions
- Remove from `app.register_blueprint()` calls
- Test all routes still work

### Phase 3: Route Consolidation (Breaking)
- Merge `auth_me_routes.py` into `user_identity_routes.py`
- Merge `strava_connection_routes.py` into `strava_routes.py`
- Update frontend to use new endpoints
- Test thoroughly

---

**Status:** Active Standard
**Last Updated:** November 2025

# Next Steps - Standardization & Refactoring

**Date:** November 2025
**Last Updated:** After completing service naming standardization

---

## ✅ Completed Work

### Standardization Phase
1. ✅ Route file naming and organization
2. ✅ Blueprint naming standardization
3. ✅ URL prefix standardization
4. ✅ Route consolidation (merged duplicates)
5. ✅ Module-level docstrings added
6. ✅ Service file naming standardization
7. ✅ Utility file organization

---

## 📋 Next Steps (Prioritized)

### Option 1: Continue Authentication Refactoring (Recommended)

**Why:** This was the original focus and aligns with the architectural analysis recommendations.

**Tasks:**
1. **Remove duplicate JWT utilities** (`auth-refactor-5`)
   - `jwt_utils.py` appears unused (no imports found)
   - Contains `require_auth` (legacy) vs `requires_auth` in `auth0_jwt.py`
   - Contains `decode_token` which delegates to `verify_and_decode`
   - **Action:** Verify it's unused, then remove or consolidate

2. **Improve PostOAuth error handling** (`auth-refactor-7`)
   - Add user-friendly error messages
   - Better error recovery
   - Improved logging

**Impact:** Medium - Improves authentication system quality

---

### Option 2: Create Routing Documentation

**Why:** Helps developers understand the API structure.

**Tasks:**
1. Create comprehensive API endpoint reference
2. Document route groups by domain
3. List all endpoints with methods, auth requirements, examples

**Impact:** Low-Medium - Documentation improvement

---

### Option 3: Legacy File Cleanup

**Why:** Remove unused code to reduce maintenance burden.

**Tasks:**
1. Verify legacy files are truly unused:
   - `athlete_readiness_assessment.py`
   - `training_profile_normalizer.py`
   - `pace_zone_mapper.py`
   - `jwt_utils.py` (if unused)
2. Remove or archive if confirmed unused
3. Update documentation

**Impact:** Low - Code cleanup

---

## 🎯 Recommended Next Step

**Continue with Authentication Refactoring - Step 5: Remove duplicate JWT utilities**

This aligns with:
- ✅ The original plan to proceed "one step at a time with testing"
- ✅ The architectural analysis recommendations
- ✅ The existing TODO list
- ✅ The user's request for systematic improvement

**Steps:**
1. Verify `jwt_utils.py` is not used anywhere
2. Compare functionality with `auth0_jwt.py`
3. Consolidate or remove duplicates
4. Test JWT validation still works
5. Update any imports if needed

---

## 📊 Current Status

**Standardization:** ✅ Complete
- Routes: 100% standardized
- Services: 100% standardized (active files)
- Utilities: Organized correctly

**Authentication Refactoring:** ⏳ In Progress
- Step 1-4: ✅ Complete
- Step 5-8: ⏳ Pending

---

**Recommended Action:** Proceed with Option 1 (Auth Refactoring - Step 5)

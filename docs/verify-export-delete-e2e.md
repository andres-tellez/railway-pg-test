# Verify Export/Delete E2E in Staging

**Status:** ✅ Verification Script Ready
**Purpose:** End-to-end verification of data export and account deletion flows

---

## Overview

This document provides a comprehensive guide for verifying that the export and delete endpoints work correctly in staging/production environments.

---

## Prerequisites

### 1. Test Account Setup

Create a dedicated test account in staging with:
- ✅ Auth0 account created
- ✅ Strava account connected
- ✅ At least 5-10 activities synced
- ✅ User profile completed (onboarding done)
- ✅ At least one training plan created

**Note:** This account will be DELETED during testing, so use a dedicated test account.

### 2. Environment Variables

Set these in your staging environment or `.env.staging`:

```bash
# API Configuration
API_BASE_URL=https://api.smartcoach.dev  # or staging URL
FRONTEND_REDIRECT=https://app.smartcoach.dev  # or staging URL

# Auth0 (for token generation if needed)
AUTH0_DOMAIN=your-domain.auth0.com
AUTH0_CLIENT_ID=your-client-id
AUTH0_CLIENT_SECRET=your-client-secret

# Or provide JWT token directly
AUTH_TOKEN=your-jwt-token-here
```

### 3. Authentication Token

Get a valid JWT token for the test user:

**Option 1: Manual Token (Recommended)**
1. Log in to staging app as test user
2. Open browser DevTools → Network tab
3. Find any API request
4. Copy the `Authorization: Bearer <token>` value
5. Set `AUTH_TOKEN=<token>` environment variable

**Option 2: Auth0 Token (Advanced)**
Use Auth0 Management API or test credentials to generate a token.

---

## Verification Steps

### Step 1: Run Verification Script

```bash
# Load staging environment
source .env.staging  # or export variables manually

# Run verification script
python -m src.scripts.verify_export_delete_e2e
```

### Step 2: Manual Verification Checklist

#### ✅ Export Data Test

1. **Test Export Endpoint**
   ```bash
   curl -X GET "https://api.smartcoach.dev/api/user/export-data" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json"
   ```

2. **Verify Export Response**
   - [ ] Status code is 200
   - [ ] Response is valid JSON
   - [ ] Contains `export_date` field
   - [ ] Contains `user_id` field
   - [ ] Contains `data` object with:
     - [ ] `identity` (email, name, picture)
     - [ ] `profile` (training preferences)
     - [ ] `strava_connections` (athlete IDs)
     - [ ] `activities` (array of activities)
   - [ ] Contains `summary` with counts
   - [ ] Activity count matches actual activities
   - [ ] All activity fields present (activity_id, name, type, start_date, distance, etc.)

3. **Verify Data Completeness**
   - [ ] All synced activities are included
   - [ ] Activity data is accurate (distances, dates match)
   - [ ] Profile data matches user profile
   - [ ] Strava connection info is present

4. **Save Export File**
   ```bash
   # Save response to file for review
   curl ... > export_data.json
   ```

#### ✅ Delete Account Test

**⚠️ WARNING: This will permanently delete the test account!**

1. **Test Delete Endpoint**
   ```bash
   curl -X DELETE "https://api.smartcoach.dev/api/user/delete-account" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json"
   ```

2. **Verify Delete Response**
   - [ ] Status code is 200
   - [ ] Response contains `success: true`
   - [ ] Response contains `deleted` object with:
     - [ ] `activities` count
     - [ ] `plans` count
     - [ ] `athlete_links` count
     - [ ] `tokens` count
     - [ ] `profile` count
     - [ ] `identity` count
   - [ ] Response contains `timestamp`
   - [ ] Deletion counts match expected values

3. **Verify Data Deletion**
   - [ ] Try to access user endpoint: `GET /api/user`
     - [ ] Should return 404 or 401
   - [ ] Try to access activities: `GET /api/activities`
     - [ ] Should return empty array or 404
   - [ ] Verify in database:
     ```sql
     -- Check user_identity deleted
     SELECT * FROM user_identity WHERE user_id = 'test-user-id';
     -- Should return 0 rows

     -- Check activities deleted
     SELECT * FROM activities WHERE user_id = 'test-user-id';
     -- Should return 0 rows

     -- Check plans deleted
     SELECT * FROM plans WHERE user_id = 'test-user-id';
     -- Should return 0 rows

     -- Check tokens deleted
     SELECT * FROM tokens WHERE athlete_id IN (
       SELECT athlete_id FROM user_athletes WHERE user_id = 'test-user-id'
     );
     -- Should return 0 rows

     -- Check athlete links deleted
     SELECT * FROM user_athletes WHERE user_id = 'test-user-id';
     -- Should return 0 rows
     ```

#### ✅ Authentication Requirements Test

1. **Test Without Authentication**
   ```bash
   # Export without token
   curl -X GET "https://api.smartcoach.dev/api/user/export-data"
   # Should return 401

   # Delete without token
   curl -X DELETE "https://api.smartcoach.dev/api/user/delete-account"
   # Should return 401
   ```

2. **Verify Authentication**
   - [ ] Export endpoint returns 401 without token
   - [ ] Delete endpoint returns 401 without token
   - [ ] Invalid token returns 401
   - [ ] Expired token returns 401

#### ✅ Frontend Integration Test

1. **Test Export via UI**
   - [ ] Navigate to `/data-usage` page
   - [ ] Click export link (if available)
   - [ ] Verify JSON download
   - [ ] Verify data is complete

2. **Test Delete via UI**
   - [ ] Navigate to `/data-deletion` page
   - [ ] Click "Delete My Account Permanently"
   - [ ] Confirm deletion
   - [ ] Verify success message shown
   - [ ] Verify logout after deletion
   - [ ] Verify account is deleted

---

## Expected Results

### Export Endpoint

**Success Response (200):**
```json
{
  "export_date": "2025-11-03T12:00:00.000Z",
  "user_id": "uuid-here",
  "data": {
    "identity": {
      "email": "user@example.com",
      "name": "Test User",
      "picture": "https://...",
      "updated_at": "2025-11-03T10:00:00.000Z"
    },
    "profile": {
      "age": 30,
      "fitness_level": "intermediate",
      "training_days": ["monday", "wednesday", "friday"],
      ...
    },
    "strava_connections": [
      {
        "athlete_id": 123456,
        "connected_at": "2025-11-01T10:00:00.000Z"
      }
    ],
    "activities": [
      {
        "activity_id": 789012,
        "name": "Morning Run",
        "type": "Run",
        "start_date": "2025-11-03T06:00:00.000Z",
        "distance": 5000.0,
        "moving_time": 1800,
        "average_speed": 2.78,
        ...
      }
    ]
  },
  "summary": {
    "total_activities": 10,
    "total_strava_connections": 1
  }
}
```

### Delete Endpoint

**Success Response (200):**
```json
{
  "success": true,
  "message": "All your data has been permanently deleted",
  "deleted": {
    "activities": 10,
    "plans": 2,
    "athlete_links": 1,
    "tokens": 1,
    "profile": 1,
    "identity": 1
  },
  "timestamp": "2025-11-03T12:00:00.000Z"
}
```

---

## Troubleshooting

### Export Fails

**Issue:** 401 Unauthorized
- **Solution:** Check token is valid and not expired
- **Solution:** Verify `Authorization: Bearer <token>` header is set

**Issue:** 500 Internal Server Error
- **Solution:** Check database connection
- **Solution:** Check logs for specific error
- **Solution:** Verify user_id exists in database

**Issue:** Missing data in export
- **Solution:** Verify user has completed onboarding
- **Solution:** Verify activities are synced
- **Solution:** Check database for missing data

### Delete Fails

**Issue:** 401 Unauthorized
- **Solution:** Same as export - check token

**Issue:** 500 Internal Server Error
- **Solution:** Check database constraints
- **Solution:** Verify foreign key relationships
- **Solution:** Check for orphaned data

**Issue:** Data not deleted
- **Solution:** Check database directly
- **Solution:** Verify cascade deletes are working
- **Solution:** Check for manual cleanup needed

---

## Verification Checklist

### Pre-Deployment
- [ ] Export endpoint tested locally
- [ ] Delete endpoint tested locally
- [ ] Authentication requirements verified
- [ ] Error handling tested

### Staging Verification
- [ ] Test account created
- [ ] Export endpoint verified
- [ ] Delete endpoint verified
- [ ] Database cleanup verified
- [ ] Frontend integration tested
- [ ] Error cases tested

### Production Readiness
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Monitoring configured
- [ ] Rollback plan ready

---

## Related Files

- **Verification Script:** `src/scripts/verify_export_delete_e2e.py`
- **Export Endpoint:** `src/routes/user_data_routes.py::export_user_data()`
- **Delete Endpoint:** `src/routes/user_data_routes.py::delete_user_account()`
- **Frontend Pages:**
  - `frontend/src/pages/DataDeletion.tsx`
  - `frontend/src/pages/DataUsage.tsx`

---

## Notes

- **Test Account:** Always use a dedicated test account for deletion tests
- **Backup:** Consider backing up test data before deletion tests
- **Monitoring:** Monitor logs during verification for any errors
- **Performance:** Export may take time for users with many activities

---

**Last Updated:** November 3, 2025

# Clean Database Test Plan - End-to-End User Journey

**Date:** November 2025
**Purpose:** Test complete user journey from fresh database

---

## 🎯 What This Test Covers

### ✅ Comprehensive Coverage

**1. Complete User Journey**
- ✅ New user registration
- ✅ Auth0 authentication
- ✅ PostOAuth component execution
- ✅ User identity creation
- ✅ Onboarding flow
- ✅ Strava connection (optional)
- ✅ All database tables populated

**2. Integration Testing**
- ✅ Frontend ↔ Backend communication
- ✅ Database operations
- ✅ API endpoints
- ✅ Authentication flow
- ✅ Data persistence

**3. Edge Cases**
- ✅ First-time user setup
- ✅ Empty database state
- ✅ All foreign key relationships
- ✅ Data consistency

---

## ❌ What This Test DOESN'T Cover

### Error Scenarios (Need Simulation)

**1. PostOAuth Error Handling**
- ❌ Network errors (needs network simulation)
- ❌ Timeout errors (needs delay simulation)
- ❌ Server errors (needs backend error simulation)
- ❌ Authentication errors (401) (needs invalid token)
- ❌ Retry functionality (needs errors to occur)
- ❌ Continue functionality (needs errors to occur)

**2. Error Recovery**
- ❌ Error UI display
- ❌ Retry button functionality
- ❌ Continue button functionality
- ❌ Error message clarity

---

## 📋 Test Plan: Clean Database Flow

### Step 1: Clean Database

**SQL Script:**
```sql
-- Delete all data from all tables (in correct order due to foreign keys)
TRUNCATE TABLE activities CASCADE;
TRUNCATE TABLE splits CASCADE;
TRUNCATE TABLE plans CASCADE;
TRUNCATE TABLE plan_workouts CASCADE;
TRUNCATE TABLE user_athletes CASCADE;
TRUNCATE TABLE tokens CASCADE;
TRUNCATE TABLE user_profile CASCADE;
TRUNCATE TABLE user_identity CASCADE;
TRUNCATE TABLE webhook_events CASCADE;
TRUNCATE TABLE conversations CASCADE;
TRUNCATE TABLE messages CASCADE;

-- Or use a script to delete in correct order
```

**Alternative: Use a script**
```python
# scripts/clean_database.py
from src.db.db_session import get_session
from src.db.models import *

def clean_database():
    session = get_session()
    try:
        # Delete in correct order (respecting foreign keys)
        session.query(Activity).delete()
        session.query(Split).delete()
        session.query(PlanWorkout).delete()
        session.query(Plan).delete()
        session.query(Message).delete()
        session.query(Conversation).delete()
        session.query(WebhookEvent).delete()
        session.query(Token).delete()
        session.query(UserAthleteLink).delete()
        session.query(UserProfile).delete()
        session.query(UserIdentity).delete()
        session.commit()
        print("✅ Database cleaned successfully")
    except Exception as e:
        session.rollback()
        print(f"❌ Error cleaning database: {e}")
    finally:
        session.close()
```

---

### Step 2: Complete User Journey

**Test Flow:**

1. **Login/Authentication**
   - [ ] Navigate to login page
   - [ ] Complete Auth0 login
   - [ ] Verify PostOAuth component executes
   - [ ] Check console for logs:
     - `🔍 PostOAuth mounted →`
     - `🪪 ID token → present`
     - `📡 Posting token to backend:`
     - `📡 /auth/login/callback → 200`

2. **User Identity Creation**
   - [ ] Verify `user_identity` table has new row
   - [ ] Check `sub` field matches Auth0 user ID
   - [ ] Check `user_id` (UUID) is generated
   - [ ] Check `created_at` timestamp

3. **Onboarding**
   - [ ] Navigate to onboarding page
   - [ ] Fill out onboarding form
   - [ ] Submit form
   - [ ] Verify `user_profile` table has new row
   - [ ] Check all profile fields are saved
   - [ ] Verify redirect to home/dashboard

4. **Strava Connection (Optional)**
   - [ ] Navigate to setup page
   - [ ] Connect Strava account
   - [ ] Verify `user_athletes` table has new row
   - [ ] Verify `tokens` table has Strava tokens
   - [ ] Check `athlete_id` matches Strava ID

5. **Activity Sync (If Strava Connected)**
   - [ ] Wait for activity sync
   - [ ] Verify `activities` table has rows
   - [ ] Check activities have proper data
   - [ ] Verify `splits` table has data (if applicable)

6. **Plan Generation (If Onboarded)**
   - [ ] Create a training plan
   - [ ] Verify `plans` table has new row
   - [ ] Verify `plan_workouts` table has rows
   - [ ] Check plan data is complete

---

### Step 3: Verify Database State

**Checklist:**

**Tables to Verify:**
- [ ] `user_identity` - 1 row (your user)
- [ ] `user_profile` - 1 row (if onboarded)
- [ ] `user_athletes` - 1 row (if Strava connected)
- [ ] `tokens` - 1+ rows (Auth0 + Strava if connected)
- [ ] `activities` - 0+ rows (if Strava connected and synced)
- [ ] `splits` - 0+ rows (if activities have splits)
- [ ] `plans` - 0+ rows (if plan created)
- [ ] `plan_workouts` - 0+ rows (if plan created)
- [ ] `conversations` - 0+ rows (if used chat)
- [ ] `messages` - 0+ rows (if used chat)
- [ ] `webhook_events` - 0+ rows (if webhooks received)

**Data Integrity:**
- [ ] All foreign keys are valid
- [ ] UUIDs are properly formatted
- [ ] Timestamps are set correctly
- [ ] No orphaned records
- [ ] Data matches what was entered

---

### Step 4: Test Edge Cases

1. **Multiple Users**
   - [ ] Create second user
   - [ ] Verify data isolation
   - [ ] Verify no conflicts

2. **Re-login**
   - [ ] Logout
   - [ ] Login again
   - [ ] Verify existing data is preserved
   - [ ] Verify no duplicate user_identity rows

3. **Partial Completion**
   - [ ] Login but don't complete onboarding
   - [ ] Verify user_identity exists
   - [ ] Verify user_profile doesn't exist
   - [ ] Complete onboarding later
   - [ ] Verify data is created correctly

---

## 🎯 Recommended Testing Strategy

### Phase 1: Clean Database Test (Your Approach)
**Time:** ~30 minutes
**Purpose:** Verify complete user journey works
**Coverage:**
- ✅ End-to-end functionality
- ✅ Database operations
- ✅ Data integrity
- ✅ User journey completion

### Phase 2: Error Scenario Tests (Additional)
**Time:** ~20 minutes
**Purpose:** Verify error handling
**Coverage:**
- ✅ Network error handling
- ✅ Timeout handling
- ✅ Retry functionality
- ✅ Continue functionality
- ✅ Error UI display

**Combined Approach:**
1. **First:** Clean database test (your approach) - Verify everything works
2. **Then:** Error simulation tests - Verify error handling works

---

## 📊 Test Checklist

### Database Cleanup
- [ ] All tables truncated/deleted
- [ ] Database is completely empty
- [ ] No foreign key violations

### User Journey
- [ ] Login successful
- [ ] PostOAuth executes without errors
- [ ] User identity created
- [ ] Onboarding completes
- [ ] All data saved correctly
- [ ] Navigation works correctly

### Data Verification
- [ ] All expected tables have data
- [ ] Foreign keys are valid
- [ ] UUIDs are properly formatted
- [ ] Timestamps are set
- [ ] No data corruption

### Error Handling (Separate Test)
- [ ] Network errors handled
- [ ] Timeout errors handled
- [ ] Retry button works
- [ ] Continue button works
- [ ] Error messages are clear

---

## ✅ Success Criteria

**Clean Database Test:**
- ✅ Complete user journey works
- ✅ All tables populate correctly
- ✅ No errors in console
- ✅ No database errors
- ✅ Data integrity maintained

**Combined with Error Tests:**
- ✅ Both happy path and error paths work
- ✅ Complete coverage of functionality
- ✅ Confident in production readiness

---

## 🚀 Recommended Approach

**Do Both:**

1. **Clean Database Test (Your Idea)** - Great for:
   - End-to-end verification
   - Data integrity
   - Complete user journey
   - Regression testing

2. **Error Simulation Tests** - Needed for:
   - PostOAuth error handling
   - User experience in error scenarios
   - Retry/continue functionality
   - Error recovery

**Total Time:** ~50 minutes for complete coverage

---

**Your approach is excellent for integration testing! Just add error simulation tests for complete coverage.**

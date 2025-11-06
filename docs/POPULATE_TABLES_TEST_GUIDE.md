# Populate All Tables - Step-by-Step Test Guide

**Date:** November 2025
**Status:** Ready to Execute

---

## 🎯 Goal

Test the complete user journey from empty database to fully populated tables, verifying:
1. All tables populate correctly
2. Data integrity is maintained
3. Foreign keys are valid
4. Complete user journey works end-to-end

---

## 📋 Pre-Test Checklist

- [ ] Database is empty (all tables cleared)
- [ ] Frontend running (`npm run dev` or similar)
- [ ] Backend running (`python run.py` or similar)
- [ ] Browser DevTools open (F12)
- [ ] Console tab open
- [ ] Network tab open

---

## 🚀 Step-by-Step Test Flow

### Step 1: Login & Authentication

**Action:**
1. Navigate to your app (localhost:5173 or staging URL)
2. Click "Login" or navigate to login page
3. Complete Auth0 authentication

**What to Check:**
- [ ] Auth0 login completes successfully
- [ ] Redirects to PostOAuth component
- [ ] Console shows: `🔍 PostOAuth mounted →`
- [ ] Console shows: `🪪 ID token → present`
- [ ] Console shows: `📡 Posting token to backend:`
- [ ] Console shows: `📡 /auth/login/callback → 200`
- [ ] No errors in console

**Expected Database Changes:**
- [ ] `user_identity` table: **1 row created**
  - Check `user_id` (UUID) is generated
  - Check `email`, `name`, `picture` fields populated
  - Check `updated_at` timestamp set

**Verify in Database:**
```sql
SELECT * FROM user_identity;
-- Should show 1 row with your user data
```

---

### Step 2: PostOAuth & User Identity Setup

**Action:**
1. Wait for PostOAuth to complete
2. Should redirect to setup page or onboarding

**What to Check:**
- [ ] PostOAuth completes without errors
- [ ] Console shows successful API calls:
  - `/user/identity` POST → 200
  - `/user` GET → 200
- [ ] Redirects correctly (not to error page)

**Expected Database Changes:**
- [ ] `user_identity` table: Row updated (if needed)
- [ ] `user_auth_providers` table: **1 row created** (may be created automatically)
  - Check `provider_name` = 'auth0'
  - Check `provider_user_id` matches Auth0 sub
  - Check `user_id` matches user_identity.user_id

**Verify in Database:**
```sql
SELECT * FROM user_identity;
SELECT * FROM user_auth_providers;
-- Should show your user data
```

---

### Step 3: Onboarding (User Profile)

**Action:**
1. Navigate to onboarding page (if not already there)
2. Fill out the onboarding form:
   - Physical stats (height, age, etc.)
   - Race details (race name, date, distance, location)
   - Training days
   - Goals/motivation
3. Submit the form

**What to Check:**
- [ ] Form submission successful
- [ ] Console shows: `POST /api/onboarding → 200`
- [ ] Redirects to home/dashboard
- [ ] No errors in console

**Expected Database Changes:**
- [ ] `user_profile` table: **1 row created**
  - Check `user_id` matches user_identity.user_id
  - Check all form fields are saved correctly
  - Check `race_date`, `race_name`, `race_location` populated
  - Check `training_days` array populated
  - Check `created_at` timestamp set

**Verify in Database:**
```sql
SELECT * FROM user_profile;
-- Should show 1 row with your onboarding data
```

---

### Step 4: Strava Connection (Optional but Recommended)

**Action:**
1. Navigate to setup page or Strava connection page
2. Click "Connect Strava" button
3. Complete Strava OAuth flow
4. Authorize the app

**What to Check:**
- [ ] Strava OAuth redirects work
- [ ] Console shows Strava callback processing
- [ ] Success message appears
- [ ] No errors in console

**Expected Database Changes:**
- [ ] `user_athletes` table: **1 row created**
  - Check `user_id` matches user_identity.user_id
  - Check `athlete_id` (Strava athlete ID) populated
  - Check `created_at` timestamp set

- [ ] `tokens` table: **1 row created** (Strava tokens)
  - Check `athlete_id` matches user_athletes.athlete_id
  - Check `access_token` populated
  - Check `refresh_token` populated
  - Check `expires_at` timestamp set

**Verify in Database:**
```sql
SELECT * FROM user_athletes;
SELECT * FROM tokens;
-- Should show Strava connection data
```

---

### Step 5: Activity Sync (If Strava Connected)

**Action:**
1. Wait for activity sync to complete (or trigger manually)
2. Check sync status in UI

**What to Check:**
- [ ] Activities sync successfully
- [ ] Console shows sync progress
- [ ] Activities appear in UI
- [ ] No errors in console

**Expected Database Changes:**
- [ ] `activities` table: **Multiple rows created** (one per run)
  - Check `user_id` matches user_identity.user_id
  - Check `athlete_id` matches user_athletes.athlete_id
  - Check `activity_id` (Strava activity ID) populated
  - Check `name`, `distance`, `duration`, `date` populated
  - Check `created_at` timestamp set

- [ ] `splits` table: **Multiple rows created** (mile splits for activities)
  - Check `activity_id` matches activities.activity_id
  - Check `split_number`, `distance`, `time`, `pace` populated

**Verify in Database:**
```sql
SELECT COUNT(*) FROM activities;
SELECT * FROM activities LIMIT 5;
SELECT COUNT(*) FROM splits;
SELECT * FROM splits LIMIT 10;
-- Should show your activities and splits
```

---

### Step 6: Plan Generation (If Onboarded)

**Action:**
1. Navigate to plan creation page
2. Create a new training plan (or use existing plan feature)
3. Fill out plan details if needed
4. Generate/activate the plan

**What to Check:**
- [ ] Plan creation successful
- [ ] Console shows plan generation
- [ ] Plan appears in UI
- [ ] No errors in console

**Expected Database Changes:**
- [ ] `plans` table: **1+ rows created**
  - Check `user_id` matches user_identity.user_id
  - Check `plan_name`, `race_date`, `race_name` populated
  - Check `race_distance`, `race_location` populated
  - Check `training_days` array populated
  - Check `is_active` flag set
  - Check `created_at` timestamp set

- [ ] `plan_workouts` table: **Multiple rows created** (one per workout)
  - Check `plan_id` matches plans.id
  - Check workout details populated (type, distance, pace, etc.)
  - Check `week_number`, `day_of_week` populated
  - Check `created_at` timestamp set

**Verify in Database:**
```sql
SELECT * FROM plans;
SELECT COUNT(*) FROM plan_workouts;
SELECT * FROM plan_workouts LIMIT 10;
-- Should show your plan and workouts
```

---

### Step 7: Chat/Conversation (Optional)

**Action:**
1. Navigate to chat/conversation page
2. Send a message to the AI
3. Receive a response

**What to Check:**
- [ ] Conversation loads successfully
- [ ] Messages send and receive correctly
- [ ] No errors in console

**Expected Database Changes:**
- [ ] `conversations` table: **1+ rows created**
  - Check `user_id` matches user_identity.user_id
  - Check `title` or `created_at` populated

- [ ] `conversation_messages` table: **Multiple rows created**
  - Check `conversation_id` matches conversations.id
  - Check `role` ('user' or 'assistant')
  - Check `content` populated
  - Check `created_at` timestamp set

**Verify in Database:**
```sql
SELECT * FROM conversations;
SELECT * FROM conversation_messages LIMIT 10;
-- Should show your conversations and messages
```

---

### Step 8: Webhooks (If Strava Connected)

**Action:**
1. Create a new activity in Strava (or wait for webhook)
2. Webhook should be received and processed

**What to Check:**
- [ ] Webhook received (check backend logs)
- [ ] Webhook processed successfully
- [ ] New activity appears in database

**Expected Database Changes:**
- [ ] `webhook_events` table: **1+ rows created**
  - Check `object_type` = 'activity'
  - Check `aspect_type` = 'create'
  - Check `owner_id` matches athlete_id
  - Check `status` = 'COMPLETED' or 'PROCESSING'
  - Check `created_at` timestamp set

**Verify in Database:**
```sql
SELECT * FROM webhook_events ORDER BY created_at DESC LIMIT 10;
-- Should show webhook events
```

---

## ✅ Final Verification Checklist

### Database Tables Status

| Table | Expected Rows | Status | Notes |
|-------|--------------|--------|-------|
| `user_identity` | 1 | [ ] | Your user |
| `user_auth_providers` | 1 | [ ] | Auth0 provider |
| `user_profile` | 1 | [ ] | Onboarding data |
| `user_athletes` | 1 | [ ] | Strava connection |
| `tokens` | 1+ | [ ] | Strava tokens |
| `activities` | 0+ | [ ] | Synced activities |
| `splits` | 0+ | [ ] | Activity splits |
| `plans` | 0+ | [ ] | Training plans |
| `plan_workouts` | 0+ | [ ] | Plan workouts |
| `conversations` | 0+ | [ ] | Chat conversations |
| `conversation_messages` | 0+ | [ ] | Chat messages |
| `webhook_events` | 0+ | [ ] | Webhook events |

### Data Integrity Checks

- [ ] All foreign keys are valid
- [ ] All UUIDs are properly formatted
- [ ] All timestamps are set correctly
- [ ] No orphaned records
- [ ] Data matches what was entered in UI

### Quick SQL Verification

```sql
-- Count rows in each table
SELECT 'user_identity' as table_name, COUNT(*) as count FROM user_identity
UNION ALL
SELECT 'user_auth_providers', COUNT(*) FROM user_auth_providers
UNION ALL
SELECT 'user_profile', COUNT(*) FROM user_profile
UNION ALL
SELECT 'user_athletes', COUNT(*) FROM user_athletes
UNION ALL
SELECT 'tokens', COUNT(*) FROM tokens
UNION ALL
SELECT 'activities', COUNT(*) FROM activities
UNION ALL
SELECT 'splits', COUNT(*) FROM splits
UNION ALL
SELECT 'plans', COUNT(*) FROM plans
UNION ALL
SELECT 'plan_workouts', COUNT(*) FROM plan_workouts
UNION ALL
SELECT 'conversations', COUNT(*) FROM conversations
UNION ALL
SELECT 'conversation_messages', COUNT(*) FROM conversation_messages
UNION ALL
SELECT 'webhook_events', COUNT(*) FROM webhook_events
ORDER BY table_name;
```

---

## 🐛 Troubleshooting

### If PostOAuth Fails:
- Check console for errors
- Verify backend is running
- Check `VITE_BACKEND_URL` is correct
- Verify Auth0 configuration

### If Tables Don't Populate:
- Check backend logs for errors
- Verify database connection
- Check foreign key constraints
- Verify API endpoints are working

### If Data Doesn't Match:
- Check form submission
- Verify API responses
- Check database constraints
- Review console logs

---

## 📝 Test Results Template

```
Test Date: ___________
Tester: ___________
Environment: [ ] Local [ ] Staging

Step 1: Login & Authentication
- [ ] Pass [ ] Fail
- user_identity: [ ] Created
- Notes: _______________________________

Step 2: PostOAuth
- [ ] Pass [ ] Fail
- user_auth_providers: [ ] Created
- Notes: _______________________________

Step 3: Onboarding
- [ ] Pass [ ] Fail
- user_profile: [ ] Created
- Notes: _______________________________

Step 4: Strava Connection
- [ ] Pass [ ] Fail [ ] Skipped
- user_athletes: [ ] Created
- tokens: [ ] Created
- Notes: _______________________________

Step 5: Activity Sync
- [ ] Pass [ ] Fail [ ] Skipped
- activities: [ ] Created (count: _____)
- splits: [ ] Created (count: _____)
- Notes: _______________________________

Step 6: Plan Generation
- [ ] Pass [ ] Fail [ ] Skipped
- plans: [ ] Created (count: _____)
- plan_workouts: [ ] Created (count: _____)
- Notes: _______________________________

Step 7: Chat/Conversation
- [ ] Pass [ ] Fail [ ] Skipped
- conversations: [ ] Created (count: _____)
- conversation_messages: [ ] Created (count: _____)
- Notes: _______________________________

Step 8: Webhooks
- [ ] Pass [ ] Fail [ ] Skipped
- webhook_events: [ ] Created (count: _____)
- Notes: _______________________________

Final Verification:
- [ ] All expected tables populated
- [ ] Data integrity maintained
- [ ] Foreign keys valid
- [ ] No errors in console

Overall Status: [ ] Pass [ ] Fail
Issues Found: _______________________________
```

---

## ✅ Success Criteria

**Test is successful if:**
- ✅ All expected tables have data
- ✅ All foreign keys are valid
- ✅ Data matches what was entered
- ✅ No errors in console
- ✅ Complete user journey works
- ✅ All features function correctly

---

**Ready to start! Follow the steps above and check off each item as you complete it.**

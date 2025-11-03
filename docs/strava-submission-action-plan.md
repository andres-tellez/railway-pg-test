# Strava Production Submission - Action Plan

**Status:** Ready for submission preparation
**Last Updated:** November 3, 2025

---

## 🎯 Overview

You're **95% ready** to submit to Strava! Here's exactly what needs to be done before submission.

---

## ✅ What's Already Complete

All infrastructure is ready:
- ✅ All required endpoints (export, delete, disconnect)
- ✅ All required pages (Privacy, Terms, Data Deletion, Data Usage)
- ✅ Security measures (token redaction, secure storage)
- ✅ Rate limiting and webhook infrastructure
- ✅ OAuth verification tools and scripts
- ✅ Documentation and guides

---

## 📋 Action Items Before Submission

### 1. **Capture Screenshots** ⚠️ REQUIRED

**Priority:** HIGH
**Time:** 15-30 minutes
**Status:** Tools ready, screenshots needed

**What to capture:**
1. **Consent Modal** (before OAuth)
   - Shows privacy policy acceptance
   - Shows terms of service acceptance
   - Shows explicit Strava data consent
   - File: `screenshots/consent-modal.png`

2. **Strava Authorization Page** (during OAuth)
   - Shows SmartCoach requesting access
   - Shows scopes being requested
   - File: `screenshots/strava-authorization.png`

3. **Post-Auth Success** (after OAuth)
   - Shows successful connection
   - Shows user redirected to app
   - File: `screenshots/post-auth-success.png`

**Guide:** See [`docs/screenshot-capture-checklist.md`](./screenshot-capture-checklist.md)

**Steps:**
1. Open staging app: `https://app.smartcoach.dev`
2. Start OAuth flow (connect Strava)
3. Capture each screenshot at the right moment
4. Save to `screenshots/` folder
5. Verify all screenshots are clear and readable

---

### 2. **Verify OAuth Settings in Strava Portal** ⚠️ REQUIRED

**Priority:** HIGH
**Time:** 10-15 minutes
**Status:** Tools ready, verification needed

**What to verify:**
1. Log into Strava Developer Portal: https://www.strava.com/settings/api
2. Verify app settings match:
   - **App Name:** SmartCoach (or your app name)
   - **Website:** https://app.smartcoach.dev
   - **Callback Domain:** api.smartcoach.dev
   - **Category:** Fitness
   - **Description:** Brief description of your app

3. Verify scopes:
   - Check that `read` and `activity:read_all` are selected
   - Verify these match your code

**Tools:**
- Run verification script: `python -m src.scripts.verify_oauth_config.py`
- Use checklist: [`docs/strava-oauth-verification-checklist.md`](./strava-oauth-verification-checklist.md)
- Document results: [`docs/strava-oauth-verification-results.md`](./strava-oauth-verification-results.md)

---

### 3. **Activate Production Webhook** ⚠️ REQUIRED

**Priority:** HIGH
**Time:** 10 minutes
**Status:** Infrastructure ready, activation needed

**Steps:**
1. Deploy latest code to production/staging
2. Set environment variables:
   ```bash
   STRAVA_WEBHOOK_VERIFY_TOKEN=your-secret-token-here
   WEBHOOK_CALLBACK_URL=https://api.smartcoach.dev/webhooks/strava
   ```

3. Register webhook:
   ```bash
   python -m src.scripts.manage_webhook_subscription create
   ```

4. Verify webhook is active:
   ```bash
   python -m src.scripts.manage_webhook_subscription view
   ```

**Guide:** See [`docs/webhook-production-activation.md`](./webhook-production-activation.md)

---

### 4. **Run E2E Verification in Staging** ⚠️ RECOMMENDED

**Priority:** MEDIUM
**Time:** 30 minutes
**Status:** Script ready, execution needed

**Steps:**
1. Create test account in staging
2. Connect Strava and sync activities
3. Run verification script:
   ```bash
   export AUTH_TOKEN=your-jwt-token
   export API_BASE_URL=https://api.smartcoach.dev
   python -m src.scripts.verify_export_delete_e2e
   ```

4. Verify all tests pass:
   - ✅ Export test passes
   - ✅ Delete test passes (deletes test account)
   - ✅ Auth test passes

**Guide:** See [`docs/verify-export-delete-e2e.md`](./verify-export-delete-e2e.md)

---

### 5. **Create Test Accounts Documentation** ⚠️ REQUIRED

**Priority:** HIGH
**Time:** 15-20 minutes
**Status:** Not started

**What to create:**
A document with 2-3 test accounts that Strava reviewers can use to test your app.

**Template:**
```markdown
# Test Accounts for Strava Review

## Test Account 1: Complete User
- **Email:** test-user-1@smartcoach.app
- **Password:** [provide password]
- **Strava:** Connected
- **Activities:** 20+ activities synced
- **Plan:** Active training plan created
- **Steps to test:**
  1. Log in with credentials above
  2. View training plan at /plan/overview
  3. View metrics at /metrics
  4. Test export at /data-usage
  5. Test disconnect at /settings

## Test Account 2: New User
- **Email:** test-user-2@smartcoach.app
- **Password:** [provide password]
- **Strava:** Not connected
- **Steps to test:**
  1. Log in with credentials above
  2. Go through OAuth flow
  3. Complete onboarding
  4. Verify activities sync
```

**Save as:** `docs/test-accounts.md`

---

### 6. **Prepare Submission Package** ⚠️ REQUIRED

**Priority:** HIGH
**Time:** 30-60 minutes
**Status:** Draft ready, finalization needed

**What to prepare:**

1. **Use Case Summary** ✅ (already drafted)
   ```
   SmartCoach generates and adapts training plans for runners
   using their recent activities. Users connect Strava so we
   can compute training insights and adapt future workouts.
   ```

2. **Scope Justification** ✅ (already drafted)
   - See: [`docs/strava-oauth-verification-checklist.md#scope-justification`](./strava-oauth-verification-checklist.md#scope-justification-for-activityread_all)

3. **Links** ✅ (already assembled)
   - Privacy Policy: https://app.smartcoach.dev/privacy-policy
   - Terms of Service: https://app.smartcoach.dev/terms-of-service
   - Data Deletion: https://app.smartcoach.dev/data-deletion
   - Homepage: https://app.smartcoach.dev
   - API: https://api.smartcoach.dev

4. **Rate Limit Request** ✅ (already drafted)
   - See checklist for details

5. **Screenshots** ⚠️ (need to capture)
   - Consent modal
   - Authorization page
   - Post-auth success

6. **Test Accounts** ⚠️ (need to create documentation)

---

## 🚀 Submission Process

### Step 1: Complete All Action Items Above

Check off each item:
- [ ] Screenshots captured
- [ ] OAuth settings verified
- [ ] Webhook activated
- [ ] E2E verification run (recommended)
- [ ] Test accounts documented

### Step 2: Final Review

Review all links:
- [ ] Privacy Policy accessible
- [ ] Terms of Service accessible
- [ ] Data Deletion page accessible
- [ ] Data Usage page accessible
- [ ] Homepage loads correctly
- [ ] API endpoints respond

### Step 3: Submit to Strava

1. Go to: https://www.strava.com/settings/api
2. Click "Request Production Access" (or similar button)
3. Fill out the form with:
   - Use case summary
   - Scope justification
   - All required links
   - Screenshots (upload as attachments)
   - Test account credentials
   - Rate limit estimate and request

4. Submit the request

### Step 4: Monitor Submission

- Strava typically reviews within 1-2 weeks
- They may ask for clarification
- Respond promptly to any questions

---

## 📝 Submission Form Fields (Expected)

Based on Strava's typical requirements:

**Required Fields:**
- App name
- Website URL
- Privacy Policy URL
- Terms of Service URL
- Data Deletion URL
- Use case description
- Scope justification
- Screenshots (3-5)
- Test accounts (2-3)
- Rate limit estimate

**Optional but Helpful:**
- Support email
- Data retention policy
- Security measures
- Webhook usage explanation

---

## ⚠️ Common Issues & Solutions

### Issue: Screenshots Rejected
**Solution:**
- Ensure screenshots show full consent flow
- Include URL bar in screenshots
- Make sure text is readable
- Use PNG format (not JPG)

### Issue: Scope Justification Questioned
**Solution:**
- Reference the detailed justification in your docs
- Explain why `activity:read_all` is needed (private activities)
- Show how you minimize data access

### Issue: Test Accounts Don't Work
**Solution:**
- Create fresh test accounts specifically for review
- Ensure accounts have real Strava data
- Test accounts yourself before providing
- Document exact steps to reproduce

---

## 📚 Reference Documents

- **Process Guide:** [`strava-production-process-guide.md`](./strava-production-process-guide.md)
- **OAuth Verification:** [`strava-oauth-verification-checklist.md`](./strava-oauth-verification-checklist.md)
- **Screenshot Guide:** [`screenshot-capture-checklist.md`](./screenshot-capture-checklist.md)
- **Webhook Activation:** [`webhook-production-activation.md`](./webhook-production-activation.md)
- **E2E Verification:** [`verify-export-delete-e2e.md`](./verify-export-delete-e2e.md)

---

## 🎯 Estimated Time to Complete

**Minimum (Essential):**
- Screenshots: 15 min
- OAuth verification: 10 min
- Webhook activation: 10 min
- Test accounts: 15 min
- **Total: ~50 minutes**

**Recommended (Thorough):**
- Add E2E verification: +30 min
- Add detailed documentation: +30 min
- **Total: ~1.5-2 hours**

---

## ✅ Success Criteria

You're ready to submit when:
1. ✅ All 3 screenshots captured
2. ✅ OAuth settings verified in Strava portal
3. ✅ Webhook subscription active
4. ✅ Test accounts documented and tested
5. ✅ All links verified and accessible
6. ✅ Submission form filled out completely

---

**Next Steps:** Start with screenshots (easiest), then work through the list in order.

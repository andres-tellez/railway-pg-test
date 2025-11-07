# Strava Production Approval Process - Complete Guide

## 📋 Quick Reference

**Main Checklist:** [`docs/strava-production-readiness.md`](./strava-production-readiness.md)
- This is your master checklist - everything you need to do is here
- Check off items as you complete them
- Also update the GitHub issue: https://github.com/andres-tellez/railway-pg-test/issues/51

## 🎯 The Process (Step-by-Step)

### Phase 1: Preparation (Current Phase)

1. **Complete Policies & Pages**
   - ✅ Privacy Policy: https://app.smartcoach.dev/privacy-policy
   - ✅ Terms of Service: https://app.smartcoach.dev/terms-of-service
   - ✅ Data Deletion: https://app.smartcoach.dev/data-deletion
   - ⏳ Data Usage page (optional but recommended)

2. **Verify OAuth Settings**
   - Run: `python src/scripts/verify_oauth_config.py`
   - Follow: [`docs/strava-oauth-verification-checklist.md`](./strava-oauth-verification-checklist.md)
   - Go to: https://www.strava.com/settings/api
   - Verify: App name, website, callback domain, description, scopes

3. **Capture Screenshots**
   - Follow: [`STRAVA_SCREENSHOT_GUIDE.md`](../STRAVA_SCREENSHOT_GUIDE.md)
   - Capture: Consent modal, Strava authorization page, post-auth success
   - Save: Screenshots for submission

### Phase 2: Implementation (Security & Rate Limits)

4. **Security & Compliance**
   - Secure token storage
   - Add "Disconnect Strava" UI
   - Test export/delete flows in staging

5. **Rate Limits & Webhooks**
   - Implement 429 backoff
   - Queue per-athlete syncs
   - Activate production webhook subscription

### Phase 3: Submission

6. **Prepare Submission Package**
   - Draft use case summary
   - Write scope justification (see checklist)
   - Assemble all links (Privacy, Terms, Deletion, Homepage, API)
   - Prepare 2-3 test accounts

7. **Submit to Strava**
   - Go to: Strava Developer Portal
   - Fill out: Production request form
   - Attach: Screenshots
   - Provide: Use case, scope justification, links
   - Submit: Wait for review

## 📁 Where Everything Lives

### Main Documentation
- **Master Checklist:** `docs/strava-production-readiness.md`
  - What: Complete task list with status
  - When: Check before starting, update as you complete items

- **OAuth Verification Checklist:** `docs/strava-oauth-verification-checklist.md`
  - What: Step-by-step guide to verify app settings
  - When: Before submitting to Strava

- **Screenshot Guide:** `STRAVA_SCREENSHOT_GUIDE.md` (root)
  - What: Instructions for capturing required screenshots
  - When: Before submitting to Strava

### Tools/Scripts
- **Verification Script:** `src/scripts/verify_oauth_config.py`
  - What: Automated check of OAuth configuration
  - When: After changing OAuth settings, before submission
  - Run: `python src/scripts/verify_oauth_config.py`

### External Resources
- **GitHub Issue:** https://github.com/andres-tellez/railway-pg-test/issues/51
  - What: Task tracking with checkboxes
  - When: Update as you complete items

- **Strava Developer Portal:** https://www.strava.com/settings/api
  - What: Where you configure app settings
  - When: During OAuth verification phase

## 🔄 Workflow Example

**Scenario: "I need to submit to Strava for production approval"**

```
1. Open: docs/strava-production-readiness.md
   → See what's done ✅ and what's left ⏳

2. Run: python src/scripts/verify_oauth_config.py
   → Verify OAuth config is correct

3. Open: docs/strava-oauth-verification-checklist.md
   → Follow checklist to verify in Strava portal

4. Open: STRAVA_SCREENSHOT_GUIDE.md
   → Capture all required screenshots

5. Complete remaining items in main checklist
   → Security, rate limits, etc.

6. Prepare submission package
   → Use draft text from main checklist

7. Submit to Strava
   → Fill out form, upload screenshots, wait for approval

8. Update GitHub issue
   → Mark items complete
```

## 🎯 How to Remember This

### Option 1: Bookmark These Files
- `docs/strava-production-readiness.md` - Main checklist
- `docs/strava-production-process-guide.md` - This file (overview)

### Option 2: Start Here
When you need to work on Strava production approval:
1. Open `docs/strava-production-readiness.md` (main checklist)
2. See what needs to be done
3. Follow links to detailed guides
4. Update checklist as you go

### Option 3: GitHub Issue
- Bookmark: https://github.com/andres-tellez/railway-pg-test/issues/51
- This has the checklist with checkboxes
- Update it as you complete items

## 📝 Key Points to Remember

1. **Main Checklist is the Source of Truth**
   - `docs/strava-production-readiness.md` has everything
   - Links to other docs from there

2. **Verification Script is for Quick Checks**
   - Run it to verify OAuth config
   - Doesn't replace manual verification in Strava portal

3. **Checklist is for Manual Verification**
   - Use it when verifying settings in Strava portal
   - Helps ensure nothing is missed

4. **Screenshots are Required**
   - Strava requires screenshots in submission
   - Follow the screenshot guide

5. **One-Time Process**
   - This is for initial production approval
   - After approval, you won't need this regularly
   - Keep docs for reference if settings change later

## 🔗 Quick Links

- **Main Checklist:** [`strava-production-readiness.md`](./strava-production-readiness.md)
- **OAuth Checklist:** [`strava-oauth-verification-checklist.md`](./strava-oauth-verification-checklist.md)
- **Screenshot Guide:** [`../STRAVA_SCREENSHOT_GUIDE.md`](../STRAVA_SCREENSHOT_GUIDE.md)
- **Verification Script:** [`../src/scripts/verify_oauth_config.py`](../src/scripts/verify_oauth_config.py)
- **GitHub Issue:** https://github.com/andres-tellez/railway-pg-test/issues/51
- **Strava Portal:** https://www.strava.com/settings/api

## 💡 Tips

- **Start with the main checklist** - it has everything
- **Update as you go** - check off items as you complete them
- **Run the script first** - catches configuration issues early
- **Follow the checklists** - they prevent missing steps
- **Save screenshots** - you'll need them for submission

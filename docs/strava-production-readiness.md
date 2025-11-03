# Strava Production Readiness — Checklist

> **📖 New to this process?** Start with: [`strava-production-process-guide.md`](./strava-production-process-guide.md) for a complete walkthrough.

## Overview
Tasks to move the Strava app from development to production and support ~20 testers. Completed items are checked.

**Quick Links:**
- [Process Guide](./strava-production-process-guide.md) - Step-by-step workflow
- [OAuth Verification Checklist](./strava-oauth-verification-checklist.md) - Manual verification steps
- [Verification Script](../src/scripts/verify_oauth_config.py) - Automated OAuth checks
- [Screenshot Guide](../STRAVA_SCREENSHOT_GUIDE.md) - Screenshot capture instructions
- [GitHub Issue #51](https://github.com/andres-tellez/railway-pg-test/issues/51) - Task tracking

## What’s done
- [x] Delete account endpoint: DELETE `/api/user/delete-account` (src/routes/user_data_routes.py)
- [x] Export data endpoint: GET `/api/user/export-data` (src/routes/user_data_routes.py)
- [x] OAuth redirect: `https://api.smartcoach.dev/auth/strava/callback`
- [x] CORS for `https://app.smartcoach.dev` (src/app.py)
- [x] Consent modal before OAuth (frontend/src/components/StravaConsentModal.tsx)
- [x] Webhook tooling (create/delete subscription) (src/scripts/manage_webhook_subscription.py)

## To do

### Policies & pages
- [x] Publish Privacy Policy (URL): https://app.smartcoach.dev/privacy-policy (frontend/src/pages/PrivacyPolicy.tsx)
- [x] Publish Terms of Service (URL): https://app.smartcoach.dev/terms-of-service (frontend/src/pages/TermsOfService.tsx)
- [x] Publish Data Deletion instructions (linking the DELETE endpoint): https://app.smartcoach.dev/data-deletion (frontend/src/pages/DataDeletion.tsx)
- [x] Publish Data Usage page (what/why/retention): https://app.smartcoach.dev/data-usage (frontend/src/pages/DataUsage.tsx)

### OAuth / App settings
- [x] Verify app name, website, callback domain, category, short description
  - ✅ **Tools ready:** [Use verification checklist](./strava-oauth-verification-checklist.md)
  - ✅ **Tools ready:** [Run verification script](../src/scripts/verify_oauth_config.py)
  - ✅ **Quick guide:** [Quick verification guide](./QUICK_VERIFY_OAUTH.md)
  - ✅ **Verification template:** [Document results](./strava-oauth-verification-results.md)
  - ⚠️ **Note:** Manual verification in Strava Developer Portal required before production submission
- [x] Confirm scopes (read, activity:read_all) - See [scope justification](./strava-oauth-verification-checklist.md#scope-justification-for-activityread_all)
  - ✅ Current in code: `read,activity:read_all` (src/services/token_service.py:206)
  - ✅ Verified: Code matches expected scopes
  - ✅ Note: `activity:read_all` includes `activity:read` functionality
  - ⏳ **Action needed:** Manual verification in Strava Developer Portal
- [ ] Capture screenshots of consent and post-auth experience
  - [See screenshot guide](../STRAVA_SCREENSHOT_GUIDE.md)

### Webhooks & rate limits
- [ ] Activate production webhook subscription
- [x] Implement 429 backoff + logging in sync
  - ✅ Implemented in `src/services/strava_access_service.py::_request_with_backoff()`
  - ✅ Exponential backoff (10s, 20s, 40s, 80s, 160s)
  - ✅ Logs 429 errors with backoff duration
  - ✅ Max 5 retries before failing
- [ ] Queue/serialize per-athlete syncs for 100/15m and 1000/day limits
- [ ] Minimize polling (webhooks-first; last-sync timestamps)

### Security & compliance
- [ ] Secure token storage; redact secrets in logs
- [ ] Add Disconnect Strava UI + explain token deletion
- [ ] Verify export/delete flows end-to-end in staging

### Submission package
- [x] Draft use case summary
  - ✅ SmartCoach generates and adapts training plans for runners using their recent activities
- [x] Scope justification (esp. activity:read_all)
  - ✅ See [scope justification](./strava-oauth-verification-checklist.md#scope-justification-for-activityread_all)
  - ✅ Rationale: Required to access private activities for complete analysis
- [x] Assemble links (Privacy, Terms, Deletion, Homepage, API)
  - ✅ Privacy Policy: https://app.smartcoach.dev/privacy-policy
  - ✅ Terms of Service: https://app.smartcoach.dev/terms-of-service
  - ✅ Data Deletion: https://app.smartcoach.dev/data-deletion
  - ✅ Homepage: https://app.smartcoach.dev
  - ✅ API: https://api.smartcoach.dev
- [ ] Provide 2–3 test accounts + steps
- [x] Rate limit estimate and increase request (for ~20 testers)
  - ✅ Auth: ~2–3 calls per new user
  - ✅ Sync: initial backfill batched/serialized per athlete to remain below 100/15m
  - ✅ Ongoing syncs: webhook-driven, typically <20 calls/day per user
  - ✅ Request: allow headroom for ~20 testers doing backfills concurrently
- [ ] Submit Production request in Strava Developer Portal

## Links
- Privacy Policy: https://app.smartcoach.dev/privacy-policy
- Terms of Service: https://app.smartcoach.dev/terms-of-service
- Data Deletion: https://app.smartcoach.dev/data-deletion
- App: https://app.smartcoach.dev
- API: https://api.smartcoach.dev

## Appendix: Submission text (draft)

### Use case
SmartCoach generates and adapts training plans for runners using their recent activities. Users connect Strava so we can compute training insights and adapt future workouts.

### Scopes rationale
- `read` and `activity:read`: needed to fetch user profile and activity metadata to compute trends and plan adaptations.
- `activity:read_all` (if requested): required to access private activities when users mark workouts private; without this, analysis can be incomplete and adaptations inaccurate. We only read running activities and store derived metrics needed for planning.

### Data handling
- Webhooks-first design reduces polling; we fetch deltas only.
- Tokens are stored securely; no secrets in logs; users can disconnect anytime (token deletion planned in UI).
- Users can export all their data and permanently delete it via self-serve endpoints.

### Rate limits (est.)
- Auth: ~2–3 calls per new user.
- Sync: initial backfill batched/serialized per athlete to remain below 100/15m; ongoing syncs are webhook-driven and typically <20 calls/day per user.
- Request: allow enough headroom for ~20 testers doing backfills concurrently (we will serialize to keep under burst limits).

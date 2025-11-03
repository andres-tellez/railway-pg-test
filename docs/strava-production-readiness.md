# Strava Production Readiness — Checklist

## Overview
Tasks to move the Strava app from development to production and support ~20 testers. Completed items are checked.

## What’s done
- [x] Delete account endpoint: DELETE `/api/user/delete-account` (src/routes/user_data_routes.py)
- [x] Export data endpoint: GET `/api/user/export-data` (src/routes/user_data_routes.py)
- [x] OAuth redirect: `https://api.smartcoach.dev/auth/strava/callback`
- [x] CORS for `https://app.smartcoach.dev` (src/app.py)
- [x] Consent modal before OAuth (frontend/src/components/StravaConsentModal.tsx)
- [x] Webhook tooling (create/delete subscription) (src/scripts/manage_webhook_subscription.py)

## To do

### Policies & pages
- [ ] Publish Privacy Policy (URL)
- [ ] Publish Terms of Service (URL)
- [ ] Publish Data Deletion instructions (linking the DELETE endpoint)
- [ ] Publish Data Usage page (what/why/retention)

### OAuth / App settings
- [ ] Verify app name, website, callback domain, category, short description
- [ ] Confirm scopes (read, activity:read, activity:read_all if justified)
- [ ] Capture screenshots of consent and post-auth experience

### Webhooks & rate limits
- [ ] Activate production webhook subscription
- [ ] Implement 429 backoff + logging in sync
- [ ] Queue/serialize per-athlete syncs for 100/15m and 1000/day limits
- [ ] Minimize polling (webhooks-first; last-sync timestamps)

### Security & compliance
- [ ] Secure token storage; redact secrets in logs
- [ ] Add Disconnect Strava UI + explain token deletion
- [ ] Verify export/delete flows end-to-end in staging

### Submission package
- [ ] Draft use case summary
- [ ] Scope justification (esp. activity:read_all)
- [ ] Assemble links (Privacy, Terms, Deletion, Homepage, API)
- [ ] Provide 2–3 test accounts + steps
- [ ] Rate limit estimate and increase request (for ~20 testers)
- [ ] Submit Production request in Strava Developer Portal

## Links
- Privacy Policy: <TBD>
- Terms of Service: <TBD>
- Data Deletion: <TBD>
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

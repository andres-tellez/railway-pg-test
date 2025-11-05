# Environment Variable Comparison: Staging vs Local

## Analysis Summary

Based on the staging environment variables list (39 vars) and your `.env.local`:

### ✅ **Variables that SHOULD be in `.env.local` (Core Functionality)**

These are required for local development:

1. **DATABASE_URL** - ✅ Required
2. **AUTH0_DOMAIN** - ✅ Required
3. **AUTH0_AUDIENCE** - ✅ Required
4. **AUTH0_ISSUER** - ✅ Required
5. **AUTH0_ALGORITHMS** - ✅ Optional (defaults to RS256)
6. **STRAVA_CLIENT_ID** - ✅ Required
7. **STRAVA_CLIENT_SECRET** - ✅ Required
8. **STRAVA_REDIRECT_URI** - ✅ Required (but different value: `http://localhost:5000/auth/callback`)
9. **OPENAI_API_KEY** - ✅ Required
10. **OPENAI_MODEL** - ✅ Required
11. **OPENAI_TRAINING_PLAN_MODEL** - ✅ Required
12. **CRON_SECRET_KEY** - ❌ **NOT NEEDED** (Legacy - removed)
13. **INTERNAL_API_KEY** - ❌ **NOT NEEDED** (Legacy - removed)
14. **CORS_ORIGINS** - ✅ Required (but different value: `https://localhost:5173,https://app.smartcoach.dev`)
15. **MIN_ACTIVITIES_REQUIRED** - ✅ Required
16. **MAX_ACTIVITIES_TO_DOWNLOAD** - ✅ Required
17. **ACCESS_TOKEN_EXP** - ✅ Optional (has default)
18. **VITE_BACKEND_URL** - ✅ Required (frontend variable, but backend uses it via config)

### ❌ **Variables that should NOT be in `.env.local` (Staging/Production Only)**

These are staging/production-specific:

1. **FLASK_ENV** - ❌ Not needed (auto-set to "local" when `.env.local` exists)
2. **FRONTEND_REDIRECT** - ❌ Optional for local (only needed for OAuth redirects in staging/prod)
3. **SESSION_COOKIE_DOMAIN** - ❌ Not needed (local dev doesn't need cross-domain cookies)
4. **SESSION_COOKIE_SECURE** - ❌ Not needed
5. **SESSION_COOKIE_SAMESITE** - ❌ Not needed
6. **SMTP_*** (all SMTP vars)** - ❌ Optional for local (email not needed for local dev)
7. **STRAVA_WEBHOOK_VERIFY_TOKEN** - ❌ Not needed (webhooks don't work locally)
8. **WEBHOOK_CALLBACK_URL** - ❌ Not needed (webhooks don't work locally)
9. ~~**ALERT_WEBHOOK_URL**~~ - ❌ **DELETED** (legacy - replaced by `/webhooks/strava/status` endpoint)
10. **ENABLE_WEEKLY_TASKS** - ❌ Deleted (code removed, manual trigger no longer available)
11. **RUN_CRON** - ❌ Optional (cron job flag)
12. **RUN_STAGING_CRON** - ❌ Not needed (GitHub Actions only)

### 🗑️ **Variables that should be REMOVED from staging (Unused)**

These are not used in codebase and should be deleted:

1. **ATHLETE_ID** - ❌ Only for local cron testing
2. **FRONTEND_BASE_URL** - ❌ Not used in code
3. **FRONTEND_URL** - ❌ Not used (use FRONTEND_REDIRECT instead)
4. **GITHUB_TOKEN** - ❌ Not used in app code (Railway may use separately)
5. **NO_CACHE** - ❌ Not used
6. **PREFERRED_URL_SCHEME** - ❌ Not used

## Recommendations

### For `.env.local`:
- ✅ Keep all core functionality variables
- ✅ Use `localhost` URLs instead of staging URLs
- ✅ Don't include staging/production-specific variables (webhooks, SMTP, session cookies)
- ✅ Your current `.env.local` looks good based on validation script results

### For Staging:
- ✅ Remove the 5-6 unused variables listed above
- ✅ Keep all required variables (31)
- ✅ Keep optional variables if you use those features (monitoring, cron jobs)

### Key Differences:

| Variable | Staging Value | Local Value |
|----------|--------------|-------------|
| `STRAVA_REDIRECT_URI` | `https://api.smartcoach.dev/auth/strava/callback` | `http://localhost:5000/auth/callback` |
| `CORS_ORIGINS` | `https://app.smartcoach.dev` | `https://localhost:5173,https://app.smartcoach.dev` |
| `DATABASE_URL` | Railway staging DB | Railway staging DB (shared) |
| `FRONTEND_REDIRECT` | `https://app.smartcoach.dev/post-oauth` | Not needed (or `http://localhost:5173/post-oauth`) |

## Validation Status

✅ **Your `.env.local` is correctly configured** - All validation tests passed!

The staging list has some cleanup opportunities (remove 5-6 unused vars), but the structure is good.

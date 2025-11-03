# Quick OAuth Verification Guide

## Step 1: Go to Strava Developer Portal
**URL:** https://www.strava.com/settings/api

## Step 2: Verify These Settings

### Required Settings

| Setting | Expected Value | Where to Find |
|---------|---------------|---------------|
| **App Name** | `SmartCoach` or `SmartCoach Training Plan` | App Information section |
| **Website** | `https://app.smartcoach.dev` | App Information section |
| **Category** | `Training` or `Fitness` | App Information section |
| **Description** | Brief description about training plans | App Information section |
| **Callback Domain** | `api.smartcoach.dev` | OAuth section |
| **Scopes** | `read, activity:read_all` | OAuth section |

### Full Callback URL
The complete callback URL should be: `https://api.smartcoach.dev/auth/strava/callback`

## Step 3: Verify Environment Variables Match

In your production environment (Railway), verify:
- `STRAVA_CLIENT_ID` matches the Client ID in Strava portal
- `STRAVA_CLIENT_SECRET` matches the Client Secret in Strava portal
- `STRAVA_REDIRECT_URI` = `https://api.smartcoach.dev/auth/strava/callback`

## Step 4: Mark as Complete

Once verified, update:
- `docs/strava-production-readiness.md` - Check off the verification task
- `docs/strava-oauth-verification-results.md` - Document the actual values

## Quick Checklist

- [ ] App Name matches "SmartCoach"
- [ ] Website is `https://app.smartcoach.dev`
- [ ] Category is "Training" or "Fitness"
- [ ] Description explains training plan generation
- [ ] Callback Domain is `api.smartcoach.dev`
- [ ] Scopes are `read, activity:read_all`
- [ ] Environment variables match portal settings

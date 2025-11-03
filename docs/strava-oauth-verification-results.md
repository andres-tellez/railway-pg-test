# Strava OAuth App Settings - Verification Results

**Date Verified:** _______________
**Verified By:** _______________
**Strava Portal:** https://www.strava.com/settings/api

## App Information Settings

### App Name
- **Value in Portal:** `_______________`
- **Expected:** SmartCoach or SmartCoach Training Plan
- **Status:** ⬜ Matches / ⬜ Needs Update

### Website
- **Value in Portal:** `_______________`
- **Expected:** `https://app.smartcoach.dev`
- **Status:** ⬜ Matches / ⬜ Needs Update

### Application Category
- **Value in Portal:** `_______________`
- **Expected:** Training or Fitness
- **Status:** ⬜ Matches / ⬜ Needs Update

### Short Description
- **Value in Portal:** `_______________`
- **Expected:** Brief description explaining SmartCoach generates and adapts training plans based on Strava activities
- **Status:** ⬜ Matches / ⬜ Needs Update

### Authorization Callback Domain
- **Value in Portal:** `_______________`
- **Expected:** `api.smartcoach.dev`
- **Full Callback URL:** `https://api.smartcoach.dev/auth/strava/callback`
- **Status:** ⬜ Matches / ⬜ Needs Update

## OAuth Scopes

### Scopes in Portal
- **Value in Portal:** `_______________`
- **Expected in Code:** `read, activity:read_all`
- **Status:** ⬜ Matches / ⬜ Needs Update

### Scope Justification
- **Status:** ⬜ Ready for submission (justification documented in checklist)

## Environment Variables (Production)

### STRAVA_CLIENT_ID
- **Value:** `_______________` (first 8 and last 4 chars: `...`)
- **Matches Portal:** ⬜ Yes / ⬜ No

### STRAVA_CLIENT_SECRET
- **Value:** `_______________` (masked)
- **Matches Portal:** ⬜ Yes / ⬜ No

### STRAVA_REDIRECT_URI
- **Value:** `https://api.smartcoach.dev/auth/strava/callback`
- **Matches Portal Callback Domain:** ⬜ Yes / ⬜ No

## Verification Summary

- [ ] All app settings verified and match expected values
- [ ] Callback domain matches production URL
- [ ] Scopes match code configuration
- [ ] Environment variables match portal settings
- [ ] Ready for production submission

## Notes
_(Add any notes about discrepancies or changes made)_

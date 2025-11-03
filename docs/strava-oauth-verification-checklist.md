# Strava OAuth App Settings Verification Checklist

## Overview
This checklist helps verify that all OAuth app settings in the Strava Developer Portal are correctly configured for production.

## Steps to Verify

### 1. Access Strava Developer Portal
- Go to: https://www.strava.com/settings/api
- Navigate to your SmartCoach app settings

### 2. App Information Settings

#### App Name
- [ ] **Current Value**: `_________________`
- [ ] **Expected**: Should clearly indicate "SmartCoach" or "SmartCoach Training Plan"
- [ ] **Action**: Update if needed to match branding

#### Website
- [ ] **Current Value**: `_________________`
- [ ] **Expected**: `https://app.smartcoach.dev` or your main website URL
- [ ] **Action**: Update if needed

#### Application Category
- [ ] **Current Value**: `_________________`
- [ ] **Expected**: Should be "Training" or "Fitness"
- [ ] **Action**: Update if needed

#### Short Description
- [ ] **Current Value**: `_________________`
- [ ] **Expected**: Brief description (max 200 chars) explaining that SmartCoach generates and adapts training plans based on Strava activities
- [ ] **Example**: "SmartCoach generates personalized running training plans that adapt based on your Strava activities and performance."
- [ ] **Action**: Update if needed

#### Authorization Callback Domain
- [ ] **Current Value**: `_________________`
- [ ] **Expected**: `api.smartcoach.dev` (must match the domain where your callback endpoint is hosted)
- [ ] **Action**: Update if needed
- [ ] **Note**: The full callback URL is: `https://api.smartcoach.dev/auth/strava/callback`

### 3. OAuth Scopes Verification

#### Current Scopes Requested in Code
Based on code review (`src/services/token_service.py`):
- ✅ `read` - Access user profile information
- ✅ `activity:read_all` - Access all activities (including private)

#### Verify in Strava Portal
- [ ] Navigate to "OAuth" or "Scopes" section
- [ ] Confirm scopes match what's requested in code
- [ ] **Note**: `activity:read_all` requires justification for production (see scope justification below)

#### Scope Justification for `activity:read_all`
**Why we need `activity:read_all`:**
- Users may mark certain runs as private in Strava
- Without `activity:read_all`, we cannot access private activities
- Missing private activities would lead to incomplete analysis and inaccurate training plan adaptations
- We only read running activities and store derived metrics (not full activity data)
- This is critical for accurate weekly plan adjustments based on actual performance

**Alternative considered:**
- Using only `activity:read` would miss private activities, leading to incomplete data
- This would result in poor training plan quality and user experience

### 4. Screenshots to Capture

#### Before OAuth (Consent Modal)
- [ ] Navigate to: `https://app.smartcoach.dev/setup`
- [ ] Click "Connect with Strava" button
- [ ] Screenshot the consent modal showing:
  - Privacy Policy checkbox
  - Terms of Service checkbox
  - Consent checkbox
  - Links to Privacy Policy and Terms
  - "Connect to Strava" button
- [ ] **Save as**: `screenshot-consent-modal.png`

#### After OAuth (Strava Authorization Page)
- [ ] After clicking "Connect to Strava" in the modal
- [ ] Screenshot the Strava authorization page showing:
  - App name and description
  - Requested scopes listed
  - "Authorize" button
- [ ] **Save as**: `screenshot-strava-authorize.png`

#### Post-Auth Success
- [ ] After authorizing, screenshot the redirect back to SmartCoach
- [ ] Show the success state or syncing indicator
- [ ] **Save as**: `screenshot-post-auth-success.png`

### 5. Environment Variables Verification

Verify these are set correctly in your production environment (Railway):

```bash
STRAVA_CLIENT_ID=<your_client_id>
STRAVA_CLIENT_SECRET=<your_secret>
STRAVA_REDIRECT_URI=https://api.smartcoach.dev/auth/strava/callback
```

- [ ] All three variables are set
- [ ] `STRAVA_REDIRECT_URI` matches the callback domain in Strava portal
- [ ] `STRAVA_CLIENT_ID` matches the Client ID in Strava portal

### 6. Testing Checklist

- [ ] Test OAuth flow end-to-end:
  1. Go to `https://app.smartcoach.dev/setup`
  2. Click "Connect with Strava"
  3. Verify consent modal appears
  4. Accept all checkboxes
  5. Click "Connect to Strava"
  6. Verify redirect to Strava authorization page
  7. Authorize the app
  8. Verify redirect back to SmartCoach
  9. Verify Strava connection is successful

- [ ] Test with a new user (no existing connection)
- [ ] Test with an existing user (reconnect flow)
- [ ] Verify activities are being fetched after connection

## Notes

- All changes in the Strava Developer Portal take effect immediately
- The callback domain must be an exact match (no wildcards)
- Screenshots are required for the production submission
- Keep screenshots organized in a folder for easy submission

## Related Documents
- [Strava Production Readiness Checklist](./strava-production-readiness.md)
- [Strava Screenshot Guide](../STRAVA_SCREENSHOT_GUIDE.md)

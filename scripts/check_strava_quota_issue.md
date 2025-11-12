# Fix Strava Quota Issue for Client ID 180950

## Problem
- Localhost needs to use `STRAVA_CLIENT_ID=180950`
- Getting "Limit of connected athletes exceeded" error
- Staging works fine with the same client ID

## Why Staging Works But Local Doesn't

**Possible reasons:**

1. **Staging already has established connections** - When you connect via staging, it might be reusing existing tokens/connections rather than creating new ones
2. **Different redirect URIs** - Staging uses `https://api.smartcoach.dev/auth/strava/callback` while local uses `http://localhost:5000/auth/strava/callback`. Strava might count these as separate "apps" for quota purposes
3. **Quota is per redirect URI** - Strava might limit connections per callback domain, so staging and local might share the same quota pool

## Solutions

### Option 1: Disconnect Old Test Connections (Free Up Quota)

1. **Go to Strava Settings:**
   - https://www.strava.com/settings/apps
   - Find "SmartCoach" app (client ID 180950)
   - Disconnect any old test accounts you don't need

2. **Check Connected Apps:**
   - Look for duplicate or old connections
   - Disconnect them to free up quota slots

### Option 2: Request Quota Increase from Strava

1. **Contact Strava Developer Support:**
   - Email: developers@strava.com
   - Subject: "Quota Increase Request for App 180950"
   - Explain:
     - You're using the app for both staging and local development
     - You need more athlete connections for testing
     - Mention it's for development/testing purposes

2. **What to include:**
   - Your Client ID: 180950
   - Reason: Local development and staging testing
   - Current usage: How many connections you have
   - Requested increase: How many more you need

### Option 3: Check if Staging Uses Different Client ID

Verify what staging is actually using:

1. Check Railway staging environment variables
2. See if `STRAVA_CLIENT_ID` in staging is different from 180950
3. If staging uses a different ID, that explains why it works

### Option 4: Reuse Existing Connections in Local

If you already have connections established:

1. **Check your local database:**
   - Look at `tokens` table
   - See if you have valid tokens for athlete_id 347085
   - If tokens exist and are valid, you might not need to reconnect

2. **Use existing tokens:**
   - If tokens exist, the app should reuse them
   - You might not need to go through OAuth flow again

## Immediate Action Items

1. ✅ Check Railway staging `STRAVA_CLIENT_ID` - is it 180950 or different?
2. ✅ Go to Strava → Settings → Apps and disconnect old test connections
3. ✅ Check local database for existing valid tokens
4. ✅ If needed, email Strava support for quota increase

## Verification

After freeing up quota or getting increase:
- Try connecting via localhost again
- Should work without quota error


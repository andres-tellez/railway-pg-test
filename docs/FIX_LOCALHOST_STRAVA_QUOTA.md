# Fix: "Limit of connected athletes exceeded" on Localhost

## Problem
When trying to connect Strava via localhost, you get:
```
Error 403: Limit of connected athletes exceeded
```

But staging (Railway) works fine.

## Root Cause
**Local and staging are using the SAME Strava Client ID**, and that Strava app has hit its quota limit for connected athletes. Strava has limits on how many athletes can connect to an app, especially for development apps.

## Solution Options

### Option 1: Create a Separate Strava App for Local Development (Recommended)

1. **Go to Strava Developer Portal**
   - URL: https://www.strava.com/settings/api
   - Click "Create App" or "Register Your Application"

2. **Create a new app for local development:**
   - **App Name**: `SmartCoach Local Dev` (or similar)
   - **Category**: Training
   - **Website**: `http://localhost:5173`
   - **Authorization Callback Domain**: `localhost:5000`
   - **Full Callback URL**: `http://localhost:5000/auth/strava/callback`
   - **Scopes**: `read, activity:read_all`

3. **Update `.env.local` with the new app credentials:**
   ```bash
   STRAVA_CLIENT_ID=<new_local_client_id>
   STRAVA_CLIENT_SECRET=<new_local_client_secret>
   STRAVA_REDIRECT_URI=http://localhost:5000/auth/strava/callback
   ```

4. **Keep staging/production using the original app:**
   - Staging/production should continue using the original `STRAVA_CLIENT_ID`
   - This way, local development won't affect production quota limits

### Option 2: Request Quota Increase from Strava

If you want to keep using the same app:

1. **Contact Strava Developer Support**
   - Email: developers@strava.com
   - Explain that you need a quota increase for development/testing
   - Mention that you're using the app for both staging and local development

2. **Wait for approval** (can take a few days)

### Option 3: Disconnect Old Test Connections

If you have old test connections in your Strava app:

1. Go to Strava → Settings → My Apps
2. Find your app and disconnect old test accounts
3. This frees up quota slots

## Why Staging Works But Local Doesn't

- **Staging** might already have connections established, so it's not creating new ones
- **Localhost** is trying to create NEW connections, which hits the quota limit
- Or staging might be using a different client ID (check your staging environment variables)

## Verification

After implementing Option 1, verify:

1. **Check your `.env.local`:**
   ```bash
   STRAVA_CLIENT_ID should be different from staging
   STRAVA_REDIRECT_URI should be http://localhost:5000/auth/strava/callback
   ```

2. **Test the connection:**
   - Start your local server
   - Try connecting Strava
   - Should work without quota errors

## Best Practice

**Always use separate Strava apps for:**
- ✅ Local development
- ✅ Staging/testing
- ✅ Production

This prevents:
- Quota limit issues
- Test data mixing with production
- Development affecting production users

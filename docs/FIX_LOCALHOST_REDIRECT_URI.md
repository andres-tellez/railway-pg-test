# Fix: Localhost Redirect URI HTTPS Conversion Issue

## Problem

The app auto-converts `http://localhost:5000` to `https://localhost:5000` because it's running on HTTPS (mkcert), but Strava app 180950 might only have `http://localhost:5000` registered.

## Solution

### Option 1: Update Strava App to Allow HTTPS (Recommended)

1. Go to Strava Developer Portal: https://www.strava.com/settings/api
2. Find your app (Client ID: 180950)
3. Update **Authorization Callback Domain** to allow both:
   - `localhost:5000` (covers both HTTP and HTTPS)
   - OR add `https://localhost:5000` explicitly

Strava's callback domain setting is flexible - if you set it to `localhost:5000`, it should accept both `http://localhost:5000` and `https://localhost:5000`.

### Option 2: Update .env.local to Use HTTPS

If Strava already has `https://localhost:5000` registered:

1. Update `.env.local`:

   ```bash
   STRAVA_REDIRECT_URI=https://localhost:5000/auth/strava/callback
   ```

2. Restart your local server

### Option 3: Disable Auto-Conversion (Not Recommended)

If you want to keep using HTTP, you'd need to modify the code, but this is not recommended since your app runs on HTTPS.

## Why This Matters

The quota error might be a red herring. The real issue could be:

1. Redirect URI mismatch → OAuth fails
2. Strava shows quota error as a generic error message
3. But the actual problem is the redirect URI not matching

## Verification

After updating Strava app settings:

1. Try connecting again
2. Check if you still get quota error
3. If quota error persists, then it's a real quota issue and you need to:
   - Disconnect old test accounts from Strava → Settings → My Apps
   - Request quota increase from Strava support

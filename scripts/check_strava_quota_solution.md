# Fix Strava Quota Limit for App 180950

## Problem Confirmed
- Strava app 180950 has hit its quota limit for connected athletes
- Localhost needs to use this app (180950)
- Staging works because it's reusing existing connections, not creating new ones

## Solutions

### Option 1: Free Up Quota by Disconnecting Old Test Accounts

1. **Go to Strava → Settings → My Apps:**
   - URL: https://www.strava.com/settings/apps
   - Find "SmartCoach" app (or whatever name app 180950 has)

2. **Disconnect old test accounts:**
   - Look for duplicate connections
   - Disconnect test accounts you no longer need
   - Each disconnected account frees up one quota slot

3. **Check connected apps:**
   - Go to https://www.strava.com/settings/apps
   - See all apps connected to your Strava account
   - Disconnect any old test connections

### Option 2: Request Quota Increase from Strava

**Email Strava Developer Support:**
- **Email:** developers@strava.com
- **Subject:** "Quota Increase Request for App 180950"
- **Body:**
  ```
  Hello Strava Developer Support,
  
  I'm requesting a quota increase for my Strava application.
  
  Client ID: 180950
  App Name: [Your app name]
  
  Reason: I need more athlete connections for local development and staging testing. 
  Currently blocked from connecting new athletes due to quota limit.
  
  Current Usage: [X] connected athletes
  Requested Increase: [Y] additional connections
  
  This is for development/testing purposes.
  
  Thank you!
  ```

### Option 3: Check if You Can Reuse Existing Connection

If you already have athlete_id 347085 connected in your local database, you might not need to reconnect:

1. **Check your local database:**
   - Look for existing tokens for athlete_id 347085
   - If tokens exist and are valid, the app should reuse them
   - You might not need to go through OAuth again

2. **Verify connection status:**
   - Check `user_athletes` table for athlete_id 347085
   - Check `tokens` table for valid tokens
   - If both exist, connection should work without OAuth

## Why Staging Works But Local Doesn't

- **Staging:** Already has established connections, so it's not creating NEW connections (doesn't hit quota)
- **Localhost:** Trying to create a NEW connection, which hits the quota limit

## Immediate Action

1. ✅ Go to Strava → Settings → My Apps and disconnect old test accounts
2. ✅ Email Strava support for quota increase (if needed)
3. ✅ Check if you can reuse existing connection in local database

## Verification

After freeing up quota or getting increase:
- Try connecting via localhost again
- Should work without quota error


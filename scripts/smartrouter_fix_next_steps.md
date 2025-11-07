# SmartRouter Race Condition Fix - Next Steps

## What Was Fixed

**Problem**: After Strava OAuth, staging was going directly to `/onboarding` instead of showing the setup page with Step 1 complete.

**Root Cause**: Race condition in `SmartRouter.tsx` - it was checking user state (`hasStrava=true`) immediately after OAuth, causing redirect to `/onboarding` before setup page could render.

**Fix Applied**: Modified `SmartRouter.tsx` to:
1. Return early when `?strava=connected` is detected (prevents user state check)
2. Also skip user state check if already on `/setup` page

## Next Steps

### Step 1: Test Locally ✅

1. **Start your local dev server**
   ```bash
   # Frontend
   npm run dev

   # Backend
   python run.py
   ```

2. **Test the Strava OAuth flow**:
   - Go to `https://localhost:5173/setup`
   - Click "Connect with Strava" button
   - Complete Strava OAuth
   - **Expected**: Should see setup page with Step 1 complete, Step 2 visible
   - **Should NOT**: Go directly to `/onboarding`

3. **Check browser console** for logs:
   - Should see: `🔄 Strava OAuth callback detected - redirecting to /setup to show consent completion`
   - Should NOT see: `⚙️ User has Strava but not onboarded, redirecting to /onboarding`

### Step 2: Verify FRONTEND_REDIRECT in Staging

**Check what `FRONTEND_REDIRECT` is set to in Railway staging backend:**

1. Go to Railway dashboard
2. Open `web-staging` service
3. Go to Variables tab
4. Find `FRONTEND_REDIRECT`
5. **Expected value**: `https://app.smartcoach.dev/post-oauth` or `https://app.smartcoach.dev/setup`

**If it's set to `/post-oauth`**: That's fine - the backend redirects there, then `SmartRouter` should handle it.

**If it's set to `/onboarding`**: That would explain why staging goes directly there! Change it to `/post-oauth` or `/setup`.

### Step 3: Commit and Deploy

Once you've tested locally:

1. **Commit the fix**:
   ```bash
   git add frontend/src/components/SmartRouter.tsx
   git commit -m "Fix SmartRouter race condition for Strava OAuth callback

   - Skip user state check when ?strava=connected is present
   - Prevent redirect to /onboarding before setup page can render
   - Allows setup page to show Step 1 complete and Step 2

   Fixes issue where staging was going directly to profile form after OAuth"
   ```

2. **Push to dev**:
   ```bash
   git push origin dev
   ```

3. **Merge to staging**:
   ```bash
   git checkout staging
   git merge dev
   git push origin staging
   ```

4. **Wait for Railway deployment** (~2-3 minutes)

### Step 4: Test in Staging

1. Go to `https://app.smartcoach.dev/setup`
2. Click "Connect with Strava" button
3. Complete Strava OAuth
4. **Expected**: Should see setup page with Step 1 complete, Step 2 visible (same as local)
5. **Should NOT**: Go directly to `/onboarding`

### Step 5: If Still Not Working

If staging still goes directly to `/onboarding` after deploying:

1. **Check browser console** for logs
2. **Check Railway logs** for backend redirect URL
3. **Verify `FRONTEND_REDIRECT`** is not set to `/onboarding`
4. **Check if there are any other redirects** happening in the code

## Summary

✅ **Fix applied**: `SmartRouter.tsx` now skips user state check when `?strava=connected` is present

⏳ **Next**: Test locally, then commit and deploy to staging

🔍 **Verify**: Check `FRONTEND_REDIRECT` value in staging backend variables

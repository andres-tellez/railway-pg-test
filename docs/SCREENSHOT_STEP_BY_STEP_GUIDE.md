# Screenshot Capture - Step-by-Step Guide

**For users who already have Strava connected**

---

## 🎯 Goal

Capture 3 required screenshots:
1. Consent Modal (before OAuth)
2. Strava Authorization Page (during OAuth)
3. Post-Auth Success (after OAuth)

---

## Step 1: Disconnect Strava (to trigger OAuth flow)

Since you already have Strava connected, you need to disconnect it first to trigger the OAuth flow again.

### Option A: Via Settings Page (Recommended)

1. **Navigate to Settings:**
   - Go to: `https://app.smartcoach.dev/settings`
   - Or click "Settings" in the top navigation menu

2. **Disconnect Strava:**
   - Scroll down to "Strava Connection" section
   - Click the red "Disconnect Strava Account" button
   - Confirm the disconnection in the popup
   - You should see a success message

3. **Verify Disconnection:**
   - The page should now show "You don't have a Strava account connected"
   - You're ready to trigger the OAuth flow again

### Option B: Via Database (Advanced)

If the UI doesn't work, you can disconnect via database:

```sql
-- Find your user_id first
SELECT user_id, email FROM user_identity WHERE email = 'your-email@example.com';

-- Delete the athlete link (this disconnects Strava)
DELETE FROM user_athletes WHERE user_id = 'your-user-id-here';

-- Delete tokens
DELETE FROM tokens WHERE athlete_id IN (
  SELECT athlete_id FROM user_athletes WHERE user_id = 'your-user-id-here'
);
```

**Note:** After disconnecting, refresh the page or navigate to `/setup`

---

## Step 2: Navigate to Setup Page

1. **Go to Setup Page:**
   - URL: `https://app.smartcoach.dev/setup`
   - Or click "Get Started" / "Setup" in navigation (if you don't have Strava connected)

2. **What You Should See:**
   - Page titled "Welcome to SmartCoach"
   - Step 1: "Connect Strava" section
   - Orange "Connect with Strava" button
   - "Powered by Strava" text below button

3. **Take Screenshot #4 (Optional):**
   - **File:** `screenshot-connect-button.png`
   - **What:** The setup page showing the orange "Connect with Strava" button
   - **Location:** `screenshots/screenshot-connect-button.png`

---

## Step 3: Screenshot #1 - Consent Modal

1. **Click "Connect with Strava" Button:**
   - On the setup page (`/setup`)
   - Click the orange "Connect with Strava" button

2. **Consent Modal Appears:**
   - A modal should pop up over the page
   - This is the consent modal you need to screenshot

3. **What to Capture:**
   - ✅ Strava logo (orange square in top left)
   - ✅ "Connect with Strava" header
   - ✅ "What Data We'll Access" section (blue box)
   - ✅ "How We'll Use Your Data" section (green box)
   - ✅ "Your Privacy Rights" section (gray box)
   - ✅ Three checkboxes (unchecked):
     - [ ] I have read and agree to the Privacy Policy
     - [ ] I have read and agree to the Terms of Service
     - [ ] I consent to SmartCoach accessing my Strava data
   - ✅ "Connect to Strava" button (should be disabled/grayed out)
   - ✅ "Cancel" button

4. **Take Screenshot:**
   - **File Name:** `screenshot-consent-modal.png`
   - **Save Location:** `screenshots/screenshot-consent-modal.png`
   - **Tips:**
     - Make sure all text is readable
     - Include the full modal (not cut off)
     - You can use browser screenshot tools or Windows Snipping Tool

---

## Step 4: Screenshot #2 - Strava Authorization Page

1. **Complete Consent Modal:**
   - Check all three checkboxes in the consent modal
   - The "Connect to Strava" button should turn orange and become clickable
   - Click "Connect to Strava"

2. **Redirect to Strava:**
   - You'll be redirected to Strava's authorization page
   - URL will be something like: `https://www.strava.com/oauth/authorize?...`

3. **What to Capture:**
   - ✅ Strava's authorization page
   - ✅ App name: "SmartCoach" (or your app name)
   - ✅ App description/logo
   - ✅ Requested permissions/scopes listed:
     - `read` - Access user profile information
     - `activity:read_all` - Access all activities (including private)
   - ✅ "Authorize" button (orange)
   - ✅ "Cancel" button

4. **Take Screenshot:**
   - **File Name:** `screenshot-strava-authorize.png`
   - **Save Location:** `screenshots/screenshot-strava-authorize.png`
   - **Tips:**
     - Include the URL bar if possible (shows it's Strava's page)
     - Make sure scopes/permissions are visible
     - All text should be readable

---

## Step 5: Screenshot #3 - Post-Auth Success

1. **Authorize on Strava:**
   - On the Strava authorization page
   - Click the orange "Authorize" button

2. **Redirect Back to SmartCoach:**
   - You'll be redirected back to: `https://app.smartcoach.dev/setup?strava=connected`
   - The page will show a syncing state

3. **What to Capture:**
   - ✅ Success message or syncing indicator
   - ✅ "Syncing your Strava data..." message (if visible)
   - ✅ Loading spinner or progress indicator
   - ✅ Any confirmation that Strava is connected
   - ✅ "Powered by Strava" attribution (if visible)

4. **Take Screenshot:**
   - **File Name:** `screenshot-post-auth-success.png`
   - **Save Location:** `screenshots/screenshot-post-auth-success.png`
   - **Tips:**
     - Capture the syncing/loading state
     - May need to screenshot quickly before it completes
     - If it completes too fast, refresh the page with `?strava=connected` in URL

---

## Step 6: Save Screenshots

### Create Screenshots Folder

1. **In your project root directory:**
   ```bash
   # Create screenshots folder
   mkdir screenshots
   ```

2. **Save all screenshots there:**
   ```
   screenshots/
   ├── screenshot-consent-modal.png
   ├── screenshot-strava-authorize.png
   ├── screenshot-post-auth-success.png
   └── screenshot-connect-button.png (optional)
   ```

### File Naming

Use these exact names:
- `screenshot-consent-modal.png`
- `screenshot-strava-authorize.png`
- `screenshot-post-auth-success.png`
- `screenshot-connect-button.png` (optional)

### Screenshot Quality

- **Format:** PNG (preferred) or JPG
- **Resolution:** At least 1920x1080 (or your screen resolution)
- **Quality:** High quality, all text readable
- **File Size:** Under 5MB per screenshot

---

## Quick Reference: Exact URLs

1. **Settings Page (to disconnect):**
   - `https://app.smartcoach.dev/settings`

2. **Setup Page (to start OAuth):**
   - `https://app.smartcoach.dev/setup`

3. **After Authorization (success page):**
   - `https://app.smartcoach.dev/setup?strava=connected`

---

## Troubleshooting

### Problem: "Connect with Strava" button doesn't show consent modal

**Solution:**
- Make sure you're logged in
- Check browser console for errors
- Try refreshing the page
- Make sure Strava is actually disconnected (check Settings page)

### Problem: Consent modal doesn't appear

**Solution:**
- Check browser console for JavaScript errors
- Try clearing browser cache
- Make sure you're on `/setup` page
- Verify `StravaConsentModal` component is working

### Problem: Strava authorization page doesn't show

**Solution:**
- Check that OAuth redirect URL is correct
- Verify Strava app settings in Developer Portal
- Check browser console for errors
- Make sure you're not already authorized (check Strava settings)

### Problem: Can't capture syncing state (too fast)

**Solution:**
- Add `?strava=connected` to URL manually after authorization
- Or use browser DevTools to slow down network (Network tab → Throttling)
- Or refresh the page with the query parameter

---

## Verification Checklist

Before submitting:
- [ ] Screenshot 1: Consent Modal captured and saved
- [ ] Screenshot 2: Strava Authorization Page captured and saved
- [ ] Screenshot 3: Post-Auth Success captured and saved
- [ ] Screenshot 4: Connect Button captured (optional)
- [ ] All screenshots saved to `screenshots/` folder
- [ ] All screenshots are readable and high quality
- [ ] File names match exactly: `screenshot-*.png`

---

## Next Steps After Screenshots

1. Verify all screenshots are clear and readable
2. Review each screenshot to ensure required elements are visible
3. Upload screenshots to Strava Developer Portal when submitting
4. Keep screenshots organized in `screenshots/` folder

---

**Last Updated:** November 3, 2025

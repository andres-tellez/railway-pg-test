# Screenshot Capture Checklist - Consent & Post-Auth

**Purpose:** Capture screenshots required for Strava production submission
**Full Guide:** See [`STRAVA_SCREENSHOT_GUIDE.md`](../STRAVA_SCREENSHOT_GUIDE.md) for complete details

---

## Required Screenshots for Production Submission

### 1. Consent Modal (Before OAuth) ✅ REQUIRED

**Location:** `https://app.smartcoach.dev/setup`

**Steps:**
1. Log in to SmartCoach
2. Navigate to `/setup` page
3. Click "Connect with Strava" button
4. **Screenshot the consent modal** that appears

**What to Capture:**
- ✅ Consent modal with Strava logo
- ✅ "Connect with Strava" header
- ✅ "What Data We'll Access" section
- ✅ "How We'll Use Your Data" section
- ✅ Three checkboxes:
  - [ ] I have read and agree to the Privacy Policy
  - [ ] I have read and agree to the Terms of Service
  - [ ] I consent to SmartCoach accessing my Strava data
- ✅ Links to Privacy Policy and Terms of Service
- ✅ "Connect to Strava" button (disabled until all checkboxes checked)
- ✅ "Cancel" button

**File Name:** `screenshot-consent-modal.png`

**Status:** ⬜ Not Captured / ⬜ Captured / ⬜ Ready for Submission

---

### 2. Strava Authorization Page (During OAuth) ✅ REQUIRED

**Location:** Redirects to Strava after clicking "Connect to Strava" in consent modal

**Steps:**
1. Complete consent modal (check all boxes, click "Connect to Strava")
2. **Screenshot the Strava authorization page** that appears

**What to Capture:**
- ✅ Strava's authorization page
- ✅ App name: "SmartCoach" (or your app name)
- ✅ App description
- ✅ Requested scopes listed:
  - `read` - Access user profile information
  - `activity:read_all` - Access all activities (including private)
- ✅ "Authorize" button
- ✅ "Cancel" button

**File Name:** `screenshot-strava-authorize.png`

**Status:** ⬜ Not Captured / ⬜ Captured / ⬜ Ready for Submission

---

### 3. Post-Auth Success (After OAuth) ✅ REQUIRED

**Location:** `https://app.smartcoach.dev/setup?strava=connected`

**Steps:**
1. Click "Authorize" on Strava authorization page
2. Wait for redirect back to SmartCoach
3. **Screenshot the success/syncing state**

**What to Capture:**
- ✅ Success message or syncing indicator
- ✅ "Syncing your Strava data..." message (if visible)
- ✅ Loading spinner or progress indicator
- ✅ Any confirmation that Strava is connected
- ✅ "Powered by Strava" attribution (if visible)

**File Name:** `screenshot-post-auth-success.png`

**Status:** ⬜ Not Captured / ⬜ Captured / ⬜ Ready for Submission

---

## Optional Screenshots (Recommended)

### 4. Connect with Strava Button

**Location:** `https://app.smartcoach.dev/setup`

**Steps:**
1. Navigate to `/setup` page (before clicking button)
2. **Screenshot the page showing the "Connect with Strava" button**

**What to Capture:**
- ✅ Official orange "Connect with Strava" button
- ✅ Strava logo on button
- ✅ "Powered by Strava" attribution below button
- ✅ Clear visibility of button design

**File Name:** `screenshot-connect-button.png`

**Status:** ⬜ Not Captured / ⬜ Captured / ⬜ Ready for Submission

---

## Screenshot Requirements

### Technical Requirements
- **Format:** PNG or JPG
- **Resolution:** At least 1920x1080 (or your screen resolution)
- **Quality:** High quality, readable text
- **File Size:** Under 5MB per screenshot

### Content Requirements
- All text must be readable
- No sensitive personal information visible (you can blur if needed)
- Screenshots should show the complete modal/page
- Include browser chrome if it helps show context

---

## Where to Store Screenshots

**Recommended Location:**
- Create folder: `docs/screenshots/` or `screenshots/` in project root
- Store all screenshots there
- Keep filenames consistent with names above

**For Submission:**
- You'll upload these screenshots to the Strava Developer Portal when submitting for production
- Keep them organized and easily accessible

---

## Verification Checklist

Before marking this task complete:
- [ ] Screenshot 1: Consent Modal captured
- [ ] Screenshot 2: Strava Authorization Page captured
- [ ] Screenshot 3: Post-Auth Success captured
- [ ] Screenshot 4: Connect Button captured (optional but recommended)
- [ ] All screenshots are readable and high quality
- [ ] Screenshots are stored in organized location
- [ ] Ready to upload to Strava submission form

---

## Quick Reference URLs

- **Setup Page:** https://app.smartcoach.dev/setup
- **Privacy Policy:** https://app.smartcoach.dev/privacy-policy
- **Terms of Service:** https://app.smartcoach.dev/terms-of-service
- **Strava Developer Portal:** https://www.strava.com/settings/api

---

**Last Updated:** November 3, 2025

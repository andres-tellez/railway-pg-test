# Strava API Review - Screenshot Guide

**App**: SmartCoach
**Required**: Screenshots showing (1) ALL places Strava data is displayed, and (2) "Connect with Strava" button

---

## 📸 **SCREENSHOTS YOU NEED TO TAKE**

### **SECTION 1: "Connect with Strava" Button (REQUIRED)**

#### **Screenshot 1: Connect with Strava Button**
- **Location**: Landing/Setup Page (`/setup`)
- **URL**: `https://app.smartcoach.dev/setup` (or `https://localhost:5173/setup`)
- **What to Show**:
  - ✅ Official orange "Connect with Strava" button with Strava logo
  - ✅ "Powered by Strava" attribution below button
  - ✅ Clear visibility of the button design

**How to Capture**:
1. Log in to SmartCoach
2. Navigate to `/setup` page
3. Take full-page screenshot showing the button
4. Make sure the orange Strava button is clearly visible

---

#### **Screenshot 2: Consent Modal (Before OAuth)**
- **Location**: After clicking "Connect with Strava"
- **What to Show**:
  - ✅ Consent modal with data explanation
  - ✅ Three checkboxes (Privacy Policy, Terms, Consent)
  - ✅ "Connect to Strava" button in modal
  - ✅ Links to Privacy Policy and Terms

**How to Capture**:
1. Click "Connect with Strava" button
2. Screenshot the consent modal that appears
3. Make sure all text is readable

---

### **SECTION 2: ALL Places Strava Data is Displayed (REQUIRED)**

#### **Screenshot 3: Metrics Overview Page**
- **Location**: Main Metrics Page (`/metrics`)
- **URL**: `https://app.smartcoach.dev/metrics`
- **Strava Data Shown**:
  - Weekly mileage totals
  - Pace data (from Strava activities)
  - Heart rate zone data
  - Activity counts

**How to Capture**:
1. Navigate to `/metrics` page
2. Take full-page screenshot
3. Make sure charts and data are visible
4. Capture the "Powered by Strava" in footer if visible

---

#### **Screenshot 4: GYR Metrics Page**
- **Location**: GYR (Green/Yellow/Red) Tab (`/metrics?tab=gyr`)
- **URL**: `https://app.smartcoach.dev/metrics?tab=gyr`
- **Strava Data Shown**:
  - Total Runs (from Strava activities)
  - Weekly Pace (from Strava activity data)
  - Weekly HR Zones (from Strava heart rate data)
  - Historical timeline bars

**How to Capture**:
1. Navigate to `/metrics` page
2. Click on "GYR" tab
3. Take full-page screenshot showing all three metrics
4. Capture the timeline bars for each metric

---

#### **Screenshot 5: VO2 Max Page (if visible)**
- **Location**: VO2 Metrics (`/vo2-metrics` or in Metrics page)
- **URL**: Check if this page is accessible
- **Strava Data Shown**:
  - VO2 max estimates (calculated from Strava activities)
  - Performance trends

**How to Capture**:
1. Navigate to VO2 metrics page
2. Take screenshot if accessible

---

#### **Screenshot 6: Training Plan Page**
- **Location**: My Plan Page (`/plan/overview`)
- **URL**: `https://app.smartcoach.dev/plan/overview`
- **Strava Data Shown**:
  - Current week's planned workouts
  - Calendar view with training days
  - **Note**: This shows planned workouts, NOT historical Strava data
  - **Important**: If you display actual completed activities here, screenshot it

**How to Capture**:
1. Navigate to `/plan/overview`
2. Take screenshot of the plan/calendar
3. Check if any historical Strava data is displayed here

---

#### **Screenshot 7: Footer Attribution**
- **Location**: Any page footer
- **What to Show**:
  - ✅ "Powered by Strava" text in footer
  - ✅ Privacy Policy link
  - ✅ Terms of Service link
  - ✅ Support contact

**How to Capture**:
1. Go to any page (e.g., `/metrics`)
2. Scroll to bottom
3. Screenshot the footer showing Strava attribution

---

## 📋 **CHECKLIST OF PAGES WITH STRAVA DATA**

Based on your codebase analysis, here are ALL pages that display Strava data:

### **✅ Pages WITH Strava Data** (Need Screenshots):
1. **`/setup`** - Connect with Strava button (REQUIRED)
2. **`/metrics`** - Main metrics dashboard (Strava activity data)
3. **`/metrics?tab=gyr`** - GYR metrics (Total Runs, Pace, HR Zones from Strava)
4. **Footer** - "Powered by Strava" attribution

### **❌ Pages WITHOUT Strava Data** (No Screenshot Needed):
1. **`/plan/overview`** - Shows planned workouts (future), not historical Strava data
2. **`/onboarding`** - User input form only
3. **`/home`** - Dashboard with links only
4. **`/privacy-policy`** - Legal text
5. **`/terms-of-service`** - Legal text

---

## 🎯 **WHAT STRAVA IS LOOKING FOR**

### **For "Connect with Strava" Button**:
- ✅ Official orange color (`#FC5200`)
- ✅ Correct button text: "Connect with Strava"
- ✅ Strava logo visible on button
- ✅ Links to correct OAuth URL (`https://www.strava.com/oauth/authorize`)
- ✅ "Powered by Strava" attribution visible

### **For Strava Data Display**:
- ✅ Only shows data to the user who owns it (not other users)
- ✅ Data attribution ("Powered by Strava" in footer)
- ✅ No leaderboards or cross-user comparisons
- ✅ Clear purpose (training metrics, not social features)

---

## 📷 **SCREENSHOT NAMING CONVENTION**

When you save screenshots, use clear names:

```
1_connect_with_strava_button.png
2_consent_modal.png
3_metrics_overview_page.png
4_gyr_metrics_page.png
5_footer_attribution.png
```

---

## 📝 **SUBMISSION NOTES TO INCLUDE**

When submitting to Strava, include this explanation:

```
**SmartCoach - Strava Data Usage**

1. CONNECT WITH STRAVA BUTTON:
   - Location: Landing/Setup page (/setup)
   - Uses official Strava orange color and logo
   - Includes "Powered by Strava" attribution
   - Shows consent modal before OAuth (see screenshot)

2. STRAVA DATA DISPLAY LOCATIONS:

   a) Metrics Overview (/metrics):
      - Displays: Weekly mileage, pace, heart rate zones
      - Purpose: Training progress tracking
      - User: Only shows data to the authenticated user

   b) GYR Metrics (/metrics?tab=gyr):
      - Displays: Total runs, weekly pace, HR zone distribution
      - Purpose: Training quality indicators
      - User: Only shows data to the authenticated user

   c) Footer Attribution:
      - All pages include "Powered by Strava" attribution
      - Links to Privacy Policy and Terms of Service

3. DATA PRIVACY:
   - No leaderboards or social features
   - No cross-user data display
   - User-specific data only
   - Full data deletion available
   - Data export available

4. COMPLIANCE:
   - Privacy Policy: https://app.smartcoach.dev/privacy-policy
   - Terms of Service: https://app.smartcoach.dev/terms-of-service
   - User consent required before OAuth
   - GDPR compliant
```

---

## 🚀 **READY TO TAKE SCREENSHOTS?**

### **Step 1: Start Your App**
```bash
# Terminal 1: Frontend
cd frontend
npm run dev

# Terminal 2: Backend
python run.py
```

### **Step 2: Log In**
1. Go to `https://localhost:5173`
2. Sign in with a test account that has Strava connected
3. Make sure you have some Strava data synced

### **Step 3: Take Screenshots**
Follow the guide above for each screenshot.

### **Step 4: Submit to Strava**
Upload screenshots to your Strava API application settings.

---

## ⚠️ **IMPORTANT NOTES**

1. **Use Production URL if Available**:
   - If your app is deployed, use `https://app.smartcoach.dev`
   - Otherwise, `https://localhost:5173` is fine

2. **Make Sure Data is Visible**:
   - Use an account with actual Strava activities synced
   - Charts and metrics should show real data

3. **Full-Page Screenshots**:
   - Use browser extensions like "Full Page Screen Capture"
   - Or take multiple screenshots and stitch them

4. **High Quality**:
   - Use PNG format (not JPG)
   - Make sure text is readable
   - Good lighting/contrast

---

## 📧 **NEED HELP?**

If you need me to:
- Walk through taking specific screenshots
- Explain what data is displayed on each page
- Help with the submission text

Just ask!

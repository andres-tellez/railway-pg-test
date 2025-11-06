# Manual Testing Guide - PostOAuth Error Handling

**Date:** November 2025
**Purpose:** Step-by-step guide for manually testing PostOAuth error scenarios

---

## 🚀 Setup

### Prerequisites
1. ✅ Frontend running locally or on staging
2. ✅ Backend running and accessible
3. ✅ Browser Developer Tools open (F12)
4. ✅ Network tab open for monitoring

### Testing Environment
- **Local:** `http://localhost:5173` (or your frontend port)
- **Staging:** `https://app.smartcoach.dev` (or your staging URL)
- **Backend:** Check `VITE_BACKEND_URL` in `.env.local`

---

## 📋 Test Scenarios

### Test 1: Successful Authentication (Baseline)

**Purpose:** Verify normal flow works before testing errors

**Steps:**
1. Open browser DevTools (F12)
2. Go to Console tab
3. Navigate to login page
4. Complete Auth0 login
5. **Expected:** You should be redirected after successful authentication
6. **Check Console:** Look for these logs:
   - `🔍 PostOAuth mounted →`
   - `🪪 ID token → present`
   - `📡 Posting token to backend:`
   - `📡 /auth/login/callback → 200`

**Pass Criteria:**
- ✅ No errors in console
- ✅ Successful redirect
- ✅ Loading state appears briefly
- ✅ No error UI shown

---

### Test 2: Network Error (Disconnect Internet)

**Purpose:** Test error handling when network is unavailable

**Steps:**
1. Open browser DevTools (F12)
2. Go to Network tab
3. Navigate to login page
4. **IMPORTANT:** Before clicking login, disconnect internet (or disable network in DevTools)
5. Complete Auth0 login (this might work from cache)
6. **Expected:** Error UI should appear

**Expected Error UI:**
- **Message:** "Network connection failed"
- **Details:** "Unable to connect to the server. Please check your internet connection."
- **Button:** "Try Again" (visible)
- **Button:** "Continue to App" (visible)
- **Tip:** "Tip: Check your internet connection and firewall settings."

**Alternative Method (DevTools):**
1. Open Network tab
2. Right-click → "Block request domain" or select "Offline"
3. Attempt authentication
4. Verify error UI appears

**Pass Criteria:**
- ✅ Error UI displays correctly
- ✅ Error message is clear
- ✅ "Try Again" button is visible
- ✅ "Continue to App" button is visible
- ✅ Network tip is shown

**Test Retry:**
1. Reconnect internet
2. Click "Try Again"
3. **Expected:** Authentication should retry and succeed

**Test Continue:**
1. Click "Continue to App"
2. **Expected:** Navigate to home page

---

### Test 3: Authentication Error (401) - Invalid Token

**Purpose:** Test handling when token is invalid or expired

**Steps:**
1. Open browser DevTools (F12)
2. Go to Application tab → Storage → Local Storage
3. Find Auth0 tokens (if any) and delete them
4. Navigate to login page
5. Complete Auth0 login
6. **Before** PostOAuth completes, manually edit the token in DevTools:
   - Open Network tab
   - Find the `/auth/login/callback` request
   - Edit request payload to send invalid token
   - Or: Modify `id_token` in console before sending

**Using DevTools Console:**
```javascript
// Intercept fetch to modify token
const originalFetch = window.fetch;
window.fetch = function(...args) {
  if (args[0].includes('/auth/login/callback')) {
    const body = JSON.parse(args[1].body);
    body.id_token = 'invalid_token_here';
    args[1].body = JSON.stringify(body);
  }
  return originalFetch.apply(this, args);
};
```

**Expected Error UI:**
- **Message:** "Authentication failed"
- **Details:** "Your login token is invalid or expired. Please try logging in again."
- **Button:** "Try Again" (visible)
- **Button:** "Continue to App" (visible)

**Pass Criteria:**
- ✅ Error UI displays correctly
- ✅ Error message indicates authentication issue
- ✅ "Try Again" button works
- ✅ "Continue to App" button works

---

### Test 4: Server Error (500+) - Simulate Backend Error

**Purpose:** Test handling when backend returns server error

**Steps:**
1. **Option A - Modify Backend (Temporary):**
   - In `src/routes/auth0_routes.py`, temporarily add:
     ```python
     @auth0_bp.route("/login/callback", methods=["POST"])
     def login_callback():
         return error_response("Simulated server error", status_code=500)
     ```
   - Restart backend
   - Attempt authentication

2. **Option B - Use DevTools Network Interception:**
   - Open DevTools → Network tab
   - Right-click on `/auth/login/callback` request
   - Select "Override content" or use Request Interception
   - Modify response to return 500 status

**Expected Error UI:**
- **Message:** "Server error"
- **Details:** "The server encountered an error. Please try again in a moment."
- **Button:** "Try Again" (visible)
- **Button:** "Continue to App" (visible)

**Pass Criteria:**
- ✅ Error UI displays correctly
- ✅ Error message indicates server issue
- ✅ "Try Again" button works
- ✅ "Continue to App" button works

**Cleanup:**
- Remove temporary code from backend
- Restart backend

---

### Test 5: Timeout Error (Slow Network)

**Purpose:** Test handling when request takes too long

**Steps:**
1. Open DevTools → Network tab
2. Set throttling to "Slow 3G" or "Offline"
3. Navigate to login page
4. Complete Auth0 login
5. **Wait:** Let the request timeout (10 seconds)
6. **Expected:** Timeout error UI should appear

**Expected Error UI:**
- **Message:** "Sign-in is taking longer than expected"
- **Details:** "The authentication process timed out. You can try again or continue."
- **Button:** "Try Again" (visible)
- **Button:** "Continue to App" (visible)

**Alternative Method:**
1. Open DevTools → Network tab
2. Find `/auth/login/callback` request
3. Right-click → "Block request URL"
4. Attempt authentication
5. Wait for timeout

**Pass Criteria:**
- ✅ Timeout error UI displays after 10 seconds
- ✅ Error message indicates timeout
- ✅ "Try Again" button works
- ✅ "Continue to App" button works

**Test Retry:**
1. Remove throttling/blocking
2. Click "Try Again"
3. **Expected:** Authentication should complete successfully

---

### Test 6: Missing Token Error

**Purpose:** Test handling when Auth0 doesn't provide token

**Steps:**
1. Open DevTools → Console
2. Navigate to login page
3. **Before** completing login, run this in console:
   ```javascript
   // Intercept getIdTokenClaims to return null
   // This requires access to Auth0 context
   // Alternative: Check what happens if token is missing
   ```
4. Complete Auth0 login
5. **Expected:** Error UI should appear if token is missing

**Expected Error UI:**
- **Message:** "Authentication token missing"
- **Details:** "Unable to retrieve your authentication token. Please try logging in again."
- **Button:** "Try Again" (visible)
- **Button:** "Continue to App" (visible)

**Pass Criteria:**
- ✅ Error UI displays correctly
- ✅ Error message indicates missing token
- ✅ "Try Again" button works
- ✅ "Continue to App" button works

---

### Test 7: Validation Error (400) - Invalid Request

**Purpose:** Test handling when request is invalid

**Steps:**
1. Open DevTools → Console
2. Navigate to login page
3. Complete Auth0 login
4. **In Network tab:** Intercept `/auth/login/callback` request
5. Modify request to send invalid data:
   - Remove `id_token` from body
   - Send malformed JSON
   - Send empty body

**Expected Error UI:**
- **Message:** "Invalid request"
- **Details:** "The authentication request was invalid. Please try logging in again."
- **Button:** "Try Again" (visible - but may not work)
- **Button:** "Continue to App" (visible)

**Pass Criteria:**
- ✅ Error UI displays correctly
- ✅ Error message indicates validation issue
- ✅ "Continue to App" button works

---

### Test 8: Retry Functionality

**Purpose:** Verify retry button works correctly

**Steps:**
1. Trigger any retryable error (network, timeout, server error)
2. Verify error UI appears
3. **Check:** "Try Again" button should be visible
4. Click "Try Again"
5. **Expected:**
   - Button should show "Retrying..."
   - Button should be disabled
   - Loading state should appear
   - Authentication should retry

**Test Scenarios:**
- **Network Error → Retry:** Disconnect, trigger error, reconnect, click retry
- **Timeout → Retry:** Block request, wait for timeout, unblock, click retry
- **Server Error → Retry:** Fix backend, click retry

**Pass Criteria:**
- ✅ Button shows "Retrying..." during retry
- ✅ Button is disabled during retry
- ✅ Authentication flow restarts
- ✅ Success case: Redirects correctly
- ✅ Failure case: Shows error again

---

### Test 9: Continue Functionality

**Purpose:** Verify continue button works correctly

**Steps:**
1. Trigger any error
2. Verify error UI appears
3. Click "Continue to App"
4. **Expected:** Navigate to home page (`/`)

**Test Scenarios:**
- **After Network Error:** Click continue → Should navigate
- **After Auth Error:** Click continue → Should navigate
- **After Server Error:** Click continue → Should navigate
- **After Timeout:** Click continue → Should navigate

**Pass Criteria:**
- ✅ Navigation works correctly
- ✅ User reaches home page
- ✅ App is functional (if backend is working)

---

### Test 10: Multiple Error Scenarios

**Purpose:** Test handling multiple errors sequentially

**Steps:**
1. Trigger network error
2. Click "Try Again"
3. If new error occurs (e.g., server error), verify new error UI appears
4. Click "Try Again" again
5. Test multiple retry cycles

**Test Scenarios:**
- **Network → Server:** Disconnect, retry, fix network but backend is down
- **Timeout → Network:** Block request, wait timeout, retry, disconnect
- **Auth → Server:** Invalid token, retry, fix token but server error

**Pass Criteria:**
- ✅ Error state updates correctly
- ✅ New error UI displays correctly
- ✅ Retry works across multiple errors
- ✅ Continue works at any point

---

### Test 11: Strava Callback Handling

**Purpose:** Verify Strava OAuth callback still works

**Steps:**
1. Complete Strava OAuth flow
2. **Expected:** Should redirect to `/setup?strava=connected`
3. **Check:** URL should have `?strava=connected` parameter
4. **Verify:** Setup page should handle the callback

**Pass Criteria:**
- ✅ Strava callback redirects correctly
- ✅ Query parameter is preserved
- ✅ Setup page handles callback

---

## 🎯 Testing Checklist

### Error Handling
- [ ] Network errors display correctly
- [ ] Authentication errors (401) display correctly
- [ ] Server errors (500+) display correctly
- [ ] Timeout errors display correctly
- [ ] Missing token errors display correctly
- [ ] Validation errors (400) display correctly
- [ ] Generic errors display correctly

### User Experience
- [ ] Error messages are clear and helpful
- [ ] Error details are informative
- [ ] Retry button is visible for retryable errors
- [ ] Retry button is hidden for non-retryable errors
- [ ] Continue button is always visible
- [ ] Loading states work correctly
- [ ] UI is responsive and accessible
- [ ] Error icon displays correctly

### Functionality
- [ ] Retry functionality works
- [ ] Continue functionality works
- [ ] Error recovery works
- [ ] Successful authentication works
- [ ] Strava callback handling preserved
- [ ] Cleanup on unmount works
- [ ] No memory leaks
- [ ] No console errors (except expected)

### Edge Cases
- [ ] Multiple retries work
- [ ] Continue after multiple errors works
- [ ] Rapid retry clicks don't break UI
- [ ] Component unmount during retry doesn't error
- [ ] Network reconnection during retry works

---

## 🐛 Debugging Tips

### Console Logs to Watch For
- `🔍 PostOAuth mounted →` - Component mounted
- `🪪 ID token → present/missing` - Token status
- `📡 Posting token to backend:` - Request starting
- `📡 /auth/login/callback → [status]` - Response status
- `❌ PostOAuth error [context]:` - Error occurred

### Network Tab Checks
- Check `/auth/login/callback` request:
  - Status code
  - Response body
  - Request payload
  - Timing

### Common Issues
1. **Error not showing:** Check console for errors
2. **Retry not working:** Check `isRetrying` state
3. **Continue not working:** Check navigation logic
4. **Timeout not triggering:** Check timeout value (10 seconds)

---

## 📝 Test Results Template

```
Test Date: ___________
Tester: ___________
Environment: [ ] Local [ ] Staging [ ] Production

Test 1: Successful Authentication
- [ ] Pass [ ] Fail
- Notes: _______________________________

Test 2: Network Error
- [ ] Pass [ ] Fail
- Notes: _______________________________

Test 3: Authentication Error (401)
- [ ] Pass [ ] Fail
- Notes: _______________________________

Test 4: Server Error (500+)
- [ ] Pass [ ] Fail
- Notes: _______________________________

Test 5: Timeout Error
- [ ] Pass [ ] Fail
- Notes: _______________________________

Test 6: Missing Token Error
- [ ] Pass [ ] Fail
- Notes: _______________________________

Test 7: Validation Error (400)
- [ ] Pass [ ] Fail
- Notes: _______________________________

Test 8: Retry Functionality
- [ ] Pass [ ] Fail
- Notes: _______________________________

Test 9: Continue Functionality
- [ ] Pass [ ] Fail
- Notes: _______________________________

Test 10: Multiple Error Scenarios
- [ ] Pass [ ] Fail
- Notes: _______________________________

Test 11: Strava Callback Handling
- [ ] Pass [ ] Fail
- Notes: _______________________________

Overall Status: [ ] Pass [ ] Fail
Issues Found: _______________________________
```

---

## ✅ Success Criteria

All tests should pass with:
- ✅ Error UI displays correctly for all error types
- ✅ Error messages are clear and helpful
- ✅ Retry button works for retryable errors
- ✅ Continue button always works
- ✅ No console errors (except expected ones)
- ✅ No UI breaking or freezing
- ✅ Smooth user experience

---

**Ready to test!** Follow the steps above and check off each test as you complete it.

# Quick Test Scenarios - PostOAuth Error Handling

**Date:** November 2025
**Quick Reference:** Fastest way to test each error scenario

---

## 🚀 Quick Test Setup

1. Open browser DevTools (F12)
2. Open Console tab
3. Open Network tab
4. Navigate to your app

---

## ⚡ Quick Tests (5 minutes each)

### Test 1: Network Error (Easiest)
1. DevTools → Network tab → Click "Offline" checkbox
2. Try to login
3. ✅ **Expected:** "Network connection failed" error
4. Click "Try Again" → Should work when online

### Test 2: Timeout Error (Easiest)
1. DevTools → Network tab → Set throttling to "Slow 3G"
2. Try to login
3. Wait 10+ seconds
4. ✅ **Expected:** "Sign-in is taking longer than expected" error

### Test 3: Server Error (Requires Backend)
1. Temporarily modify `auth0_routes.py`:
   ```python
   @auth0_bp.route("/login/callback", methods=["POST"])
   def login_callback():
       return error_response("Test error", status_code=500)
   ```
2. Restart backend
3. Try to login
4. ✅ **Expected:** "Server error" message
5. **Remember:** Remove test code after!

### Test 4: Retry Button
1. Trigger any error (network, timeout, etc.)
2. Click "Try Again"
3. ✅ **Expected:** Button shows "Retrying..." and is disabled
4. ✅ **Expected:** Authentication retries

### Test 5: Continue Button
1. Trigger any error
2. Click "Continue to App"
3. ✅ **Expected:** Navigates to home page

---

## 📋 One-Liner Test Checklist

```
☐ Network error shows correct message
☐ Timeout error shows after 10 seconds
☐ Retry button works and shows "Retrying..."
☐ Continue button navigates to home
☐ Error messages are clear and helpful
☐ UI looks professional
☐ No console errors
☐ Successful login still works
```

---

## 🎯 Priority Tests (Do These First)

1. **Network Error** - Easiest to test
2. **Retry Button** - Most important feature
3. **Continue Button** - Secondary feature
4. **Successful Login** - Baseline functionality

---

**Total Time:** ~20 minutes for priority tests

# Phase 0 Unit System Test Checklist

## Test Overview
This document outlines the test plan for Phase 0 of the unit system migration. Phase 0 establishes the foundation without changing any existing displays.

## Test Environment
- **Branch**: `dev` (or current feature branch)
- **Test Route**: `/unit-test` (temporary test page)
- **Navigation**: Profile dropdown → Unit toggle

---

## ✅ Test Checklist

### 1. Context & Provider Setup
- [ ] App loads without errors
- [ ] No console errors related to `UnitSystemContext`
- [ ] `UnitSystemProvider` is properly wrapped in `App.tsx`
- [ ] Context defaults to `imperial` if no preference saved

### 2. Navigation Toggle
- [ ] Profile dropdown opens when clicking user avatar
- [ ] Unit toggle section is visible in dropdown
- [ ] "Imperial" and "Metric" buttons are visible
- [ ] Active unit shows checkmark (✓) and blue background
- [ ] Clicking a unit button updates the selection
- [ ] Dropdown stays open after clicking a unit button (good UX)
- [ ] Visual feedback shows current selection ("Using miles, min/mi" or "Using km, min/km")
- [ ] Clicking outside dropdown closes it

### 3. localStorage Persistence
- [ ] Selecting "Imperial" saves to localStorage
- [ ] Selecting "Metric" saves to localStorage
- [ ] Refreshing page maintains the selected unit
- [ ] localStorage key: `smartcoach_unit_system`
- [ ] Clearing localStorage resets to default (imperial)

### 4. Unit Test Page (`/unit-test`)
- [ ] Navigate to `/unit-test` route
- [ ] Page loads without errors
- [ ] Current unit system displays correctly
- [ ] Toggle buttons work on test page
- [ ] Distance conversion: 5.0 mi → 8.0 km (metric)
- [ ] Pace conversion: 8:00 min/mi → 4:58 min/km (metric)
- [ ] Elevation conversion: 1000 ft → 305 m (metric)
- [ ] Race distances convert correctly
- [ ] All conversions update immediately when toggling

### 5. No Breaking Changes
- [ ] Metrics page still loads (`/metrics`)
- [ ] All existing displays show imperial units (expected)
- [ ] No console errors on any page
- [ ] Navigation works normally
- [ ] Settings page loads without errors
- [ ] No TypeScript errors
- [ ] No linting errors

### 6. Performance
- [ ] Toggle response is instant (< 100ms)
- [ ] No lag when switching units
- [ ] Context updates don't cause unnecessary re-renders
- [ ] localStorage operations are synchronous (no delay)

---

## Test Steps

### Manual Test Procedure

1. **Start the dev server:**
   ```bash
   cd frontend
   npm run dev
   ```

2. **Test Navigation Toggle:**
   - Log in to the app
   - Click on user profile avatar (top right)
   - Verify unit toggle section appears
   - Click "Metric" button
   - Verify checkmark appears and text updates
   - Click "Imperial" button
   - Verify it switches back
   - Click outside dropdown to close

3. **Test localStorage Persistence:**
   - Select "Metric" in navigation
   - Refresh the page (F5)
   - Verify "Metric" is still selected
   - Open browser DevTools → Application → Local Storage
   - Verify `smartcoach_unit_system` = `"metric"`

4. **Test Unit Test Page:**
   - Navigate to `/unit-test`
   - Verify all conversions display correctly
   - Toggle between Imperial and Metric
   - Verify all values update immediately
   - Check localStorage value updates

5. **Test No Breaking Changes:**
   - Navigate to `/metrics`
   - Verify page loads normally
   - Verify all displays show imperial (expected)
   - Check browser console for errors
   - Navigate to other pages (Settings, Plan, etc.)
   - Verify everything works normally

---

## Expected Results

### ✅ Success Criteria
- All checklist items pass
- No console errors
- Toggle works smoothly
- localStorage persists correctly
- No existing functionality broken

### ❌ Failure Criteria
- Console errors related to context
- Toggle doesn't work
- localStorage doesn't persist
- Existing pages break
- TypeScript/linting errors

---

## Cleanup After Testing

Once Phase 0 testing is complete:
1. Remove `/unit-test` route from `App.tsx`
2. Delete `frontend/src/components/UnitSystemTest.tsx`
3. Commit test results

---

## Notes

- **Phase 0 Goal**: Foundation only - no visual changes to existing displays
- **Next Phase**: Phase 1 will migrate actual metric displays to use unit system
- **Performance**: All conversions are O(1) operations, should be instant

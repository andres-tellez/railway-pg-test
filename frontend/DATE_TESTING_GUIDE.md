# Date Testing Guide

This guide explains how to test the date matching logic before deploying to ensure workouts appear on the correct days.

## Quick Start

### Option 1: Browser Console (Recommended)

1. Open your app in the browser
2. Open the browser console (F12)
3. Run the test suite:
   ```javascript
   window.dateTestUtils.runAllDateTests()
   ```
4. Or test with a specific date:
   ```javascript
   window.dateTestUtils.runAllDateTests('2024-11-12')
   ```

### Option 2: Test Page

1. Navigate to `/date-test` in your app
2. Select a test date (defaults to today)
3. Click "Run All Tests"
4. Check the browser console for detailed logs
5. Review the test results displayed on the page

## What Gets Tested

### 1. Date Matching Tests
- ✅ Date-only string matching (same day)
- ✅ Datetime string matching (same day, different time)
- ✅ Next day (should NOT match)
- ✅ Previous day (should NOT match)

### 2. Week Range Test
- ✅ Week starts on Monday (day 1)
- ✅ Week ends on Sunday (day 0)
- ✅ Correct date range calculation

### 3. Process Week Data Test
- ✅ Workouts match correct days
- ✅ Activities match workouts correctly
- ✅ Week days are created correctly

## Manual Testing Steps

### Step 1: Check Console Logs

When you load the homepage (`/home`), check the browser console for:

1. **Week Range Logs:**
   ```
   [Week Range] Today: 2024-11-12 Week Start: 2024-11-11 Week End: 2024-11-17
   [Week Range Debug] Today day of week: 2 Week start day: 1 Week end day: 0
   ```
   - Verify week start is Monday (day 1)
   - Verify week end is Sunday (day 0)

2. **Workout Dates Logs:**
   ```
   [Workout Dates] First 3 workouts: [{date: "2024-11-12", type: "Easy"}, ...]
   ```
   - Verify dates are in `YYYY-MM-DD` format
   - Verify dates match what's in the database

3. **Date Comparison Logs:**
   ```
   [Date Compare] Day: 2024-11-12 (Date object: 2024-11-12 00:00:00), Workout: 2024-11-12 (normalized: 2024-11-12), Match: true
   ```
   - Verify dates match correctly
   - Verify no timezone shifts occur

### Step 2: Visual Verification

1. Go to `/home`
2. Check that today's workout appears on today's date
3. Check that workouts appear on the correct days of the week
4. Verify completed workouts show checkmarks

### Step 3: Edge Case Testing

Test with different dates:
- Today's date
- Dates near week boundaries (Sunday/Monday)
- Dates in different months
- Dates in different years

```javascript
// Test with different dates
window.dateTestUtils.runAllDateTests('2024-11-10') // Sunday
window.dateTestUtils.runAllDateTests('2024-11-11') // Monday
window.dateTestUtils.runAllDateTests('2024-12-01') // Different month
```

## Understanding the Fix

### The Problem
Dates were shifting due to:
1. Time components in Date objects causing timezone conversions
2. `parseISO()` interpreting date-only strings as UTC
3. Week range calculation including time components

### The Solution
1. **Normalize all dates to date-only** (midnight local time, no time component)
2. **Use string comparison** for date matching (YYYY-MM-DD format)
3. **Avoid UTC conversions** by using `format()` instead of `toISOString()`
4. **Manual date parsing** instead of `parseISO()` for date-only strings

### Key Changes

**`getThisWeekRange()`:**
- Normalizes `today` to date-only before calculating week range
- Ensures week start/end are also date-only

**`processWeekData()`:**
- Normalizes each day to date-only before comparison
- Uses string comparison for date matching
- Enhanced logging for debugging

**`matchActivityToWorkout()`:**
- Extracts date part from datetime strings
- Uses manual date parsing (not `parseISO()`)
- Compares dates as local dates

## Troubleshooting

### Workouts Still Appearing on Wrong Day

1. **Check the console logs:**
   - Look for `[Date Compare]` logs
   - Verify the dates being compared
   - Check if there's a mismatch

2. **Verify API response:**
   - Check `[Workout Dates]` log
   - Verify dates are in `YYYY-MM-DD` format
   - Check if dates match database values

3. **Check timezone:**
   - Verify browser timezone settings
   - Check server timezone (if applicable)
   - Ensure dates are stored correctly in database

### Tests Failing

1. **Date Matching Tests Failing:**
   - Check if date strings are in correct format
   - Verify normalization function works correctly
   - Check for timezone issues

2. **Week Range Test Failing:**
   - Verify `startOfWeek` and `endOfWeek` are working correctly
   - Check if date normalization is applied
   - Verify day of week calculations

3. **Process Week Data Test Failing:**
   - Check if workouts are being matched correctly
   - Verify date comparison logic
   - Check for timezone shifts

## Production Checklist

Before deploying, verify:

- [ ] All tests pass in browser console
- [ ] Visual verification on homepage shows correct dates
- [ ] Console logs show correct date matching
- [ ] No timezone-related errors in console
- [ ] Workouts appear on correct days
- [ ] Completed workouts show correctly
- [ ] Week range is correct (Monday to Sunday)

## Additional Resources

- `frontend/src/utils/weekTimelineUtils.ts` - Core date logic
- `frontend/src/utils/dateTestUtils.ts` - Test utilities
- `frontend/src/pages/DateTestPage.tsx` - Test page component


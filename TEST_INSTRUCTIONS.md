# How to Test the Date Fix

## Option 1: Browser Console (Easiest)

1. **Start the dev server** (if not already running):
   ```powershell
   cd frontend
   npm run dev
   ```

2. **Open your browser** and navigate to your app (usually `http://localhost:5173`)

3. **Open the browser console** (F12 or Right-click → Inspect → Console tab)

4. **Run the tests**:
   ```javascript
   window.dateTestUtils.runAllDateTests()
   ```

5. **Or test with today's date**:
   ```javascript
   window.dateTestUtils.runAllDateTests('2024-11-12')
   ```

6. **Check the results** - you should see:
   - ✅ All date matching tests passed
   - ✅ Week range test passed
   - ✅ Process week data test passed

## Option 2: Test Page

1. **Start the dev server**:
   ```powershell
   cd frontend
   npm run dev
   ```

2. **Navigate to** `http://localhost:5173/date-test`

3. **Select a test date** (or use default)

4. **Click "Run All Tests"**

5. **Check both**:
   - The visual results on the page
   - The browser console for detailed logs

## Option 3: Manual Verification

1. **Go to the homepage** (`/home`)

2. **Open browser console** (F12)

3. **Look for these logs**:
   ```
   [Week Range] Today: 2024-11-12 Week Start: 2024-11-11 Week End: 2024-11-17
   [Week Range Debug] Today day of week: 2 Week start day: 1 Week end day: 0
   [Workout Dates] First 3 workouts: [...]
   [Date Compare] Day: 2024-11-12 ... Match: true/false
   ```

4. **Verify**:
   - Week start is Monday (day 1)
   - Week end is Sunday (day 0)
   - Workouts appear on the correct days
   - Today's workout shows on today's date

## Option 4: Node.js Test Script

If you want to test the logic without a browser:

```powershell
cd frontend
node test-date-logic.js
```

This will run basic date matching and week range tests.

## What to Look For

### ✅ Success Indicators:
- All tests pass
- Week starts on Monday (day 1)
- Week ends on Sunday (day 0)
- Workouts match correct dates
- No timezone shifts in console logs

### ❌ Failure Indicators:
- Tests fail
- Week doesn't start on Monday
- Workouts appear on wrong days
- Date mismatches in console logs
- Timezone-related errors

## Quick Test Commands

Once the app is running, you can test different scenarios:

```javascript
// Test with today
window.dateTestUtils.runAllDateTests()

// Test with a specific date (Tuesday)
window.dateTestUtils.runAllDateTests('2024-11-12')

// Test with Sunday (week boundary)
window.dateTestUtils.runAllDateTests('2024-11-10')

// Test with Monday (week boundary)
window.dateTestUtils.runAllDateTests('2024-11-11')

// Test individual functions
window.dateTestUtils.testDateMatching()
window.dateTestUtils.testWeekRange('2024-11-12')
window.dateTestUtils.testProcessWeekData('2024-11-12')
```

## Troubleshooting

If tests fail or dates are wrong:

1. **Check console logs** - Look for `[Date Compare]` logs to see what's being compared
2. **Verify API response** - Check `[Workout Dates]` log to see dates from backend
3. **Check timezone** - Ensure browser timezone matches your location
4. **Clear cache** - Try hard refresh (Ctrl+Shift+R) or clear browser cache


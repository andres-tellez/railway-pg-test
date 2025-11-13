# Commit Instructions

The git commands are getting stuck, likely due to pre-commit hooks. Here's how to commit manually:

## Option 1: Commit with hooks (recommended)

Run these commands in your terminal:

```powershell
git add frontend/src/utils/weekTimelineUtils.ts
git add frontend/src/pages/HomeScreen.tsx
git add frontend/src/utils/dateTestUtils.ts
git add frontend/src/pages/DateTestPage.tsx
git add frontend/src/App.tsx
git add frontend/DATE_TESTING_GUIDE.md
git add TEST_INSTRUCTIONS.md
git commit -m "Fix date timezone issues in week timeline - normalize all dates to date-only format"
```

## Option 2: Skip hooks (if hooks are causing issues)

```powershell
git add frontend/src/utils/weekTimelineUtils.ts
git add frontend/src/pages/HomeScreen.tsx
git add frontend/src/utils/dateTestUtils.ts
git add frontend/src/pages/DateTestPage.tsx
git add frontend/src/App.tsx
git add frontend/DATE_TESTING_GUIDE.md
git add TEST_INSTRUCTIONS.md
git commit --no-verify -m "Fix date timezone issues in week timeline - normalize all dates to date-only format"
```

## Files Changed

1. **frontend/src/utils/weekTimelineUtils.ts** - Fixed date normalization in `getThisWeekRange()` and `processWeekData()`
2. **frontend/src/pages/HomeScreen.tsx** - Added import for test utilities
3. **frontend/src/utils/dateTestUtils.ts** - New test utilities file
4. **frontend/src/pages/DateTestPage.tsx** - New test page component
5. **frontend/src/App.tsx** - Added route for test page
6. **frontend/DATE_TESTING_GUIDE.md** - Testing documentation
7. **TEST_INSTRUCTIONS.md** - Quick test instructions

## What the Fix Does

- Normalizes all dates to date-only format (no time component)
- Prevents timezone shifts when comparing dates
- Ensures workouts appear on the correct days
- Adds comprehensive logging for debugging


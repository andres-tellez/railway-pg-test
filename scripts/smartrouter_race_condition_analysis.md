# SmartRouter Race Condition Analysis

## The Problem

**Local**: After Strava OAuth → Shows setup page with Step 1 complete, Step 2 visible
**Staging**: After Strava OAuth → Goes directly to profile form (`/onboarding`)

## Root Cause: Race Condition in SmartRouter

### Current Flow (After Strava OAuth):

1. **Backend redirects** to: `FRONTEND_REDIRECT?strava=connected`

   - Line 188 in `auth_routes.py`: `return redirect(f"{frontend_redirect}?strava=connected")`

2. **SmartRouter detects** `?strava=connected`:

   - Line 38-41: Redirects to `/setup?strava=connected`
   - This should preserve the query param

3. **BUT THEN SmartRouter ALSO checks user state**:
   - Line 52: Calls `/user` API to get `hasOnboarded` and `hasStrava`
   - Line 61-64: **If `hasStrava=true` but `hasOnboarded=false` → redirects to `/onboarding`**

### The Race Condition:

When Strava OAuth completes:

- ✅ Backend stores tokens immediately (user now has Strava)
- ✅ Backend redirects to frontend with `?strava=connected`
- ⚠️ SmartRouter checks `/user` API
- ⚠️ API returns `hasStrava=true` (because tokens were just stored)
- ❌ SmartRouter sees `hasStrava=true` → redirects to `/onboarding`
- ❌ Setup page never gets a chance to render

### Why Local vs Staging Differ:

1. **Timing**: Local might be slower (network latency), allowing setup page to render briefly
2. **FRONTEND_REDIRECT**: Staging might have different `FRONTEND_REDIRECT` value
3. **API Response Speed**: Staging API might be faster, completing the check before setup page renders

## The Fix

**SmartRouter should skip the `hasStrava` check when `?strava=connected` is present:**

```typescript
// Check if we're handling a Strava OAuth callback
const params = new URLSearchParams(window.location.search);
if (params.get("strava") === "connected") {
  console.log(
    "🔄 Strava OAuth callback detected - redirecting to /setup to show consent completion"
  );
  navigate("/setup?strava=connected", { replace: true });
  return; // ✅ RETURN EARLY - don't check user state
}
```

Currently, the code redirects to `/setup?strava=connected` but then **continues** to check user state, which causes the redirect to `/onboarding`.

## Solution

Modify `SmartRouter.tsx` to **return early** when `?strava=connected` is detected, preventing the user state check from running.

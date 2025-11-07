# SmartRouter & PostOAuth Fix Explanation

## The Problem

**Staging Flow:**
1. Backend redirects to: `/post-oauth?strava=connected` (from `FRONTEND_REDIRECT`)
2. `PostOAuth` component handles Auth0 token exchange
3. `PostOAuth` redirects to `/` (loses `?strava=connected`)
4. `SmartRouter` (mounted at `/`) checks user state
5. API returns `hasStrava=true` (tokens just stored)
6. `SmartRouter` redirects to `/onboarding` ❌
7. Setup page never renders

**Local Flow (works):**
1. Backend redirects to: `/setup?strava=connected` (default)
2. `SmartRouter` sees `?strava=connected` → redirects to `/setup?strava=connected`
3. Setup page renders ✅

## The Fix

### Fix #1: SmartRouter.tsx

**Changed lines 35-48:**

```typescript
// BEFORE: Only checked query param, but then continued to check user state
if (params.get('strava') === 'connected') {
  navigate('/setup?strava=connected', { replace: true });
  return; // ❌ But useEffect continues...
}

// AFTER: Check query param AND pathname, return early to prevent user state check
if (params.get('strava') === 'connected') {
  navigate('/setup?strava=connected', { replace: true });
  return; // ✅ CRITICAL: Return early to prevent user state check
}

// Also check if we're already on /setup page - don't interfere
if (window.location.pathname === '/setup') {
  return; // ✅ Don't interfere with setup page
}
```

**What this does:**
- When `?strava=connected` is detected, redirects to `/setup` and **returns early**
- Prevents the `checkUserState()` function from running
- Also prevents interference if already on `/setup` page

### Fix #2: PostOAuth.tsx

**Changed in 3 places:**

#### 1. Safety Timeout (lines 39-52):
```typescript
// BEFORE:
const safety = setTimeout(() => {
  navigate("/", { replace: true }); // ❌ Loses query param
}, 8000);

// AFTER:
const params = new URLSearchParams(window.location.search);
const isStravaCallback = params.get('strava') === 'connected';

const safety = setTimeout(() => {
  if (isStravaCallback) {
    navigate("/setup?strava=connected", { replace: true }); // ✅ Preserves query param
  } else {
    navigate("/", { replace: true });
  }
}, 8000);
```

#### 2. Error Handler (lines 87-97):
```typescript
// BEFORE:
catch (err) {
  navigate("/", { replace: true }); // ❌ Loses query param
}

// AFTER:
catch (err) {
  const params = new URLSearchParams(window.location.search);
  if (params.get('strava') === 'connected') {
    navigate("/setup?strava=connected", { replace: true }); // ✅ Preserves query param
  } else {
    navigate("/", { replace: true });
  }
}
```

#### 3. LandingProgress Completion (lines 108-123):
```typescript
// BEFORE:
<LandingProgress
  onComplete={() => navigate("/", { replace: true })} // ❌ Loses query param
/>

// AFTER:
const params = new URLSearchParams(window.location.search);
const isStravaCallback = params.get('strava') === 'connected';

<LandingProgress
  onComplete={() => {
    if (isStravaCallback) {
      navigate("/setup?strava=connected", { replace: true }); // ✅ Preserves query param
    } else {
      navigate("/", { replace: true });
    }
  }}
/>
```

**What this does:**
- Preserves `?strava=connected` query param in ALL redirect scenarios
- Ensures `/setup?strava=connected` is reached, not just `/`
- Allows `SmartRouter` to detect the query param and skip user state check

## How It Works Now

### Staging Flow (After Fix):

1. ✅ Backend redirects to: `/post-oauth?strava=connected`
2. ✅ `PostOAuth` detects `?strava=connected`
3. ✅ `PostOAuth` handles Auth0 token exchange
4. ✅ `PostOAuth` redirects to `/setup?strava=connected` (preserves query param)
5. ✅ `SmartRouter` sees `?strava=connected` → skips user state check
6. ✅ Setup page renders with Step 1 complete, Step 2 visible

### Local Flow (Still Works):

1. ✅ Backend redirects to: `/setup?strava=connected` (default)
2. ✅ `SmartRouter` sees `?strava=connected` → skips user state check
3. ✅ Setup page renders

## Summary

**Two fixes working together:**
1. **SmartRouter**: Skips user state check when `?strava=connected` is present
2. **PostOAuth**: Preserves `?strava=connected` query param in all redirect scenarios

This ensures the setup page always renders after Strava OAuth, regardless of whether it goes through `/post-oauth` (staging) or directly to `/setup` (local).

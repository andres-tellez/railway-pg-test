# Frontend Authentication Architecture

## Overview

This document defines the architectural guardrails and best practices for authentication in the SmartCoach frontend application. It establishes the centralized authentication mechanism as the single source of truth and provides clear guidelines to prevent code duplication and authentication drift.

## 🎯 Core Principle

**There is ONE and ONLY ONE centralized authentication mechanism. All pages MUST use this mechanism - no exceptions, no shortcuts, no individual implementations.**

## ✅ Centralized Authentication Mechanism

### Components

The centralized authentication consists of two core components:

#### 1. `useAuthSetup` Hook
**Location:** `frontend/src/hooks/useAuthSetup.ts`

**Purpose:** Ensures user identity is created and ready before making API calls.

**Responsibilities:**
- Calls `POST /user/identity` to create backend user identity
- Returns consistent `userId`
- Provides `isReady` flag to handle race conditions
- Handles authentication errors gracefully

**Usage:**
```typescript
const { isReady, userId, error } = useAuthSetup();
```

#### 2. `AuthGuard` Component
**Location:** `frontend/src/components/AuthGuard.tsx`

**Purpose:** Centralizes all authentication logic and UI states.

**Responsibilities:**
- Handles loading states (Auth0 SDK initialization)
- Manages authentication status checks
- Displays error states
- Waits for identity setup completion
- Renders children only when authenticated and ready

**Usage:**
```typescript
return (
  <AuthGuard>
    {/* Your page content */}
  </AuthGuard>
);
```

## 📋 Implementation Pattern

### Standard Page Implementation

Every authenticated page MUST follow this exact pattern:

```typescript
import { useAuthSetup } from '@/hooks/useAuthSetup';
import { AuthGuard } from '@/components/AuthGuard';
import { useApiClient } from '@/utils/apiClient';

export default function MyPage() {
  // 1. Get auth state from centralized hook
  const { isReady, userId } = useAuthSetup();
  const api = useApiClient();

  // 2. Gate API calls with auth readiness
  useEffect(() => {
    if (!isReady || !userId) return; // ✅ Critical guard

    const fetchData = async () => {
      // Your API calls here
    };

    fetchData();
  }, [isReady, userId, api]); // ✅ Must depend on auth setup

  // 3. Wrap return JSX with AuthGuard
  return (
    <AuthGuard>
      {/* Your page content */}
    </AuthGuard>
  );
}
```

## 🚫 Architectural Prohibitions

### ❌ NEVER Do These Things

1. **Do NOT import `useAuth0` directly in page components**
   ```typescript
   // ❌ WRONG
   import { useAuth0 } from '@auth0/auth0-react';
   const { isLoading, isAuthenticated } = useAuth0();
   ```

2. **Do NOT create individual authentication wrappers**
   ```typescript
   // ❌ WRONG
   function MyPage() {
     if (isLoading) return <div>Loading...</div>;
     if (!isAuthenticated) return <div>Not authenticated</div>;
     // ...
   }
   ```

3. **Do NOT duplicate authentication logic**
   ```typescript
   // ❌ WRONG
   useEffect(() => {
     if (!isAuthenticated) {
       navigate('/login');
     }
   }, [isAuthenticated]);
   ```

4. **Do NOT create custom ProtectedRoute wrappers**
   ```typescript
   // ❌ WRONG
   <ProtectedRoute>
     <MyPage />
   </ProtectedRoute>
   ```

5. **Do NOT bypass the centralized mechanism**
   ```typescript
   // ❌ WRONG
   if (!user) return <LoginPrompt />;
   ```

## ✅ Approved Exceptions

The following components are EXCEPTIONS that may use `useAuth0` directly:

### 1. `LoginPage` Component
**File:** `frontend/src/App.tsx`

**Reason:** Handles the login flow and needs direct access to `loginWithRedirect` and `isAuthenticated` for routing decisions.

**Usage:**
```typescript
function LoginPage() {
  const { loginWithRedirect, isAuthenticated, isLoading } = useAuth0();
  // ... login-specific logic
}
```

### 2. `SmartRouter` Component
**File:** `frontend/src/components/SmartRouter.tsx`

**Reason:** Performs routing-level authentication checks before page components mount.

**Usage:**
```typescript
const SmartRouter: React.FC = () => {
  const { isAuthenticated, isLoading: authLoading } = useAuth0();
  // ... routing logic
};
```

### 3. `Navigation` Component
**File:** `frontend/src/components/Navigation.tsx`

**Reason:** Displays conditional UI (logout button) based on authentication status.

**Usage:**
```typescript
const { user, logout, isAuthenticated } = useAuth0();
// ... navigation UI logic
```

### 4. OAuth Callback Handlers
**Files:** `PostOAuth.tsx`, `AuthCallbackHandler.tsx`

**Reason:** Handle Auth0 OAuth redirect flows and require direct token access.

**Usage:**
```typescript
const { getIdTokenClaims, isLoading, isAuthenticated } = useAuth0();
// ... OAuth callback logic
```

### 5. `AuthTestPage` Component
**File:** `frontend/src/pages/AuthTestPage.tsx`

**Reason:** Displays authentication state for debugging and testing purposes.

**Usage:**
```typescript
const { isAuthenticated, isLoading, user } = useAuth0();
// ... display auth state
```

## 📊 Page Compliance Checklist

Every new page MUST meet these criteria:

- [ ] Imports `useAuthSetup` from `@/hooks/useAuthSetup`
- [ ] Imports `AuthGuard` from `@/components/AuthGuard`
- [ ] Calls `useAuthSetup()` to get `isReady` and `userId`
- [ ] Guards all API calls with `if (!isReady || !userId) return;`
- [ ] Includes `isReady` and `userId` in `useEffect` dependencies
- [ ] Wraps return JSX with `<AuthGuard>...</AuthGuard>`
- [ ] Does NOT import `useAuth0` directly
- [ ] Does NOT implement custom authentication logic

## 🔍 Verification Process

### Before Adding New Pages

1. Check existing pages for pattern compliance
2. Reference this document for guidance
3. Use the standard implementation pattern
4. Test authentication flow (login, logout, refresh)
5. Verify no linter errors

### Code Review Checklist

When reviewing authentication-related code:

- [ ] Does this use the centralized auth mechanism?
- [ ] Is `AuthGuard` wrapping the page content?
- [ ] Are API calls properly gated with auth guards?
- [ ] Is this following the approved exception list?
- [ ] Will this create authentication drift?

## 🎯 Benefits of Centralized Authentication

### 1. Single Source of Truth
- All authentication logic lives in one place
- Changes propagate automatically to all pages
- No conflicting implementations

### 2. Reduced Code Duplication
- No repeated auth checks in every page
- Consistent loading and error states
- Easier maintenance

### 3. Better Error Handling
- Centralized error management
- Consistent user experience
- Easier debugging

### 4. Type Safety
- Consistent `userId` type across app
- Centralized error types
- Better TypeScript inference

### 5. Performance
- Single auth setup per page load
- Efficient caching of auth state
- Optimal re-render patterns

## 🚨 Compliance Enforcement

### Code Review Process

All authentication-related code MUST be reviewed for compliance with this architecture. Non-compliant code will be rejected with a reference to this document.

### Linter Checks

The following linter rules help enforce compliance:

- No direct `useAuth0` imports in page components (except exceptions)
- Required use of `AuthGuard` wrapper
- Required auth guards before API calls

### Documentation Updates

When adding new exceptions to the approved list:

1. Document the exception in this file
2. Explain the rationale
3. Provide usage example
4. Update the implementation pattern

## 📚 Related Documentation

- `AUTH_AUDIT.md` - Authentication audit and migration status
- `FRONTEND_AUTH_INTEGRATION_STATUS.md` - Integration progress tracking
- `PLAN_CREATION_FLOW.md` - User flow documentation
- `src/hooks/useAuthSetup.ts` - Hook implementation
- `src/components/AuthGuard.tsx` - Component implementation

## 🔄 Migration Guide

### Migrating Existing Pages

1. Remove direct `useAuth0` imports
2. Import `useAuthSetup` and `AuthGuard`
3. Replace auth checks with `useAuthSetup`
4. Wrap JSX with `<AuthGuard>`
5. Gate API calls with auth guards
6. Test thoroughly

### Example Migration

**Before:**
```typescript
import { useAuth0 } from '@auth0/auth0-react';

function MyPage() {
  const { isAuthenticated, isLoading, user } = useAuth0();

  if (isLoading) return <div>Loading...</div>;
  if (!isAuthenticated) return <div>Not authenticated</div>;

  useEffect(() => {
    fetchData();
  }, []);

  return <div>Content</div>;
}
```

**After:**
```typescript
import { useAuthSetup } from '@/hooks/useAuthSetup';
import { AuthGuard } from '@/components/AuthGuard';

function MyPage() {
  const { isReady, userId } = useAuthSetup();

  useEffect(() => {
    if (!isReady || !userId) return;
    fetchData();
  }, [isReady, userId]);

  return (
    <AuthGuard>
      <div>Content</div>
    </AuthGuard>
  );
}
```

## 📞 Support

For questions or clarification about the authentication architecture:

1. Review this document first
2. Check existing implementations for patterns
3. Refer to approved exceptions list
4. Consult the team for edge cases

---

**Document Version:** 1.0
**Last Updated:** 2025-01-28
**Maintained By:** Frontend Architecture Team

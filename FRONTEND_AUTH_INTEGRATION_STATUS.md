# Frontend Auth Integration Status

## ✅ Completed Pages (Using AuthGuard)

1. **MyPlan.tsx** - ✅ Fully integrated
2. **PlanPage.tsx** - ✅ Fully integrated
3. **OnboardingForm.tsx** - ✅ Fully integrated

## ⚠️ Needs Manual Integration

### SimpleMetrics.tsx

**Status**: File is too large (667 lines) for automated edits. Structure was broken.

**What needs to be done manually**:

1. Add imports at top:

   ```typescript
   import { useAuthSetup } from "../hooks/useAuthSetup";
   import { AuthGuard } from "../components/AuthGuard";
   ```

2. Add hook call inside component:

   ```typescript
   export default function SimpleMetrics() {
     const { isReady, userId } = useAuthSetup(); // ✅ Centralized auth
     const api = useApiClient();
     // ... rest
   ```

3. Add auth check in useEffect:

   ```typescript
   useEffect(() => {
     if (!isReady || !userId) return; // ✅ Wait for auth setup
     // ... existing code
   }, [isReady, userId, api]); // ✅ Depend on auth setup
   ```

4. Wrap return statement:
   ```typescript
   return (
     <AuthGuard>
       <div className="min-h-screen bg-gray-50 p-6">
         {/* existing content */}
       </div>
     </AuthGuard>
   );
   ```

## 📋 Remaining Pages to Update

### GYRMetricsDemo.tsx

- Add `useAuthSetup` hook
- Add AuthGuard wrapper
- Update useEffect dependencies

### Admin.tsx

- Add `useAuthSetup` hook
- Add AuthGuard wrapper
- Update useEffect dependencies

## Pattern to Follow

For all remaining pages:

```typescript
// 1. Add imports
import { useAuthSetup } from "../hooks/useAuthSetup";
import { AuthGuard } from "../components/AuthGuard";

// 2. Add hook in component
const { isReady, userId } = useAuthSetup();

// 3. Gate API calls with auth
useEffect(() => {
  if (!isReady || !userId) return;
  // ... API calls
}, [isReady, userId, api]);

// 4. Wrap return with AuthGuard
return <AuthGuard>{/* existing JSX */}</AuthGuard>;
```

## Benefits

- ✅ Single source of truth for auth UI
- ✅ No code duplication
- ✅ Consistent UX across pages
- ✅ Easy to maintain

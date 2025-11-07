# React useEffect Best Practices - Preventing Infinite Loops

## 🚨 Common Pitfalls

### ❌ Problem: Including Non-Stable References

```typescript
const api = useApiClient();
const data = { key: "value" };

useEffect(() => {
  api.get("/endpoint");
}, [api]); // ❌ api changes on every render!
```

### ✅ Solution 1: Don't Include Stable References (Recommended)

```typescript
const api = useApiClient();

useEffect(() => {
  api.get("/endpoint");
}, []); // ✅ Empty array for one-time execution

// OR

useEffect(() => {
  if (!isReady) return;
  api.get("/endpoint");
}, [isReady]); // ✅ Only depend on actual data that triggers re-runs
```

### ✅ Solution 2: Memoize Unstable References

```typescript
const api = useMemo(() => createApiClient(), []);
const data = useMemo(() => ({ key: "value" }), []);

useEffect(() => {
  api.get("/endpoint", data);
}, [api, data]); // ✅ Now safe to include - they're stable
```

## 📋 Dependency Array Rules

### ✅ SAFE to Include:

- Primitive values: `string`, `number`, `boolean`
- State variables from `useState`
- Props passed from parent
- Values from `useMemo` or `useCallback`
- Stable IDs (user IDs, IDs from auth)

### ❌ UNSAFE to Include:

- Objects created inline: `{ key: 'value' }`
- Arrays created inline: `[1, 2, 3]`
- Functions created inline: `() => {}`
- API clients not memoized
- Values from hooks that return new instances each render

## 🔍 Common Patterns in This Codebase

### Pattern 1: API Calls with Auth

```typescript
const { isReady, userId } = useAuthSetup();
const api = useApiClient();

useEffect(() => {
  if (!isReady || !userId) return;
  api.get("/user");
}, [isReady, userId]); // ✅ Don't include api
```

### Pattern 2: Fetch on Mount

```typescript
const api = useApiClient();

useEffect(() => {
  api.get("/data");
}, []); // ✅ Empty array - runs once on mount
```

### Pattern 3: Polling or Interval

```typescript
const [interval, setInterval] = useState(5000);

useEffect(() => {
  const timer = setInterval(() => {
    api.get("/data");
  }, interval);

  return () => clearInterval(timer);
}, [interval]); // ✅ Only depend on interval value
```

## 🛡️ Preventive Measures

1. **Always ask**: "Do I really need this in the dependency array?"
2. **Use ESLint**: Install `eslint-plugin-react-hooks` to catch violations
3. **Test thoroughly**: Infinite loops usually happen in production
4. **Add guards**: Check `isReady`, `userId`, etc. before making API calls
5. **Use refs**: For values that shouldn't trigger re-runs

```typescript
const ran = useRef(false);

useEffect(() => {
  if (ran.current) return;
  ran.current = true;

  // One-time initialization
}, []);
```

## 📝 Quick Reference

| Situation             | Dependency Array         | Example                     |
| --------------------- | ------------------------ | --------------------------- |
| Run once on mount     | `[]`                     | Initialize data             |
| Run when auth ready   | `[isReady, userId]`      | Fetch user data             |
| Run when data changes | `[data.id, data.status]` | Refetch on ID/status change |
| Run on cleanup        | `return () => {}`        | Clear timers, subscriptions |

## ✅ Checklist Before Committing

- [ ] Are all dependencies in the array actually needed?
- [ ] Are objects/functions memoized if included?
- [ ] Is there a guard clause (if/early return) for conditional execution?
- [ ] Have I tested that the effect doesn't run indefinitely?
- [ ] Did I check the browser console for infinite request warnings?

# Production Environment Variables Verification Checklist

## Frontend Production Variables Investigation

### ✅ Variable 1: `VITE_AUTH0_DOMAIN`
**Current Value:** `dev-ppz6v1x0u18obr81.us.auth0.com`

**Expected:** Same Auth0 tenant for staging and production
**Used in:** `frontend/src/auth/AuthProvider.tsx` - Auth0Provider domain prop
**Verification:**
- [x] Should match staging (both use same Auth0 app)
- [x] Should match Auth0 Dashboard → Applications → Your App → Domain
- [x] **Status: ✅ CORRECT** - This is your Auth0 domain, should be same for all environments

---

### ✅ Variable 2: `VITE_AUTH0_CLIENT_ID`
**Current Value:** `qcD3RetLx160YCVAzEHvmccSbYozk21N`

**Expected:** Same Client ID for staging and production (single Auth0 app)
**Used in:** `frontend/src/auth/AuthProvider.tsx` - Auth0Provider clientId prop
**Verification:**
- [ ] Should match staging
- [ ] Should match Auth0 Dashboard → Applications → Your App → Client ID
- [ ] **Status: ⚠️ VERIFY** - Check if this matches staging and Auth0 dashboard

---

### ✅ Variable 3: `VITE_AUTH0_REDIRECT_URI`
**Current Value:** `https://www.smartcoach.dev/post-oauth`

**Expected:** Production callback URL
**Used in:** `frontend/src/auth/AuthProvider.tsx` - authorizationParams.redirect_uri
**Critical:** This must match EXACTLY what's in Auth0's "Allowed Callback URLs"
**Verification:**
- [x] Should be `https://www.smartcoach.dev/post-oauth` for production
- [x] Should be in Auth0 → Applications → Allowed Callback URLs (you confirmed this)
- [ ] **Status: ⚠️ NEEDS REBUILD** - Must rebuild frontend for this to take effect (Vite embeds at build time)

---

### ✅ Variable 4: `VITE_AUTH0_AUDIENCE`
**Current Value:** `https://api.smartcoach.dev`

**Expected:** API identifier (same for staging and production)
**Used in:** `frontend/src/auth/AuthProvider.tsx` - authorizationParams.audience
**Verification:**
- [ ] Should match staging
- [ ] Should match Auth0 Dashboard → APIs → Your API → Identifier
- [ ] **Status: ⚠️ VERIFY** - Check if staging uses same value

---

### ✅ Variable 5: `VITE_BACKEND_URL`
**Current Value:** `https://api.prod.smartcoach.dev`

**Expected:** Production backend API URL
**Used in:**
- `frontend/src/utils/apiClient.ts` - Axios baseURL
- `frontend/src/pages/PostOAuth.tsx` - Backend API calls
- `frontend/src/hooks/useStravaSetup.ts` - API base URL

**Verification:**
- [x] Should point to production backend: `https://api.prod.smartcoach.dev`
- [ ] Should match your Railway `backend-prod` service domain
- [ ] **Status: ⚠️ VERIFY** - Confirm `api.prod.smartcoach.dev` is correct production backend

---

## Next Steps

1. **Check Staging Variables** - Compare each variable with staging to ensure consistency (except URLs which should differ)
2. **Verify Auth0 Dashboard** - Confirm Client ID and Audience match Auth0 settings
3. **Rebuild Frontend** - After confirming all variables, rebuild frontend so they're embedded in the build
4. **Test Authentication** - Try logging in after rebuild completes

---

## Common Issues

- **403 Forbidden:** Usually means `VITE_AUTH0_REDIRECT_URI` doesn't match Auth0's allowed callbacks (but you already added it)
- **Build-time embedding:** Vite embeds `VITE_*` vars at build time - must rebuild after changing
- **Cache issues:** Browser cache might serve old JavaScript - clear cache or use incognito

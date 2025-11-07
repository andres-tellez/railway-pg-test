# Session Cookie Variables Analysis

## Current Variables

| Variable | Value | Used? | Reason |
|----------|-------|-------|--------|
| `SESSION_COOKIE_DOMAIN` | `app.smartcoach.dev` | ✅ **YES** | Used in code |

## Code Analysis

### SESSION_COOKIE_DOMAIN ✅ NEEDED

**Used in:**
- `src/app.py` line 110: `SESSION_COOKIE_DOMAIN=os.getenv("SESSION_COOKIE_DOMAIN")`
- `src/routes/auth_routes.py` line 373: `domain=os.getenv("SESSION_COOKIE_DOMAIN")`

**Purpose:**
- Allows cookies to be shared across subdomains
- Frontend: `app.smartcoach.dev`
- Backend: `api.smartcoach.dev`
- Setting domain to `.smartcoach.dev` or `app.smartcoach.dev` enables cookie sharing

**Why it's needed:**
- Cross-domain authentication requires cookies to work across subdomains
- Without this, cookies won't be sent from `app.smartcoach.dev` to `api.smartcoach.dev`

**Note:** Other session cookie settings (`SESSION_COOKIE_SAMESITE` and `SESSION_COOKIE_SECURE`) are hardcoded in the application code and don't require environment variables.

## Summary

| Variable | Action | Impact |
|----------|--------|--------|
| `SESSION_COOKIE_DOMAIN` | ✅ **KEEP** | Required for cross-domain cookies |

## Recommendation

**Keep:**
- `SESSION_COOKIE_DOMAIN=app.smartcoach.dev` (or `.smartcoach.dev` for all subdomains)

**Note:** Session cookie security settings (`SameSite=None` and `Secure=True`) are hardcoded in the application code and are correct for production. No environment variables are needed for these settings.

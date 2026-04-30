# API Documentation

**Date:** March 2026 (activity / SmartCoach analyze-run section added)
**Status:** In Progress
**Base URL:** `https://api.smartcoach.dev` (production) / `https://localhost:5000` (local)

---

## Authentication

All API endpoints (except `/health` and `/auth/login/callback`) require authentication via JWT token.

### Authentication Header

```
Authorization: Bearer <JWT_TOKEN>
```

The JWT token is obtained from Auth0 after user login and is passed in the `Authorization` header.

---

## Authentication Endpoints

### POST /auth/login/callback

**Description:** Handles Auth0 login callback and creates user identity.

**Rate Limit:** 10 requests per 5 minutes per IP

**Request:**
```json
{
  "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
- **200**: Redirect to frontend
- **400**: Missing or invalid id_token
- **401**: Invalid token
- **429**: Rate limit exceeded

**Error Response:**
```json
{
  "error": "Missing id_token",
  "status": 400,
  "error_code": "VALIDATION_ERROR",
  "details": {
    "field": "id_token"
  }
}
```

---

### GET /auth/strava-login

**Description:** Initiates Strava OAuth flow.

**Rate Limit:** 10 requests per 5 minutes per IP

**Query Parameters:**
- `user_id` (optional): Fallback user identifier if cookie not available

**Response:**
- **302**: Redirect to Strava OAuth
- **500**: Configuration error

---

### GET /auth/strava/callback

**Description:** Handles Strava OAuth callback (browser redirect).

**Rate Limit:** 10 requests per 5 minutes per IP

**Query Parameters:**
- `code` (required): Authorization code from Strava
- `state` (required): State parameter (usually auth0_sub)

**Response:**
- **302**: Redirect to frontend with `?strava=connected`
- **400**: Missing code or state
- **500**: Failed to process callback
- **429**: Rate limit exceeded

---

### POST /auth/strava/callback

**Description:** Handles Strava OAuth callback (API exchange).

**Rate Limit:** 10 requests per 5 minutes per IP

**Request:**
```json
{
  "code": "strava_auth_code",
  "sub": "auth0|user-id"
}
```

**Response:**
```json
{
  "status": "success",
  "user_id": "uuid-123",
  "athlete_id": 347085
}
```

**Error Response:**
```json
{
  "error": "Missing code or sub",
  "status": 400,
  "error_code": "VALIDATION_ERROR",
  "details": {
    "errors": {
      "code": "required",
      "sub": "required"
    }
  }
}
```

---

### POST /auth/refresh/<athlete_id>

**Description:** Force refresh Strava tokens if expired.

**Rate Limit:** 30 requests per 15 minutes per IP

**Authentication:** Required (Bearer token)

**Response:**
```json
{
  "refreshed": true
}
```

**Error Response:**
- **401**: Unauthorized (missing or invalid token)
- **429**: Rate limit exceeded
- **500**: Failed to refresh token

---

### POST /auth/logout/<athlete_id>

**Description:** Logout athlete by deleting stored Strava tokens.

**Authentication:** Required (Bearer token)

**Response:**
```json
{
  "deleted": true
}
```

---

## User Identity Endpoints

### GET /api/user/identity

**Description:** Get user identity information.

**Authentication:** Required (Bearer token)

**Response:**
```json
{
  "status": 200,
  "data": {
    "user_id": "uuid-123",
    "email": "user@example.com",
    "name": "John Doe",
    "picture": "https://...",
    "email_verified": true,
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:00:00Z"
  }
}
```

**Error Response:**
- **400**: Missing sub claim in token
- **404**: User not found
- **401**: Unauthorized

---

### POST /api/user/identity

**Description:** Create or update user identity.

**Authentication:** Required (Bearer token)

**Request:**
```json
{}
```

**Response:**
```json
{
  "status": 200,
  "data": {
    "user_id": "uuid-123"
  }
}
```

**Error Response:**
- **400**: Missing sub claim in token
- **401**: Unauthorized

---

### GET /api/user

**Description:** Get user info with onboarding and Strava connection status.

**Authentication:** Required (Bearer token)

**Response:**
```json
{
  "status": 200,
  "data": {
    "name": "John Doe",
    "email": "user@example.com",
    "picture": "https://...",
    "hasOnboarded": true,
    "hasStrava": true
  }
}
```

**Error Response:**
- **400**: Missing sub claim in token
- **404**: User not found
- **401**: Unauthorized

---

### GET /api/me

**Description:** Get canonical user view (creates identity if missing).

**Authentication:** Required (Bearer token)

**Response:**
```json
{
  "status": 200,
  "data": {
    "user_id": "uuid-123"
  }
}
```

**Error Response:**
- **400**: Missing sub claim in token
- **401**: Unauthorized

---

## User-Athlete Linking Endpoints

### GET /api/user/link

**Description:** Get user-athlete link status.

**Authentication:** Required (Bearer token)

**Response:**
```json
{
  "status": 200,
  "data": {
    "linked": true,
    "user_id": "uuid-123",
    "athlete_id": 347085
  }
}
```

**Error Response:**
- **400**: Missing sub claim in token
- **404**: User-athlete link not found

---

### POST /api/user/link

**Description:** Link user to Strava athlete.

**Authentication:** Required (Bearer token)

**Request:**
```json
{
  "athlete_id": 347085
}
```

**Response:**
```json
{
  "status": 201,
  "data": {
    "linked": true,
    "user_id": "uuid-123",
    "athlete_id": 347085
  }
}
```

**Error Response:**
- **400**: Missing sub claim or invalid athlete_id
- **409**: User or athlete already linked
- **401**: Unauthorized

---

### DELETE /api/user/link

**Description:** Unlink user from Strava athlete.

**Authentication:** Required (Bearer token)

**Response:**
```json
{
  "status": 200,
  "data": {
    "deleted": true
  }
}
```

**Error Response:**
- **400**: Missing sub claim in token
- **404**: User-athlete link not found
- **401**: Unauthorized

---

## Activity Endpoints

### GET /api/activities/

**Description:** Returns the authenticated user’s recent Run activities (last 30 days) for plan and UI context. Uses the same JWT as other `/api/...` routes.

**Authentication:** Required (`Authorization: Bearer <access_token>`)

**Response:** `200` with `{ "activities": [ ... ] }` (each item includes `activity_id`, local `date`, distances, etc.).

---

### POST /api/activities/smartcoach/analyze-run

**Description:** Builds a `run` payload from the database (activity + **split** rows), then proxies to the SmartCoach HTTP service `POST {SMARTCOACH_BASE_URL}/analyze-run`. The main API does not duplicate SmartCoach logic; it only reads the DB and forwards the response.

**Authentication:** Required — same as `GET /api/activities/` (`@requires_auth`, Auth0 access token, internal `g.user_id` resolution).

**Headers:**

- `Authorization: Bearer <access_token>`
- `Content-Type: application/json`
- `Accept: application/json` (optional)

**Request body (JSON) — provide exactly one of:**

```json
{ "activity_id": 1234567890 }
```

```json
{ "date": "2025-03-23" }
```

- **`activity_id`:** Strava activity id as stored and returned in activity lists. Must belong to the caller (`activities.user_id` must match the JWT user). If missing, wrong user, or not found → **404** with `{ "error": "Activity not found" }` (or equivalent) without leaking other users’ data.
- **`date`:** Local calendar date for the linked athlete, using the same timezone rules as `GET /api/activities/`. **404** if no run that day; **409** if multiple runs that day — client must send `activity_id` instead.

**Activity type:** Only `Run` is supported; otherwise **400**.

**Data dependency — splits required:** Split rows must exist for the activity (typically after enrichment). They are loaded ordered by `lap_index`. If none:

- **422** with JSON such as:
  ```json
  {
    "error": "Cannot build run for SmartCoach",
    "detail": "No split rows for this activity; enrich the activity to load splits first."
  }
  ```

**Downstream (server configuration):**

- Set **`SMARTCOACH_BASE_URL`** on the API service (Railway/env) to the SmartCoach service **origin only** (no `/analyze-run` suffix). Example: `https://smartcoach-internal.example.com` or `http://127.0.0.1:8000`.
- Optional: **`SMARTCOACH_TIMEOUT_SECONDS`** (default `60`), **`SMARTCOACH_DATE_LOOKBACK_DAYS`** (default `0` = unlimited history when resolving by `date`).
- The API must be able to reach that host (network / private URL / firewall).

**Downstream request shape (internal):**

```json
{
  "run": { "duration_seconds": 3600, "samples": [ ... ] },
  "runner_id": "<internal user UUID string>"
}
```

**Success — 200:** Response body is SmartCoach’s JSON **as-is** (no wrapper), e.g. string fields such as `summary`, `explanation`, `evidence`, `recommendation` per your SmartCoach contract.

**Error responses (summary):**

| Status | When | Body (typical) |
|--------|------|----------------|
| **400** | Invalid JSON, both `activity_id` and `date`, neither, invalid `date` format, non-Run activity | `{ "error": "<message>" }` |
| **401** | Missing or invalid JWT | `{ "error": "unauthorized", ... }` |
| **404** | Activity not found / not owned; no linked athlete (`date` path); no run on date | `{ "error": "<message>" }` |
| **409** | Multiple runs on the same `date` | `{ "error": "...", "detail": "Pass activity_id to choose one run." }` |
| **422** | No splits or other mapper validation failure; or SmartCoach returned validation error | `{ "error", "detail" }` or forwarded `{ "detail": ... }` (FastAPI style) |
| **503** | `SMARTCOACH_BASE_URL` not set | `{ "detail": "SmartCoach is not configured (SMARTCOACH_BASE_URL)." }` |
| **500** | SmartCoach unreachable, transport error, or non-422 upstream failure | `{ "error": "Analysis service unavailable" }` (details only in server logs) |

**Post-deploy verification (production `https://api.smartcoach.dev`):**

| Check | Expected |
|-------|----------|
| `POST …/api/activities/smartcoach/analyze-run` **without** `Authorization` | **401** — proves the route is registered (not Werkzeug **404** “URL was not found”). |
| Same with valid JWT, valid owned `activity_id`, splits present | **200** + coaching JSON |
| Valid JWT, owned activity, **no** splits | **422** + enrich / splits message |
| Valid JWT, another user’s `activity_id` | **404** + `{ "error": "..." }` |

If unauthenticated `POST` returns Werkzeug **404**, the deployed build does not include this route yet.

---

## Conversation Endpoints

### POST /api/conversations/<conversation_id>/messages

**Description:** Send a message in a conversation and get AI coach response.

**Authentication:** Required (Bearer token)

**Rate Limit:** 10 requests per minute per user (OpenAI API rate limiting)

**Request:**
```json
{
  "message": "How should I adjust my training this week?"
}
```

**Response:**
```json
{
  "message": "Message sent successfully",
  "response": "Based on your training data...",
  "message_id": "uuid-123",
  "response_time": 2.5,
  "context_used": {
    "context_loaded": true,
    "context_length": 1500
  },
  "rate_limit": {
    "remaining": 7,
    "limit": 10,
    "used": 3
  }
}
```

**Response Fields:**
- `rate_limit.remaining`: Number of requests remaining in the current 1-minute window
- `rate_limit.limit`: Total requests allowed per minute (10)
- `rate_limit.used`: Number of requests used in the current window

**Error Response:**
- **400**: Missing or invalid message
- **401**: Unauthorized
- **404**: Conversation not found
- **429**: OpenAI rate limit exceeded (`OPENAI_RATE_LIMIT_EXCEEDED`)
- **500**: Internal server error

**Rate Limit Error Response:**
```json
{
  "error": "Rate limit exceeded. Please try again in 45 seconds.",
  "error_code": "OPENAI_RATE_LIMIT_EXCEEDED",
  "status": 429,
  "details": {
    "retry_after_seconds": 45,
    "limit": "10 requests per minute"
  }
}
```

---

## Strava Connection Management

### DELETE /api/strava/disconnect

**Description:** Disconnect Strava account.

**Authentication:** Required (Bearer token)

**Response:**
```json
{
  "status": 200,
  "message": "Strava disconnected successfully"
}
```

---

### GET /api/strava/status

**Description:** Get Strava connection status.

**Authentication:** Required (Bearer token)

**Response:**
```json
{
  "status": 200,
  "data": {
    "connected": true,
    "athlete_id": 347085,
    "expires_at": "2025-12-01T00:00:00Z"
  }
}
```

---

### GET /api/strava/sync-health

**Description:** Compare Strava run activity IDs to the database for the same rolling window as ingestion full sync (Monday 00:00 UTC at the start of **`STRAVA_INGEST_LOOKBACK_WEEKS`** full ISO weeks before the current week, through now — see `src/services/strava_reconciliation_service.py`; currently **3** weeks).

**Authentication:** Required (Bearer token)

**Notes:** Read-only for the database; may call the Strava activities list API to build the diff.

---

## Error Response Format

All error responses follow this standard format:

```json
{
  "error": "Human-readable error message",
  "status": 400,
  "error_code": "ERROR_CODE",
  "details": {
    "field": "field_name",
    "errors": {
      "field": "validation error"
    }
  }
}
```

### Common Error Codes

- `VALIDATION_ERROR` (400): Request validation failed
- `UNAUTHORIZED` (401): Authentication required or failed
- `NOT_FOUND` (404): Resource not found
- `ALREADY_LINKED` (409): User or athlete already linked
- `RATE_LIMIT_EXCEEDED` (429): Too many requests (general rate limit)
- `OPENAI_RATE_LIMIT_EXCEEDED` (429): Too many OpenAI API requests
- `INTERNAL_ERROR` (500): Server error

### Rate Limit Error Response

When rate limit is exceeded:

```json
{
  "error": "Rate limit exceeded",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "status": 429,
  "retry_after_seconds": 120,
  "message": "Too many requests. Please try again in 120 seconds."
}
```

### OpenAI Rate Limit Error Response

When OpenAI API rate limit is exceeded:

```json
{
  "error": "Rate limit exceeded. Please try again in 45 seconds.",
  "error_code": "OPENAI_RATE_LIMIT_EXCEEDED",
  "status": 429,
  "details": {
    "retry_after_seconds": 45,
    "limit": "10 requests per minute"
  }
}
```

---

## Rate Limits

### Authentication Endpoints

- **Login/OAuth callbacks**: 10 requests per 5 minutes per IP
- **Token refresh**: 30 requests per 15 minutes per IP
- **General auth endpoints**: 20 requests per 5 minutes per IP

### OpenAI API Endpoints

- **Conversation messages** (`POST /api/conversations/<conversation_id>/messages`): 10 requests per minute per user
  - Rate limiting is applied to prevent abuse and manage OpenAI API costs
  - Per-user tracking (not per-IP)
  - Returns `OPENAI_RATE_LIMIT_EXCEEDED` error code when limit exceeded

### Rate Limit Headers

When approaching rate limit, responses may include:

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 3
X-RateLimit-Reset: 1699123456
```

---

## Testing

### Local Development

For local testing, use:
- Base URL: `https://localhost:5000`
- Auth0 Domain: Set in `.env.local` as `AUTH0_DOMAIN`
- CORS: Configured for `https://localhost:5173`

### Test Authentication

Use Auth0 test tokens or set `AUTH_BYPASS=1` for local testing (bypasses JWT validation).

---

## Notes

- All timestamps are in UTC ISO 8601 format
- All UUIDs are lowercase
- All endpoints use HTTPS in production
- CORS is configured for allowed origins only

---

**Last Updated:** November 2025

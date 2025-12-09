# API Documentation

**Date:** November 2025
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

Authentication Architecture Overview
SmartCoach separates authentication into two distinct systems — one for user login via Auth0 (frontend-only), and another for data access via Strava OAuth (backend-only). This separation ensures clean responsibility boundaries and simpler security models.

1. 🔐 Auth0 (User Authentication - Frontend Only)
   Purpose: Authenticates who can access the frontend of the app.

Implemented entirely in the frontend using @auth0/auth0-react.

Handles login, logout, session management, and route gating.

Routes like /login, /post-oauth, /dashboard, /settings are protected using Auth0 context.

Backend does not validate Auth0 tokens — this simplifies server logic and avoids cross-system coupling.

Enables social login (Google, Apple, etc.) without backend changes.

Why?

Minimal backend complexity.

Rapid iteration on frontend login UX.

Clear separation between UI access and data access.

2. 🚴‍♂️ Strava OAuth (Data Sync - Backend Only)
   Purpose: Authorizes the backend to sync user activity data from Strava.

User clicks “Connect with Strava”.

Backend routes (/auth/strava/\*) handle OAuth redirects and token exchange.

Access/refresh tokens are stored in PostgreSQL (linked to athlete_id).

Used for syncing runs, computing metrics, and enrichment.

Why?

Keeps token security and API calls strictly in backend.

Avoids exposing Strava tokens in the browser.

Cleanly separates identity (Auth0) from data (Strava).

3. ⚙️ Route Ownership Table
   Route Pattern Owned By Auth System
   /login, /post-oauth Frontend Auth0
   /dashboard, /settings Frontend Auth0
   /auth/strava/_ Backend Strava OAuth
   /sync/_, /admin/\* Backend JWT (optional)

4. 🌐 Environment Variables
   System Variable Names Location
   Auth0 REACT_APP_AUTH0_DOMAIN, REACT_APP_AUTH0_CLIENT_ID .env.local
   Strava STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REDIRECT_URI .env.staging, .env.prod
   General VITE_API_URL, FLASK_SECRET_KEY All .env.\*

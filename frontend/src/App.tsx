/**
 * @file App.tsx
 * @component App
 * @description Top-level React app component defining all frontend routes using React Router.
 *              Applies protected routing logic to enforce Auth0-based authentication.
 *
 * @features:
 * - Public and protected route declarations
 * - Custom `ProtectedRoute` wrapper for authenticated-only pages
 * - Dedicated login page using Auth0 loginWithRedirect
 * - Default route redirection for unknown paths
 *
 * @integration-points:
 * - `@auth0/auth0-react` for authentication state and login/logout
 * - `react-router-dom` for routing and navigation
 *
 * @usage:
 * - Rendered as the root React app component inside `main.tsx`
 * - Mounts routes like `/`, `/login`, `/welcome`, `/onboarding`, and `/plan`
 * - Protects sensitive routes using `ProtectedRoute`
 *
 * @prerequisites:
 * - App must be wrapped in `<Auth0Provider>` (in `main.tsx`)
 * - Auth0 must be configured with proper `domain`, `clientId`, and `audience`
 * - Backend must accept and validate Auth0 JWTs
 */

import React from "react";
import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";

import OnboardingForm from "./pages/OnboardingForm";
import LandingPage from "./pages/LandingPage";
import PlanPage from "./pages/PlanPage";
import PostOAuth from "./pages/PostOAuth";

// ---------------------------
// ProtectedRoute
// ---------------------------
function ProtectedRoute({ children }: { children: JSX.Element }) {
  const { isLoading, isAuthenticated } = useAuth0();
  if (isLoading) return <div className="p-6">🔄 Loading…</div>;
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

// ---------------------------
// LoginPage
// ---------------------------
function LoginPage() {
  const { loginWithRedirect, logout, isAuthenticated, isLoading, user } = useAuth0();
  const navigate = useNavigate();

  if (isLoading) return <div className="p-6">🔄 Loading…</div>;

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-gray-100 p-8">
      <h1 className="text-3xl font-bold mb-6">Welcome to SmartCoach</h1>
      {!isAuthenticated ? (
        <button
          className="bg-blue-600 text-white px-6 py-3 rounded hover:bg-blue-700 transition"
          onClick={() =>
            loginWithRedirect({
              authorizationParams: {
                redirect_uri: import.meta.env.VITE_AUTH0_REDIRECT_URI, // ✅ Match your AuthProvider
                audience: import.meta.env.VITE_AUTH0_AUDIENCE,
                scope: "openid profile email offline_access",
              },
            })
          }

        >
          Sign In
        </button>
      ) : (
        <div className="space-y-2">
          <p className="text-green-600">
            You're already logged in as <strong>{user?.email}</strong>
          </p>
          <button
            className="bg-red-600 text-white px-6 py-3 rounded hover:bg-red-700 transition"
            onClick={() =>
              logout({ logoutParams: { returnTo: window.location.origin } })
            }
          >
            Log Out
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------
// App Root
// ---------------------------
export default function App() {
  const { isLoading, isAuthenticated } = useAuth0();

  console.log("🔍 App mounted");
  console.log("Auth0 Status →", { isLoading, isAuthenticated });

  return (
    <div className="min-h-screen bg-gray-50">
      <Routes>
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <LandingPage />
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/post-oauth" element={<PostOAuth />} />
        <Route
          path="/onboarding"
          element={
            <ProtectedRoute>
              <OnboardingForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/plan"
          element={
            <ProtectedRoute>
              <PlanPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}

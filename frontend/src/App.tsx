// src/App.tsx
import React, { useEffect } from "react";
import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";

import PostOAuth from "./pages/PostOAuth";
import OnboardingForm from "./pages/OnboardingForm";
import Dashboard from "./pages/Dashboard";
import LandingPage from "./pages/LandingPage";
import StravaCallbackHandler from "./pages/StravaCallbackHandler";

function ProtectedRoute({ children }: { children: JSX.Element }) {
  const { isLoading, isAuthenticated } = useAuth0();
  if (isLoading) return <div className="p‑6">🔄 Loading…</div>;
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function isNewUser(user: any): boolean {
  // TEMP: Replace with real logic (from backend or Auth0 metadata)
  // Example: check for custom field or flag
  return !user?.has_completed_onboarding;
}


function LoginPage() {
  const { loginWithRedirect, logout, isAuthenticated, isLoading, user } = useAuth0();
  const navigate = useNavigate();


  useEffect(() => {
  if (!isLoading && isAuthenticated && user) {
    if (isNewUser(user)) {
      navigate("/welcome", { replace: true });
    } else {
      navigate("/dashboard", { replace: true });
    }
  }
}, [isLoading, isAuthenticated, user, navigate]);



  if (isLoading) return <div className="p‑6">🔄 Loading…</div>;

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-gray-100 p-8">
      <h1 className="text-3xl font-bold mb-6">Welcome to Your Dashboard</h1>
      {!isAuthenticated ? (
        <button
          className="bg-blue-600 text-white px-6 py-3 rounded hover:bg-blue-700 transition"
          onClick={() =>
            loginWithRedirect({
              authorizationParams: {
                redirect_uri: `${window.location.origin}/post-oauth`,
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
          <p className="text-green-600">You're already logged in as <strong>{user?.email}</strong></p>
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

function HomeGate() {
  const { isLoading, isAuthenticated, user } = useAuth0();
  console.log("🔍 Auth State", { isAuthenticated, isLoading, user });
  if (isLoading) return <div className="p‑6">🔄 Loading…</div>;
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Routes>
        <Route path="/" element={<HomeGate />} />
        <Route path="/welcome" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/post-oauth" element={<StravaCallbackHandler  />} />
        <Route path="/onboarding" element={
          <ProtectedRoute>
            <OnboardingForm />
          </ProtectedRoute>
        }/>
        <Route path="/dashboard" element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }/>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}

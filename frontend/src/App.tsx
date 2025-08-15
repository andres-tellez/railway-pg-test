// src/App.tsx
import React, { useEffect } from "react";
import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import PostOAuth from "./pages/PostOAuth";
import OnboardingForm from "./pages/OnboardingForm";
import Dashboard from "./pages/Dashboard";
import DevAuthTools from "./components/DevAuthTools";

function AuthDebug() {
  const { isAuthenticated, isLoading, user } = useAuth0();
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.log("[Auth Debug]", { isAuthenticated, isLoading, user });
  }, [isAuthenticated, isLoading, user]);
  return null;
}

function Protected({ children }: { children: JSX.Element }) {
  const { isAuthenticated, isLoading } = useAuth0();
  if (isLoading) return <div>Loading…</div>;
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function Login() {
  const { loginWithRedirect, logout, isAuthenticated, isLoading, user } = useAuth0();
  const navigate = useNavigate();

  // If user hits /login while already authenticated, go to dashboard (not /post-oauth)
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate("/dashboard", { replace: true });
    }
  }, [isLoading, isAuthenticated, navigate]);

  if (isLoading) return <div>Loading…</div>;

  return (
    <div className="p-8">
      <h1 className="text-xl font-bold mb-4">🔐 Auth0 Test</h1>
      {!isAuthenticated ? (
        <button
          className="bg-blue-600 text-white px-4 py-2 rounded"
          onClick={() =>
            loginWithRedirect({
              // Send the user to /post-oauth right after *successful* Auth0 login (one-time)
              authorizationParams: {
                redirect_uri: `${window.location.origin}/post-oauth`,
                audience: import.meta.env.VITE_AUTH0_AUDIENCE,
                scope: "openid profile email offline_access",
              },
            })
          }
        >
          🔓 Login
        </button>
      ) : (
        <div>
          <p className="mb-2">✅ Logged in as: {user?.email}</p>
          <button
            className="bg-red-600 text-white px-4 py-2 rounded"
            onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
          >
            🔒 Logout
          </button>
        </div>
      )}
    </div>
  );
}

// Root gate: if already authenticated, send to dashboard (not /post-oauth)
function HomeGate() {
  const { isAuthenticated, isLoading } = useAuth0();
  if (isLoading) return <div>Loading…</div>;
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<HomeGate />} />
        <Route path="/login" element={<Login />} />
        {/* This page runs the identity save + auto-linking, then navigates to onboarding/dashboard */}
        <Route path="/post-oauth" element={<PostOAuth />} />
        <Route
          path="/onboarding"
          element={
            <Protected>
              <OnboardingForm />
            </Protected>
          }
        />
        <Route
          path="/dashboard"
          element={
            <Protected>
              <Dashboard />
            </Protected>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      <AuthDebug />
      <DevAuthTools />
    </>
  );
}

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
import PlanPage from "./pages/PlanPage";
import MyPlan from "./pages/MyPlan";
import SetupPage from "./pages/LandingPage";
import PostOAuth from "./pages/PostOAuth";
import HomeScreen from "./pages/HomeScreen";
import AskGptMvpUI from "./pages/AskGptMvpUI";
import WelcomePage from "./pages/WelcomePage";
import SimpleMetrics from "./pages/SimpleMetrics";
import SimpleMetricsCopy from "./pages/SimpleMetricsCopy";
import VO2Metrics from "./pages/VO2Metrics";
import GYRMetricsDemo from "./pages/GYRMetricsDemo";

import Layout from "./components/Layout";
import SmartRouter from "./components/SmartRouter";

// ---------------------------
// ProtectedRoute
// ---------------------------
function ProtectedRoute({ children }: { children: JSX.Element }) {
  const { isLoading, isAuthenticated } = useAuth0();
  if (isLoading) return <div className="p-6">🔄 Loading…</div>;
  return isAuthenticated ? children : <Navigate to="/welcome" replace />;
}

// ---------------------------
// LoginPage
// ---------------------------
function LoginPage() {
  const { loginWithRedirect, isAuthenticated, isLoading } = useAuth0();
  const navigate = useNavigate();

  if (isLoading) return <div className="p-6">🔄 Loading…</div>;

  // If already authenticated, redirect to smart router
  if (isAuthenticated) {
    navigate('/', { replace: true });
    return null;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex flex-col items-center justify-center p-8">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-6">
          <span className="text-white font-bold text-2xl">SC</span>
        </div>

        <h1 className="text-3xl font-bold text-gray-900 mb-4">
          Sign in to SmartCoach
        </h1>

        <p className="text-gray-600 mb-8">
          Connect with your account to access your personalized training plans and coaching.
        </p>

        <button
          className="w-full bg-blue-600 text-white px-6 py-4 rounded-lg font-medium hover:bg-blue-700 transition-colors shadow-lg hover:shadow-xl"
          onClick={() =>
            loginWithRedirect({
              authorizationParams: {
                redirect_uri: import.meta.env.VITE_AUTH0_REDIRECT_URI,
                audience: import.meta.env.VITE_AUTH0_AUDIENCE,
                scope: "openid profile email offline_access",
              },
            })
          }
        >
          Sign In
        </button>

        <p className="text-sm text-gray-500 mt-4">
          Don't have an account? Sign in with Google or create one during the process.
        </p>
      </div>
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
    <Routes>
      {/* Public Routes */}
      <Route path="/welcome" element={<WelcomePage />} />
      <Route path="/login" element={<LoginPage />} />

      {/* Smart Routing */}
      <Route path="/" element={<SmartRouter />} />

      {/* Protected Routes with Layout */}
      <Route
        path="/setup"
        element={
          <ProtectedRoute>
            <Layout>
              <SetupPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/onboarding"
        element={
          <ProtectedRoute>
            <Layout>
              <OnboardingForm />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/home"
        element={
          <ProtectedRoute>
            <Layout>
              <HomeScreen />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/plan/overview"
        element={
          <ProtectedRoute>
            <Layout>
              <MyPlan />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/ask"
        element={
          <ProtectedRoute>
            <Layout>
              <AskGptMvpUI />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/metrics-original"
        element={
          <ProtectedRoute>
            <Layout>
              <SimpleMetrics />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/metrics"
        element={
          <ProtectedRoute>
            <Layout>
              <SimpleMetricsCopy />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/vo2"
        element={
          <ProtectedRoute>
            <Layout>
              <VO2Metrics />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/gyr-demo"
        element={
          <ProtectedRoute>
            <Layout>
              <GYRMetricsDemo />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Legacy Routes - redirect to new structure */}
      <Route
        path="/plan/:id"
        element={
          <ProtectedRoute>
            <Layout>
              <PlanPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/plan"
        element={
          <ProtectedRoute>
            <Layout>
              <PlanPage />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Auth Callback */}
      <Route path="/post-oauth" element={<PostOAuth />} />

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

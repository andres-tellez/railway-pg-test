/**
 * @file App.tsx
 * @component App
 * @description Top-level React app component defining all frontend routes using React Router.
 *              Uses AuthGuard for authentication (handled within each page component).
 *
 * @features:
 * - Public and protected route declarations
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
 * - Individual pages handle authentication via AuthGuard component
 *
 * @prerequisites:
 * - App must be wrapped in `<Auth0Provider>` (in `main.tsx`)
 * - Auth0 must be configured with proper `domain`, `clientId`, and `audience`
 * - Backend must accept and validate Auth0 JWTs
 */

import React from "react";
import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";

import UserProfile from "./pages/UserProfile";
import PlanPage from "./pages/PlanPage";
import MyPlan from "./pages/MyPlan";
import NewPlanForm from "./pages/NewPlanForm";
import NewPlanFormV2 from "./pages/NewPlanFormV2";
import PlansManagement from "./pages/PlansManagement";
import PlanDraftPreview from "./pages/PlanDraftPreview";
import PlanOverviewTable from "./pages/PlanOverviewTable";
import SetupPage from "./pages/LandingPage";
import PostOAuth from "./pages/PostOAuth";
import HomeScreen from "./pages/HomeScreen";
import AuthTestPage from "./pages/AuthTestPage";
import WelcomePage from "./pages/WelcomePage";
import SimpleMetrics from "./pages/SimpleMetrics";
// import GYRMetricsDemo from "./pages/GYRMetricsDemo"; // GYR Scores page hidden
import Metrics from "./pages/Metrics";
import PrivacyPolicy from "./pages/PrivacyPolicy";
import TermsOfService from "./pages/TermsOfService";
import DataDeletion from "./pages/DataDeletion";
import DataUsage from "./pages/DataUsage";
import Settings from "./pages/Settings";
import Admin from "./pages/Admin";
import DateTestPage from "./pages/DateTestPage";
import HeartRateZones from "./pages/HeartRateZones";
import PaceZones from "./pages/PaceZones";

import { getAuth0RedirectUri } from "./auth/auth0RedirectUri";
import Layout from "./components/Layout";
import PlanLayout from "./components/layout/PlanLayout";
import SmartRouter from "./components/SmartRouter";
import { UnitSystemProvider } from "./context/UnitSystemContext";

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
                redirect_uri: getAuth0RedirectUri(),
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
    <UnitSystemProvider>
      <Routes>
        {/* Public Routes */}
        <Route path="/welcome" element={<WelcomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/privacy-policy" element={<PrivacyPolicy />} />
      <Route path="/terms-of-service" element={<TermsOfService />} />
      <Route path="/data-deletion" element={<DataDeletion />} />
      <Route path="/data-usage" element={<DataUsage />} />

      {/* Smart Routing */}
      <Route path="/" element={<SmartRouter />} />

      {/* Protected Routes with Layout - AuthGuard is handled within each page */}
      <Route
        path="/setup"
        element={
          <Layout>
            <SetupPage />
          </Layout>
        }
      />
      <Route
        path="/onboarding"
        element={<Navigate to="/profile" replace />}
      />
      <Route
        path="/profile"
        element={
          <Layout>
            <UserProfile />
          </Layout>
        }
      />
      <Route
        path="/settings"
        element={
          <Layout>
            <Settings />
          </Layout>
        }
      />
      <Route
        path="/heart-rate-zones"
        element={
          <Layout>
            <HeartRateZones />
          </Layout>
        }
      />
      <Route
        path="/pace-zones"
        element={
          <Layout>
            <PaceZones />
          </Layout>
        }
      />
      <Route
        path="/home"
        element={
          <Layout>
            <HomeScreen />
          </Layout>
        }
      />
      <Route
        path="/plan/overview"
        element={
          <Layout>
            <PlanLayout>
              <PlanOverviewTable />
            </PlanLayout>
          </Layout>
        }
      />
      {/* Calendar view - hidden but code preserved */}
      {/*
      <Route
        path="/plan/overview-table"
        element={
          <Layout>
            <PlanLayout>
              <MyPlan />
            </PlanLayout>
          </Layout>
        }
      />
      */}
      <Route
        path="/plan/new"
        element={
          <Layout>
            <PlanLayout>
              <NewPlanForm />
            </PlanLayout>
          </Layout>
        }
      />
      <Route
        path="/plan/new-v2"
        element={
          <Layout>
            <PlanLayout>
              <NewPlanFormV2 />
            </PlanLayout>
          </Layout>
        }
      />
      <Route
        path="/plan/draft"
        element={
          <Layout>
            <PlanLayout>
              <PlanDraftPreview />
            </PlanLayout>
          </Layout>
        }
      />
      <Route
        path="/plan/manage"
        element={
          <Layout>
            <PlanLayout>
              <PlansManagement />
            </PlanLayout>
          </Layout>
        }
      />
      <Route
        path="/test"
        element={
          <Layout>
            <AuthTestPage />
          </Layout>
        }
      />
      <Route
        path="/metrics"
        element={
          <Layout>
            <Metrics />
          </Layout>
        }
      />
      {/* GYR Scores demo route - hidden */}
      {/*
      <Route
        path="/gyr-demo"
        element={
          <Layout>
            <GYRMetricsDemo />
          </Layout>
        }
      />
      */}

      {/* Legacy Routes */}
      <Route
        path="/plan/:id"
        element={
          <Layout>
            <PlanLayout>
              <PlanPage />
            </PlanLayout>
          </Layout>
        }
      />
      <Route
        path="/plan"
        element={
          <Layout>
            <PlanPage />
          </Layout>
        }
      />

      {/* Admin Routes */}
      <Route
        path="/admin"
        element={
          <Layout>
            <Admin />
          </Layout>
        }
      />
      <Route
        path="/date-test"
        element={
          <Layout>
            <DateTestPage />
          </Layout>
        }
      />

      {/* Auth Callback */}
      <Route path="/post-oauth" element={<PostOAuth />} />

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </UnitSystemProvider>
  );
}

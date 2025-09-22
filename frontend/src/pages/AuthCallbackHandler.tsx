/**
 * @file AuthCallbackHandler.tsx
 * @component AuthCallbackHandler
 * @description Handles the Auth0 redirect flow. This file finalizes the login process after the user
 *              authenticates with Auth0 and is redirected back to the app via /auth/callback.
 *
 * @features:
 * - Uses Auth0 React SDK to process login redirect response
 * - Finalizes the authentication session via handleRedirectCallback()
 * - Navigates the user to the root route after successful login
 *
 * @integration-points:
 * - Auth0 SDK: useAuth0().handleRedirectCallback()
 * - React Router: useNavigate() to redirect post-login
 *
 * @usage:
 * - Must be mounted at route: `/auth/callback`
 * - Declared in App.tsx via:
 *     <Route path="/auth/callback" element={<AuthCallbackHandler />} />
 *
 * @prerequisites:
 * - Must match redirect_uri used in loginWithRedirect()
 * - Auth0Provider must wrap the root of the app in main.tsx
 */

import { useEffect } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useNavigate } from "react-router-dom";

export default function AuthCallbackHandler() {
  const { handleRedirectCallback } = useAuth0();
  const navigate = useNavigate();

  useEffect(() => {
    const finalizeLogin = async () => {
      try {
        await handleRedirectCallback(); // ✅ Finalizes login
        navigate("/", { replace: true }); // ✅ Send user to app entry point
      } catch (err) {
        console.error("❌ Auth callback failed", err);
        navigate("/login"); // Fallback
      }
    };
    void finalizeLogin();
  }, [handleRedirectCallback, navigate]);

  return <div className="p-6">🔐 Finalizing login…</div>;
}

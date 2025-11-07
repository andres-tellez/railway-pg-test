// @file PostOAuth.tsx
// @description: Handles Auth0 login callback, token exchange, and user identity creation
// @features: Auth0 token processing, secure backend login, error handling with retry
// @integration-points: Auth0, /auth/login/callback, /user/identity, SmartRouter
// @usage: Called via redirect after Auth0 authentication completes
// @prerequisites: Auth0 must return valid id_token, user must be authenticated

import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { useApiClient } from "@/utils/apiClient";

interface ErrorState {
  message: string;
  type: "network" | "auth" | "server" | "timeout" | "unknown";
  retryable: boolean;
  details?: string;
}

const PostOAuth: React.FC = () => {
  const navigate = useNavigate();
  const { isLoading, isAuthenticated, getIdTokenClaims } = useAuth0();
  const api = useApiClient();
  const ran = useRef(false);

  const [error, setError] = useState<ErrorState | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);

  const handleError = (err: unknown, context: string): ErrorState => {
    console.error(`❌ PostOAuth error [${context}]:`, err);

    // Handle AbortError (user cancelled or timeout)
    if (err instanceof Error && err.name === "AbortError") {
      return {
        message: "Request was cancelled or timed out",
        type: "timeout",
        retryable: true,
        details: "The authentication process took too long. Please try again.",
      };
    }

    // Handle network errors
    if (err instanceof TypeError && err.message.includes("fetch")) {
      return {
        message: "Network connection failed",
        type: "network",
        retryable: true,
        details: "Unable to connect to the server. Please check your internet connection.",
      };
    }

    // Handle fetch response errors
    if (err instanceof Error && err.message.includes("auth/login/callback failed")) {
      const match = err.message.match(/failed: (\d+)/);
      const statusCode = match ? parseInt(match[1], 10) : 0;

      if (statusCode === 401) {
        return {
          message: "Authentication failed",
          type: "auth",
          retryable: true,
          details: "Your login token is invalid or expired. Please try logging in again.",
        };
      }

      if (statusCode === 400) {
        return {
          message: "Invalid request",
          type: "auth",
          retryable: false,
          details: "The authentication request was invalid. Please try logging in again.",
        };
      }

      if (statusCode >= 500) {
        return {
          message: "Server error",
          type: "server",
          retryable: true,
          details: "The server encountered an error. Please try again in a moment.",
        };
      }
    }

    // Handle Auth0 token errors
    if (err instanceof Error && err.message.includes("id_token")) {
      return {
        message: "Authentication token missing",
        type: "auth",
        retryable: true,
        details: "Unable to retrieve your authentication token. Please try logging in again.",
      };
    }

    // Generic error
    return {
      message: "An error occurred during sign-in",
      type: "unknown",
      retryable: true,
      details: err instanceof Error ? err.message : "Please try again.",
    };
  };

  const performAuth = async (signal: AbortSignal) => {
    setError(null);
    setIsRetrying(false);

    try {
      const claims = await getIdTokenClaims();
      const idToken = claims?.__raw;
      console.log("🪪 ID token →", idToken ? "present" : "missing");

      if (!idToken) {
        throw new Error("No Auth0 id_token found");
      }

      const base =
        import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:5000";

      console.log("📡 Posting token to backend:", base);

      const resp = await fetch(`${base}/auth/login/callback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_token: idToken }),
        credentials: "include",
        signal,
      });

      console.log("📡 /auth/login/callback →", resp.status);

      if (!resp.ok) {
        let errorData;
        try {
          errorData = await resp.json();
        } catch {
          errorData = { error: await resp.text().catch(() => "Unknown error") };
        }

        const errorMessage = errorData.error || errorData.message || `HTTP ${resp.status}`;
        throw new Error(`auth/login/callback failed: ${resp.status} ${errorMessage}`);
      }

      // Create/update user identity
      await api.post("/api/user/identity", {}, { signal });

      // Get user info
      await api.get("/api/user", { signal });

      // Check if this is a Strava callback
      const params = new URLSearchParams(window.location.search);
      const isStravaCallback = params.get("strava") === "connected";

      // Success - redirect appropriately
      if (isStravaCallback) {
        navigate("/setup?strava=connected", { replace: true });
      } else {
        navigate("/", { replace: true });
      }
    } catch (err) {
      if (signal.aborted) {
        // Don't set error if request was intentionally aborted
        return;
      }
      const errorState = handleError(err, "performAuth");
      setError(errorState);
    }
  };

  useEffect(() => {
    console.log("🔍 PostOAuth mounted →", { isLoading, isAuthenticated });

    if (isLoading) {
      console.log("⏳ Auth0 still loading, skipping");
      return;
    }

    if (!isAuthenticated) {
      console.warn("🚨 Not authenticated after loading → sending to /login");
      navigate("/login", { replace: true });
      return;
    }

    if (ran.current && !isRetrying) return;
    ran.current = true;

    const ac = new AbortController();
    const safety = setTimeout(() => {
      if (!error) {
        console.warn("⏱️ Safety timeout triggered");
        setError({
          message: "Sign-in is taking longer than expected",
          type: "timeout",
          retryable: true,
          details: "The authentication process timed out. You can try again or continue.",
        });
      }
    }, 10000); // Increased to 10 seconds

    void performAuth(ac.signal);

    return () => {
      clearTimeout(safety);
      ac.abort();
    };
  }, [isLoading, isAuthenticated, getIdTokenClaims, navigate, api, isRetrying, error]);

  const handleRetry = () => {
    setIsRetrying(true);
    ran.current = false; // Allow effect to run again
  };

  const handleContinue = () => {
    // Allow user to continue even if there was an error
    navigate("/", { replace: true });
  };

  // Show error state with user-friendly message and retry option
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-6">
          <div className="flex items-center justify-center w-12 h-12 mx-auto mb-4 bg-red-100 rounded-full">
            <svg
              className="w-6 h-6 text-red-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>

          <h2 className="text-xl font-semibold text-gray-900 text-center mb-2">
            {error.message}
          </h2>

          {error.details && (
            <p className="text-gray-600 text-center mb-6 text-sm">
              {error.details}
            </p>
          )}

          <div className="flex flex-col gap-3">
            {error.retryable && (
              <button
                onClick={handleRetry}
                disabled={isRetrying}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isRetrying ? "Retrying..." : "Try Again"}
              </button>
            )}

            <button
              onClick={handleContinue}
              className="w-full px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
            >
              Continue to App
            </button>
          </div>

          {error.type === "network" && (
            <p className="text-xs text-gray-500 text-center mt-4">
              Tip: Check your internet connection and firewall settings.
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p className="text-gray-600">🔐 Finishing sign-in…</p>
        <p className="text-gray-500 text-sm mt-2">This may take a few seconds</p>
      </div>
    </div>
  );
};

export default PostOAuth;

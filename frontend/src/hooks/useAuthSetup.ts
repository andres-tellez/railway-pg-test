// frontend/src/hooks/useAuthSetup.ts
import { useEffect, useRef, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useApiClient } from "../utils/apiClient";

interface AuthSetupResult {
  isReady: boolean;
  userId: string | null;
  error: string | null;
}

/**
 * Centralized authentication setup hook that ensures user identity is created
 * and ready before making API calls. This should be used by all pages that
 * need to make authenticated API requests.
 */
export function useAuthSetup(): AuthSetupResult {
  const { isAuthenticated, isLoading } = useAuth0();
  const api = useApiClient();
  const hasSetupIdentity = useRef(false);
  const [isReady, setIsReady] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    console.log("🔍 Auth setup effect:", { isAuthenticated, isLoading, hasSetupIdentity: hasSetupIdentity.current });

    if (!isAuthenticated || isLoading || hasSetupIdentity.current) {
      return;
    }

    hasSetupIdentity.current = true;
    setError(null);
    console.log("🚀 Starting user identity setup...");

    // Ensure user identity is created (like other working pages do)
    api.post("/api/user/identity", {})
      .then((res) => {
        // Backend returns {data: {user_id: "..."}, status: 200}
        const newUserId = res.data.data?.user_id || res.data.user_id;
        setUserId(newUserId);
        setIsReady(true);
        console.log("✅ Auth setup complete - User ID:", newUserId);
      })
      .catch((err) => {
        const errorMessage = err.response?.data?.message || err.message || "Failed to setup authentication";
        setError(errorMessage);
        console.error("❌ Auth setup failed:", errorMessage);
        // Still mark as ready to prevent infinite loading
        setIsReady(true);
      });
  }, [isAuthenticated, isLoading, api]);

  return {
    isReady,
    userId,
    error
  };
}

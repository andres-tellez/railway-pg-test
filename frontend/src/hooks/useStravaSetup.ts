// Custom hook for Strava connection state and logic
import { useState, useEffect, useCallback } from "react";
import { useApiClient } from "../utils/apiClient";
import { useNavigate } from "react-router-dom";
import { useAuthSetup } from "./useAuthSetup";

interface UserStatus {
  hasOnboarded: boolean;
  hasStrava: boolean;
}

interface UseStravaSetupReturn {
  isSyncing: boolean;
  isComplete: boolean;
  isLoading: boolean;
  error: string | null;
  userId: string | null;
  showConsentModal: boolean;
  handleConnectClick: (e?: React.MouseEvent) => void;
  handleConsentAccept: () => void;
  handleConsentDecline: () => void;
  retryFetch: () => void;
}

export function useStravaSetup(): UseStravaSetupReturn {
  const api = useApiClient();
  const navigate = useNavigate();
  const { isReady, userId } = useAuthSetup();

  const [syncing, setSyncing] = useState(false);
  const [forceSyncing, setForceSyncing] = useState(false);
  const [hasStrava, setHasStrava] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showConsentModal, setShowConsentModal] = useState(false);

  // Fetch user status
  const fetchUserStatus = useCallback(async () => {
    if (!isReady || !userId) {
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      const res = await api.get<UserStatus>("/api/user");
      console.log("📊 User status:", res.data);

      // Backend wraps response in { data: {...}, status: 200 }
      const userData = res.data.data || res.data;
      console.log("📊 Extracted user data:", userData);

      setHasStrava(userData.hasStrava || false);

      if (userData.hasOnboarded) {
        navigate("/home");
      }
    } catch (err: any) {
      const errorMessage = err.response?.data?.message || err.message || "Failed to load user status";
      console.error("❌ Failed to fetch user status:", errorMessage);
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [isReady, userId, api, navigate]);

  const retryFetch = useCallback(() => {
    fetchUserStatus();
  }, [fetchUserStatus]);

  // Initial load
  useEffect(() => {
    fetchUserStatus();
  }, [fetchUserStatus]);

  // Handle Strava OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("strava") === "connected") {
      console.log("🔄 Strava connected, showing sync spinner");
      setForceSyncing(true);

      const timer = setTimeout(() => {
        setForceSyncing(false);
        params.delete("strava");
        window.history.replaceState({}, "", window.location.pathname);
        fetchUserStatus();
      }, 8000);

      return () => clearTimeout(timer);
    }
  }, [fetchUserStatus]);

  const handleConnectClick = useCallback((e?: React.MouseEvent) => {
    e?.stopPropagation();
    e?.preventDefault();
    setShowConsentModal(true);
  }, []);

  const handleConsentAccept = useCallback(() => {
    if (!userId) {
      console.error("❌ Cannot connect Strava: no userId");
      setShowConsentModal(false);
      return;
    }

    const apiBase = import.meta.env.VITE_BACKEND_URL;

    // Store consent timestamp before redirect
    const consentTimestamp = new Date().toISOString();
    console.log("✅ User consent granted at:", consentTimestamp);
    localStorage.setItem('strava_consent_timestamp', consentTimestamp);

    // Redirect immediately - keep modal visible during redirect to prevent blank screen
    // The modal will naturally disappear when the page navigates to Strava
    window.location.href = `${apiBase}/auth/strava-login?user_id=${encodeURIComponent(userId)}`;
  }, [userId]);

  const handleConsentDecline = useCallback(() => {
    setShowConsentModal(false);
  }, []);

  const isSyncing = syncing || forceSyncing;
  const isComplete = hasStrava && !isSyncing;

  return {
    isSyncing,
    isComplete,
    isLoading,
    error,
    userId,
    showConsentModal,
    handleConnectClick,
    handleConsentAccept,
    handleConsentDecline,
    retryFetch,
  };
}

// Custom hook for Strava connection state and logic
import { useState, useEffect, useCallback } from "react";
import { useApiClient } from "../utils/apiClient";
import { useNavigate } from "react-router-dom";
import { useAuthSetup } from "./useAuthSetup";

interface UserStatus {
  hasOnboarded: boolean;
  hasStrava: boolean;
}

interface SyncStatus {
  status: string | null;
  progress: number;
  step: string | null;
  detail: string | null;
  errorCode?: string | null;
  updatedAt?: string | null;
}

interface UseStravaSetupReturn {
  isSyncing: boolean;
  isComplete: boolean;
  isLoading: boolean;
  error: string | null;
  userId: string | null;
  syncStatus: SyncStatus | null;
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
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);

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

  const fetchStravaStatus = useCallback(async () => {
    if (!isReady) return;

    try {
      const res = await api.get("/api/strava/status");
      const payload = res.data.data || res.data;

      setHasStrava(Boolean(payload.connected));

      if (payload.sync_status) {
        setSyncStatus({
          status: payload.sync_status.status ?? null,
          progress:
            typeof payload.sync_status.progress === "number"
              ? payload.sync_status.progress
              : 0,
          step: payload.sync_status.step ?? null,
          detail: payload.sync_status.detail ?? null,
          errorCode: payload.sync_status.errorCode ?? undefined,
          updatedAt: payload.sync_status.updatedAt ?? undefined,
        });
      } else {
        setSyncStatus(null);
      }

      const statusValue = payload.sync_status?.status;
      const currentlySyncing =
        statusValue === "in_progress" || statusValue === "pending";
      setSyncing(currentlySyncing);

      if (!currentlySyncing) {
        setForceSyncing(false);
      }

      if (statusValue === "error") {
        setError(payload.sync_status?.detail || "Strava sync failed");
      }
    } catch (err: any) {
      const message =
        err?.response?.data?.message || err?.message || "Failed to fetch Strava status";
      console.error("❌ Failed to fetch Strava status:", message);
      setError(message);
    }
  }, [api, isReady]);

  const retryFetch = useCallback(() => {
    fetchUserStatus();
    fetchStravaStatus();
  }, [fetchUserStatus, fetchStravaStatus]);

  // Initial load
  useEffect(() => {
    fetchUserStatus();
    fetchStravaStatus();
  }, [fetchUserStatus, fetchStravaStatus]);

  // Handle Strava OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("strava") === "connected") {
      console.log("🔄 Strava connected, showing sync spinner");
      setForceSyncing(true);
      fetchStravaStatus();
      params.delete("strava");
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [fetchStravaStatus]);

  useEffect(() => {
    if (!forceSyncing && syncStatus?.status !== "in_progress") {
      return;
    }

    const interval = setInterval(() => {
      fetchStravaStatus();
    }, 3000);

    return () => clearInterval(interval);
  }, [forceSyncing, syncStatus?.status, fetchStravaStatus]);

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

  const isSyncing =
    syncing ||
    forceSyncing ||
    syncStatus?.status === "in_progress" ||
    syncStatus?.status === "pending";
  const isComplete =
    hasStrava &&
    !isSyncing &&
    (syncStatus?.status === "complete" || syncStatus === null);

  return {
    isSyncing,
    isComplete,
    isLoading,
    error,
    userId,
    syncStatus,
    showConsentModal,
    handleConnectClick,
    handleConsentAccept,
    handleConsentDecline,
    retryFetch,
  };
}

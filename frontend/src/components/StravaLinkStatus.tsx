// src/components/StravaLinkStatus.tsx
import React from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { getLink, postLink, deleteLink, type LinkStatus } from "../utils/linkApi";

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; data: LinkStatus }
  | { kind: "error"; message: string };

export default function StravaLinkStatus() {
  const { isAuthenticated, getAccessTokenSilently, loginWithRedirect } = useAuth0();
  const [state, setState] = React.useState<State>({ kind: "idle" });
  const [manualAthleteId, setManualAthleteId] = React.useState<string>("");

  const isBusy = state.kind === "loading";

  // Centralized way to fetch an API-scoped token; falls back to "dev" for AUTH_BYPASS mode
  const getApiToken = React.useCallback(async () => {
    if (!isAuthenticated) return "dev";
    return getAccessTokenSilently({
      authorizationParams: {
        audience: import.meta.env.VITE_AUTH0_AUDIENCE,
        scope: "openid profile email offline_access",
      },
    });
  }, [getAccessTokenSilently, isAuthenticated]);

  const load = React.useCallback(async () => {
    try {
      setState({ kind: "loading" });
      const token = await getApiToken();
      const data = await getLink(token);
      setState({ kind: "loaded", data });
    } catch (err: any) {
      const message =
        typeof err === "string" ? err : err?.message || "Failed to load link status";
      // If desired later: if (message.includes("401")) loginWithRedirect();
      setState({ kind: "error", message });
    }
  }, [getApiToken]);

  React.useEffect(() => {
    void load();
  }, [load]);

  function handleConnectStrava() {
    // SPA starts the Strava OAuth via backend alias
    window.location.assign("/auth/strava/connect");
  }

  async function handleManualLink() {
    if (!manualAthleteId) return;
    try {
      setState({ kind: "loading" });
      const token = await getApiToken();
      await postLink(token, Number(manualAthleteId));
      await load();
    } catch (err: any) {
      setState({ kind: "error", message: err?.message || "Failed to link athlete" });
    }
  }

  async function handleUnlink() {
    try {
      setState({ kind: "loading" });
      const token = await getApiToken();
      await deleteLink(token);
      await load();
    } catch (err: any) {
      setState({ kind: "error", message: err?.message || "Failed to unlink" });
    }
  }

  if (!isAuthenticated) {
    return (
      <div style={{ border: "1px solid #ddd", padding: 16, borderRadius: 8 }}>
        <p>You’re not logged in.</p>
        <button onClick={() => loginWithRedirect()}>Log in</button>
      </div>
    );
  }

  if (state.kind === "loading" || state.kind === "idle") {
    return <div style={{ padding: 8 }}>Checking Strava link…</div>;
  }

  if (state.kind === "error") {
    return (
      <div style={{ border: "1px solid #f5c2c7", background: "#f8d7da", padding: 16, borderRadius: 8 }}>
        <p style={{ margin: 0 }}>Error: {state.message}</p>
        <button style={{ marginTop: 8 }} onClick={load}>Retry</button>
      </div>
    );
  }

  // loaded
  const { data } = state;

  if (data.linked) {
    return (
      <div style={{ border: "1px solid #d1e7dd", background: "#dff0d8", padding: 16, borderRadius: 8 }}>
        <div style={{ marginBottom: 8 }}>
          ✅ Linked to Strava (athlete <strong>#{data.athlete_id}</strong>)
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={handleUnlink} disabled={isBusy}>Unlink</button>
          <button onClick={load} disabled={isBusy}>Refresh</button>
        </div>
      </div>
    );
  }

  // not linked
  return (
    <div style={{ border: "1px solid #ffeeba", background: "#fff3cd", padding: 16, borderRadius: 8 }}>
      <div style={{ marginBottom: 8 }}>⚠️ Not linked to Strava yet.</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button onClick={handleConnectStrava} disabled={isBusy}>Connect Strava</button>
        <span style={{ alignSelf: "center" }}>— or dev-only —</span>
        <input
          value={manualAthleteId}
          onChange={(e) => setManualAthleteId(e.target.value)}
          placeholder="Athlete ID"
          inputMode="numeric"
          style={{ padding: 6 }}
        />
        <button onClick={handleManualLink} disabled={isBusy || !manualAthleteId}>
          Link Manually
        </button>
      </div>
    </div>
  );
}

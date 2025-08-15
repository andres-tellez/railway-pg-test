// src/components/DevAuthTools.tsx
import { useAuth0 } from "@auth0/auth0-react";

export default function DevAuthTools() {
  if (!import.meta.env.DEV) return null;

  const { isAuthenticated, user, getAccessTokenSilently, loginWithRedirect, getAccessTokenWithPopup } = useAuth0();

  async function printToken() {
    try {
      const token = await getAccessTokenSilently({
        authorizationParams: {
          audience: import.meta.env.VITE_AUTH0_AUDIENCE,
          scope: "openid profile email offline_access",
        },
      });
      console.log("🔑 access_token", token);
      alert("Access token printed to console");
    } catch (e: any) {
      // First-time or API permission change → require consent/interaction
      if (["consent_required", "login_required", "interaction_required"].includes(e?.error)) {
        // either redirect flow:
        await loginWithRedirect({
          authorizationParams: {
            audience: import.meta.env.VITE_AUTH0_AUDIENCE,
            scope: "openid profile email offline_access",
            prompt: "consent",
          },
        });
        // or popup (uncomment if you prefer popup):
        // await getAccessTokenWithPopup({
        //   authorizationParams: {
        //     audience: import.meta.env.VITE_AUTH0_AUDIENCE,
        //     scope: "openid profile email offline_access",
        //   },
        // });
      } else {
        console.error(e);
        alert(`Token error: ${e?.message || e}`);
      }
    }
  }

  return (
    <div style={{ position: "fixed", bottom: 12, right: 12, padding: 12, border: "1px solid #ccc", background: "#fff", borderRadius: 8, zIndex: 9999 }}>
      <div style={{ fontWeight: 600, marginBottom: 8 }}>Dev Auth Tools</div>
      <div style={{ fontSize: 12, marginBottom: 8 }}>
        {isAuthenticated ? `User: ${user?.email ?? user?.sub}` : "Not authenticated"}
      </div>
      <button type="button" onClick={printToken}>Print Access Token</button>
    </div>
  );
}

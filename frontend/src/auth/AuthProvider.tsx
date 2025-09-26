// frontend/src/auth/AuthProvider.tsx
import { Auth0Provider } from "@auth0/auth0-react";
import React from "react";

const AuthProviderWithHistory: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const domain = import.meta.env.VITE_AUTH0_DOMAIN;
  const clientId = import.meta.env.VITE_AUTH0_CLIENT_ID;
  const redirectUri = import.meta.env.VITE_AUTH0_REDIRECT_URI; // e.g. https://app.smartcoach.dev/post-oauth
  const audience = import.meta.env.VITE_AUTH0_AUDIENCE;        // e.g. https://api.smartcoach.dev

  console.log("🔍 Auth0 Config", { domain, clientId, redirectUri, audience });

  if (!domain || !clientId || !redirectUri || !audience) {
    throw new Error("Missing Auth0 env values");
  }

  return (
    <Auth0Provider
      domain={domain}
      clientId={clientId}
      authorizationParams={{
        redirect_uri: redirectUri,
        audience: audience,
        scope: "openid profile email", // ✅ Required to receive those claims
      }}
      cacheLocation="localstorage"
      useRefreshTokens={true}
    >
      {children}
    </Auth0Provider>
  );
};

export default AuthProviderWithHistory;

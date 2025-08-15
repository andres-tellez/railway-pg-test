// frontend/src/auth/AuthProvider.tsx
import { Auth0Provider } from "@auth0/auth0-react";
import React from "react";
import { useNavigate } from "react-router-dom";

const AuthProviderWithHistory: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return <InnerAuthProvider>{children}</InnerAuthProvider>;
};

const InnerAuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();

  const domain       = import.meta.env.VITE_AUTH0_DOMAIN;
  const clientId     = import.meta.env.VITE_AUTH0_CLIENT_ID;
  const redirectUri  = import.meta.env.VITE_AUTH0_REDIRECT_URI; // https://localhost:5173/post-oauth
  const audience     = import.meta.env.VITE_AUTH0_AUDIENCE;     // https://api.smartcoach.dev

  console.log("🔍 Auth0 Config", { domain, clientId, redirectUri, audience });

  if (!domain || !clientId || !redirectUri || !audience) {
    throw new Error("Missing Auth0 env values");
  }

  const onRedirectCallback = (appState?: { returnTo?: string }) => {
    navigate(appState?.returnTo || "/dashboard", { replace: true });
  };

  return (
    <Auth0Provider
      domain={domain}
      clientId={clientId}
      authorizationParams={{
        redirect_uri: redirectUri,
        audience,
        scope: "openid profile email offline_access",
      }}
      onRedirectCallback={onRedirectCallback}
      cacheLocation="localstorage"
      useRefreshTokens
      useCookiesForTransactions
    >
      {children}
    </Auth0Provider>
  );
};

export default AuthProviderWithHistory;

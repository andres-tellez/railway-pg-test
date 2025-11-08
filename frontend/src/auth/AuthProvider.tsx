// frontend/src/auth/AuthProvider.tsx
import { Auth0Provider } from "@auth0/auth0-react";
import React from "react";
import { useNavigate } from "react-router-dom";

const AuthProviderWithHistory: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const domain = import.meta.env.VITE_AUTH0_DOMAIN;
  const clientId = import.meta.env.VITE_AUTH0_CLIENT_ID;
  const redirectUri = import.meta.env.VITE_AUTH0_REDIRECT_URI;
  const audience = import.meta.env.VITE_AUTH0_AUDIENCE;

  const navigate = useNavigate();

  const onRedirectCallback = (appState: any) => {
    console.log("🎯 Redirect callback:", appState);

    // If Auth0 provided an appState return path (e.g., when login was triggered mid-session),
    // honor it so the user lands back where they started. Otherwise, leave navigation alone
    // so dedicated callback routes (like /post-oauth) can finish their own flows before
    // redirecting (they will call navigate once setup completes).
    if (appState?.returnTo) {
      navigate(appState.returnTo, { replace: true });
    }
  };

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
        scope: "openid profile email offline_access",
      }}
      onRedirectCallback={onRedirectCallback}
      cacheLocation="localstorage"
      useRefreshTokens={true}
    >
      {children}
    </Auth0Provider>
  );
};

export default AuthProviderWithHistory;

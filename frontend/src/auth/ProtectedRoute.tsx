// src/auth/ProtectedRoute.tsx
import { useAuth0 } from "@auth0/auth0-react";
import React, { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

type Props = { children: React.ReactNode };

const ProtectedRoute: React.FC<Props> = ({ children }) => {
  const { isAuthenticated, isLoading, loginWithRedirect, error } = useAuth0();
  const location = useLocation();
  const redirected = useRef(false);

  useEffect(() => {
    if (isLoading) return; // wait for SDK
    if (redirected.current) return; // avoid repeat calls if component re-renders

    if (!isAuthenticated) {
      redirected.current = true;
      loginWithRedirect({
        appState: { returnTo: location.pathname + location.search },
      });
    }
  }, [isLoading, isAuthenticated, loginWithRedirect, location]);

  if (error) return <div>Auth error: {error.message}</div>;
  if (isLoading || !isAuthenticated) {
    return <div>Checking your session…</div>;
  }

  return <>{children}</>;
};

export default ProtectedRoute;

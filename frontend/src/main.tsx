import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Auth0Provider } from "@auth0/auth0-react";
import App from "./App";
import './index.css';


ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Auth0Provider
        domain="dev-ppz6v1x0u18obr81.us.auth0.com"
        clientId="qcD3RetLxl6OYCVAzEHvmccSbYozk21N"
        authorizationParams={{
          redirect_uri: import.meta.env.VITE_AUTH0_REDIRECT_URI
            ?? `${window.location.origin}/post-oauth`,
          scope: "openid profile email offline_access",
          response_type: "code",
          response_mode: "query",
        }}
        cacheLocation="localstorage"
        useCookiesForTransactions
      >
        <App />
      </Auth0Provider>
    </BrowserRouter>
  </React.StrictMode>
);

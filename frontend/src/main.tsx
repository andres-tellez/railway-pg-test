// src/main.tsx

import "./index.css";

console.log('AUTH0 CLIENT ID:', import.meta.env.VITE_AUTH0_CLIENT_ID);

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import AuthProviderWithHistory from "./auth/AuthProvider";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProviderWithHistory>
        <App />
      </AuthProviderWithHistory>
    </BrowserRouter>
  </React.StrictMode>
);

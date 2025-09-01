// src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import AuthProviderWithHistory from "./auth/AuthProvider";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthProviderWithHistory>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </AuthProviderWithHistory>
  </React.StrictMode>
);

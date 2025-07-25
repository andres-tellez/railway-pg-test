import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./index.css";
import App from "./App"; // ⬅ remove `.js` to avoid TS import issues

const rootElement = document.getElementById("root");

if (!rootElement) throw new Error("Root element not found");

createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter basename="/">
      <App />
    </BrowserRouter>
  </StrictMode>
);

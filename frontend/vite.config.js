// vite.config.js
import fs from "fs";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  if (!env.VITE_BACKEND_URL) {
    throw new Error("❌ Missing VITE_BACKEND_URL in .env.local");
  }

  const backendTarget = env.VITE_BACKEND_URL;

  return {
    base: "/",
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
      },
    },
    server: {
      port: 5173,
      https: {
        key: fs.readFileSync("./localhost-key.pem"),
        cert: fs.readFileSync("./localhost.pem"),
      },
      strictPort: true,
      proxy: {
        "/auth": {
          target: backendTarget,
          changeOrigin: true,
          secure: false,
        },
        "/api": {
          target: backendTarget,
          changeOrigin: true,
          secure: false,
          ws: false, // 🚫 disable websocket upgrade for SSE to work
        },
      },
      historyApiFallback: true,
    },
    build: {
      outDir: "dist",
      emptyOutDir: true,
    },
  };
});

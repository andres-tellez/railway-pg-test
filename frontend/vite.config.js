// vite.config.js
import fs from "fs";
import { defineConfig, loadEnv } from "vite";
import path from "path";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const isDev = mode === "development";

  // Only require VITE_BACKEND_URL in development (for proxy)
  if (isDev && !env.VITE_BACKEND_URL) {
    throw new Error("❌ Missing VITE_BACKEND_URL in .env.local");
  }

  const backendTarget = env.VITE_BACKEND_URL;

  // SSL certificates are only needed for local dev server
  let httpsConfig = undefined;
  if (isDev) {
    try {
      httpsConfig = {
        key: fs.readFileSync("./localhost-key.pem"),
        cert: fs.readFileSync("./localhost.pem"),
      };
    } catch (e) {
      // Certificates not found, use HTTP (fallback)
      console.warn("⚠️  SSL certificates not found, using HTTP for dev server");
    }
  }

  return {
    base: "/",
    plugins: [tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
      },
    },
    server: isDev ? {
      port: 5173,
      ...(httpsConfig && { https: httpsConfig }),
      strictPort: true,
      proxy: backendTarget ? {
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
      } : {},
      historyApiFallback: true,
    } : undefined,
    build: {
      outDir: "dist",
      emptyOutDir: true,
    },
  };
});

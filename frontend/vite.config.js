import fs from "fs";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import tailwindcss from "@tailwindcss/vite"; // ✅ ADD THIS

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendTarget = env.VITE_BACKEND_URL || "http://127.0.0.1:5000";

  return {
    base: "/",
    plugins: [
      react(),
      tailwindcss(), // ✅ ADD THIS
    ],
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

import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import mkcert from 'vite-plugin-mkcert';
import path from 'path';
import fs from 'fs';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  const backendTarget = env.VITE_BACKEND_URL || 'http://127.0.0.1:5000';

  return {
    base: '/',
    plugins: [react(), mkcert()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      https: {
        key: fs.readFileSync('./localhost-key.pem'),
        cert: fs.readFileSync('./localhost.pem'),
      },
      strictPort: true,
      proxy: {
        '/auth':  { target: backendTarget, changeOrigin: true, secure: false },
        '/admin': { target: backendTarget, changeOrigin: true, secure: false },
        '/sync':  { target: backendTarget, changeOrigin: true, secure: false },
        '/ask':   { target: backendTarget, changeOrigin: true, secure: false },
        // 👇 Added so PostOAuth can call /api/onboarding (and any other API routes)
        '/api':   { target: backendTarget, changeOrigin: true, secure: false },
      },
      historyApiFallback: true,
    },
    preview: {
      historyApiFallback: true,
    },
    build: {
      outDir: 'dist',
      emptyOutDir: true,
    },
  };
});

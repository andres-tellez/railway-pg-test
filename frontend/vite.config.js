import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(({ mode }) => {
  // Load .env file variables (VITE_BACKEND_URL expected)
  const env = loadEnv(mode, process.cwd(), '');

  return {
    base: '/',
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        '/auth': {
          target: env.VITE_BACKEND_URL,
          changeOrigin: true,
          secure: false,
        },
        '/admin': {
          target: env.VITE_BACKEND_URL,
          changeOrigin: true,
          secure: false,
        },
        '/sync': {
          target: env.VITE_BACKEND_URL,
          changeOrigin: true,
          secure: false,
        },
        '/ask': {
          target: env.VITE_BACKEND_URL,
          changeOrigin: true,
          secure: false,
        },
      },
    },
    build: {
      outDir: '../src/frontend/dist',  // ✅ Matches backend static path
      emptyOutDir: true,
    },
  };
});

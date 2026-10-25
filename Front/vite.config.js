import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Proxy /api -> backend Spring Boot (localhost:8080) para evitar CORS en dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
});

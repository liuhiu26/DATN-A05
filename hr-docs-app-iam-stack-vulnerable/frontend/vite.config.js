import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Mọi request /api từ trình duyệt đi qua Kong (API Gateway, cổng 8000), không gọi thẳng FastAPI.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': process.env.VITE_API_TARGET || 'http://localhost:8000' },
  },
});

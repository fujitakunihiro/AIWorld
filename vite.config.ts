import { defineConfig } from 'vite';
export default defineConfig({
  root: 'frontend',
  server: {
    port: 5173, strictPort: true,
    proxy: {
      '/api': { target: process.env.BACKEND_URL ?? 'http://localhost:3001' },
      '/socket': { target: process.env.BACKEND_URL ?? 'http://localhost:3001', ws: true }
    }
  },
  build: { outDir: '../dist', emptyOutDir: true }
});

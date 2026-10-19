import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// in dev, send /api calls to django on :8000 so we dont have to deal with CORS
export default defineConfig({
  plugins: [react()],
  base: '/',
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'static/assets',
  },
})

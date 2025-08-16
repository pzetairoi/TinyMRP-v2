import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': { target: 'http://127.0.0.1:5000', changeOrigin: true } } },
  build: {
    outDir: '../app/static/parts-ui',
    emptyOutDir: true,
    manifest: true,             // <-- important
  },
  base: '/static/parts-ui/',    // URLs Flask/Jinja will reference
})

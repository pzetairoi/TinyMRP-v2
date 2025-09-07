// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ command }) => {
  const isBuild = command === 'build'
  const backend = process.env.VITE_BACKEND_URL || 'http://localhost:5000'
  return {
    plugins: [react()],
    base: isBuild ? '/static/parts-ui/' : '/',
    build: {
      outDir: '../app/static/parts-ui',
      emptyOutDir: true,
      manifest: true,
      sourcemap: false,
      rollupOptions: {},
    },
    optimizeDeps: { include: ['react','react-dom'] },
    server: {
      port: 5173, strictPort: true,
      proxy: {
        '/api':        { target: backend, changeOrigin: true },
        '/extfiles':   { target: backend, changeOrigin: true },
        '/deliverables': { target: backend, changeOrigin: true }, // optional
      },
    },
    preview: { port: 5174, strictPort: true },
  }
})

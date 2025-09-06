// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ command }) => {
  const isBuild = command === 'build'
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
        '/api':      { target: 'http://localhost:5000', changeOrigin: true },
        '/extfiles': { target: 'http://localhost:5000', changeOrigin: true },
        '/Deliverables': { target: 'http://localhost:5000', changeOrigin: true }, // optional
      },
    },
    preview: { port: 5174, strictPort: true },
  }
})

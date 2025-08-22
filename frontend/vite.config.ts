import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// IMPORTANT:
// - base MUST be the URL prefix where Flask serves the built assets
// - outDir MUST be the Flask static folder for the SPA
export default defineConfig({
  plugins: [react()],
  base: '/static/parts-ui/',
  build: {
    outDir: '../app/static/parts-ui',
    emptyOutDir: true,
    manifest: true,
    sourcemap: false,
    rollupOptions: {
      // Ensure NOTHING is externalized here. If you had 'external: ["react","react-dom"]' remove it.
    }
  },
  // Also ensure we don't exclude 'react' from optimizeDeps
  optimizeDeps: {
    include: ['react', 'react-dom']
  }
})

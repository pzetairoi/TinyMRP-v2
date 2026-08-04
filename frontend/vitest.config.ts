/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Kept separate from vite.config.ts on purpose. That file drives the
// production build (outDir ../app/static/parts-ui, base /static/parts-ui/),
// and a test run must not be able to touch the shipped bundle.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    // 3D viewers and canvas markup pull in WebGL, which jsdom cannot provide.
    // Those need Playwright (QA-FE-01 residue), not a fake DOM.
    exclude: ['node_modules/**', 'dist/**'],
    coverage: {
      provider: 'v8',
      reportsDirectory: './coverage',
      include: ['src/lib/**', 'src/components/**', 'src/pages/**'],
      exclude: ['src/**/*.d.ts', 'src/test/**'],
    },
  },
})

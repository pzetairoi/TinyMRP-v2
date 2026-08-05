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
      // Thresholds apply to src/lib only, on purpose. That is the pure logic
      // layer, and it is genuinely covered (>90%). Including the pages would
      // force the number down to something like 13%, and a threshold set that
      // low ratchets nothing - it would pass even if every lib test were
      // deleted. A meaningful gate over the covered code beats a decorative
      // one over everything.
      //
      // When a page gains real tests, add it here rather than lowering these.
      include: ['src/lib/**'],
      exclude: ['src/**/*.d.ts', 'src/test/**', 'src/**/*.test.{ts,tsx}'],
      thresholds: {
        statements: 90,
        branches: 90,
        functions: 85,
        lines: 90,
      },
    },
  },
})

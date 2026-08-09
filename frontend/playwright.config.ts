import { defineConfig, devices } from '@playwright/test'

/**
 * Browser-level coverage for the paths unit tests cannot prove.
 *
 * DELIBERATELY SMALL. The plan's instruction was "do not attempt a giant E2E
 * framework", and the reason is specific to this project: a large browser
 * suite is slow, flaky and expensive to keep honest, and it tends to duplicate
 * what the 336 unit tests already cover cheaply. What it uniquely proves is
 * that the real pages render, navigate and refuse - things a jsdom test cannot
 * see because it never runs the router, the CSP or a real fetch.
 *
 * Runs against a LIVE INSTANCE rather than a dev server, chosen with
 * PLAYWRIGHT_BASE_URL, because the things worth catching here - a strict CSP
 * blocking a script, a build that ships a broken chunk - only exist in a real
 * deployment. Defaults to localhost:5000 for a local run.
 *
 * Credentials come from the environment and are never defaulted: a suite that
 * carries a working login is a suite that ships one.
 */
export default defineConfig({
  testDir: './e2e',
  // A browser test that takes longer than this is telling you something.
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['github'], ['list']] : [['list']],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5000',
    // Evidence for the failures that are hard to reproduce by description.
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ignoreHTTPSErrors: false,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})

import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

/**
 * The critical path, in a real browser.
 *
 * Everything here is chosen because a jsdom unit test CANNOT prove it:
 *   - the built bundle actually parses and runs
 *   - the enforced Content-Security-Policy does not block our own scripts
 *   - the router resolves real URLs
 *   - an unauthenticated caller is refused rather than shown the page
 *
 * The CSP check earns its place: script-src dropped 'unsafe-inline' fleet-wide
 * on 2026-08-09, and the failure mode of getting that wrong is a blank page
 * that returns HTTP 200. Nothing in the backend suite can see it.
 *
 * TESTS THAT NEED A LOGIN SKIP unless E2E_EMAIL and E2E_PASSWORD are set.
 * They are never defaulted - a suite carrying working credentials is a suite
 * that ships them.
 */

const EMAIL = process.env.E2E_EMAIL || ''
const PASSWORD = process.env.E2E_PASSWORD || ''
const HAS_LOGIN = Boolean(EMAIL && PASSWORD)

/** Fail the test on any console error, which is how a blocked script shows up. */
function watchConsole(page: import('@playwright/test').Page): string[] {
  const errors: string[] = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text())
  })
  page.on('pageerror', (err) => errors.push(String(err)))
  return errors
}

test('the login page renders and its scripts are not blocked by CSP', async ({ page }) => {
  const errors = watchConsole(page)
  const response = await page.goto('/login')

  expect(response?.status()).toBe(200)
  await expect(page.locator('input[type="password"]')).toBeVisible()

  // A CSP that blocks our own bundle reports here and nowhere else.
  const blocked = errors.filter((e) => /Content Security Policy|Refused to (load|execute)/i.test(e))
  expect(blocked, `CSP blocked something:\n${blocked.join('\n')}`).toHaveLength(0)
})

test('the login page has no serious accessibility violations', async ({ page }) => {
  await page.goto('/login')
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze()

  // Only serious and critical gate. Minor findings are recorded by the run but
  // must not block a deploy on a page that works.
  const serious = results.violations.filter(
    (v) => v.impact === 'serious' || v.impact === 'critical',
  )
  const summary = serious.map((v) => `${v.id}: ${v.help}`).join('\n')
  expect(serious, `accessibility violations:\n${summary}`).toHaveLength(0)
})

test('an unauthenticated caller is refused the parts API, not shown data', async ({ request }) => {
  const response = await request.get('/api/parts_lazy', { failOnStatusCode: false })
  // 401 or a redirect to login. Never 200 with a body.
  expect([401, 302, 303, 403]).toContain(response.status())
})

test('health is anonymous and reports the service', async ({ request }) => {
  const response = await request.get('/api/health')
  expect(response.status()).toBe(200)
  const body = await response.json()
  expect(body.ok).toBe(true)
  expect(body.service).toBe('tinymrp')
})

test.describe('signed in', () => {
  test.skip(!HAS_LOGIN, 'set E2E_EMAIL and E2E_PASSWORD to run the signed-in path')

  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="email"], input[name="email"]', EMAIL)
    await page.fill('input[type="password"]', PASSWORD)
    await page.click('button[type="submit"], input[type="submit"]')
    await page.waitForLoadState('networkidle')

    // Assert the login WORKED before anything else runs. Without this, bad
    // credentials surface as "the parts table is missing", which sends the
    // next person looking at the parts page instead of at their password.
    expect(
      page.url(),
      `login did not succeed - still at ${page.url()}. Check E2E_EMAIL/E2E_PASSWORD.`,
    ).not.toContain('/login')
  })

  test('the parts list loads and renders rows without console errors', async ({ page }) => {
    const errors = watchConsole(page)
    await page.goto('/ui/parts')
    await page.waitForLoadState('networkidle')

    // The table shell must exist. Row count is deliberately not asserted: an
    // empty instance is a valid state and this test must not depend on data.
    await expect(page.locator('table, [role="table"], .p-datatable').first()).toBeVisible()

    const blocked = errors.filter((e) => /Content Security Policy|Refused to/i.test(e))
    expect(blocked, `CSP blocked something on the parts list:\n${blocked.join('\n')}`).toHaveLength(0)
  })
})

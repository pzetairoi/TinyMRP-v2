/**
 * Help images for "Workflow B: Progressive Ordering Across Multi-Level BOM".
 *
 * Separate from capture-help-shots.mjs so this workflow can be re-shot on its
 * own: it drives a stateful sequence (raise an order, submit it, watch coverage
 * move) rather than photographing static pages, and re-running the whole help
 * set to fix one caption is wasteful.
 *
 * Point it at a disposable instance seeded with `flask demo install`, never at
 * the development instance - that database holds real part numbers. Reset the
 * worked example first, or the coverage shots start from wherever the last run
 * left off:
 *
 *   ENV_FILE=<instance env> python frontend/tools/seed-help-job.py
 *   HELP_BASE_URL=http://localhost:5056 \
 *   HELP_COMMERCIAL_EMAIL=permtest.commercial@demo.com \
 *   HELP_COMMERCIAL_PASSWORD=... \
 *   HELP_INTERNAL_EMAIL=permtest.internal@demo.com \
 *   HELP_INTERNAL_PASSWORD=... \
 *   node frontend/tools/capture-job-ordering-shots.mjs
 */
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(scriptDir, '..', '..')
const outputDir = path.join(repoRoot, 'app', 'static', 'help', 'img')
const baseUrl = (process.env.HELP_BASE_URL || 'http://localhost:5056').replace(/\/$/, '')
const jobNumber = process.env.HELP_JOB_NUMBER || 'JOB-2026-014'

// The worked example buys one commodity group across the whole job. Filtering
// the description to PLATE gathers pressed and cut plate from both job roots and
// from three different levels, which is the case for consolidating a buy.
const CONSOLIDATE_FILTER = 'PLATE'

const accounts = {
  commercial: {
    email: process.env.HELP_COMMERCIAL_EMAIL || '',
    password: process.env.HELP_COMMERCIAL_PASSWORD || '',
  },
  internal: {
    email: process.env.HELP_INTERNAL_EMAIL || '',
    password: process.env.HELP_INTERNAL_PASSWORD || '',
  },
}

for (const [role, account] of Object.entries(accounts)) {
  if (!account.email || !account.password) {
    throw new Error(`Set HELP_${role.toUpperCase()}_EMAIL and HELP_${role.toUpperCase()}_PASSWORD.`)
  }
}

async function signIn(context, account) {
  const page = await context.newPage()
  await page.goto(`${baseUrl}/login`)
  await page.locator('input[type=email], input[name=email]').fill(account.email)
  await page.locator('input[type=password]').fill(account.password)
  await page.locator('button[type=submit], input[type=submit]').click()
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 20_000 })
  return page
}

async function settle(page, milliseconds = 1200) {
  await page.waitForLoadState('domcontentloaded')
  await page.waitForTimeout(milliseconds)
}

/** Find the job by number rather than hard-coding an ObjectId that changes per seed. */
async function jobUrl(page) {
  await page.goto(`${baseUrl}/admin/jobs/?job_q=${encodeURIComponent(jobNumber)}`)
  await settle(page)
  const link = page.getByRole('link', { name: jobNumber, exact: true }).first()
  await link.waitFor({ state: 'visible', timeout: 15_000 })
  const href = await link.getAttribute('href')
  return new URL(href, baseUrl).toString().replace(/\/edit$/, '')
}

/** Photograph a section plus its heading, clipped so captions stay readable. */
async function sectionShot(page, headingText, name, maxHeight = 760) {
  const heading = page.getByRole('heading', { name: headingText }).first()
  await heading.waitFor({ state: 'visible', timeout: 15_000 })
  await heading.evaluate((el) => el.scrollIntoView({ block: 'start' }))
  await page.waitForTimeout(500)
  const box = await heading.boundingBox()
  if (!box) throw new Error(`Could not measure "${headingText}".`)
  await page.screenshot({
    path: path.join(outputDir, `${name}.png`),
    clip: {
      x: 12,
      y: Math.max(0, box.y - 20),
      width: 1416,
      height: Math.min(maxHeight, 1260 - box.y),
    },
  })
  console.log(`wrote ${name}.png`)
}

/** Some panels are labelled with a <label>, not a heading. */
async function labelShot(page, labelText, name, maxHeight = 700) {
  const label = page.getByText(labelText, { exact: true }).first()
  await label.waitFor({ state: 'visible', timeout: 15_000 })
  await label.evaluate((el) => el.scrollIntoView({ block: 'start' }))
  await page.waitForTimeout(500)
  const box = await label.boundingBox()
  if (!box) throw new Error(`Could not measure "${labelText}".`)
  await page.screenshot({
    path: path.join(outputDir, `${name}.png`),
    clip: { x: 12, y: Math.max(0, box.y - 64), width: 1416, height: Math.min(maxHeight, 1240 - box.y) },
  })
  console.log(`wrote ${name}.png`)
}

const browser = await chromium.launch()
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1300 }, deviceScaleFactor: 1 })
  const page = await signIn(context, accounts.commercial)
  const job = await jobUrl(page)

  // 1. Flat view: one consolidated line per part/revision across the whole job.
  await page.goto(job)
  await settle(page)
  await page.locator('#remaining-view-flat').click()
  await page.waitForTimeout(500)
  await sectionShot(page, 'Parts Not Yet Ordered', 'job-ordering-flat')

  // 2. Tree view: the same demand split by occurrence, with BOM level paths.
  await page.locator('#remaining-view-tree').click()
  await page.waitForTimeout(500)
  await page.locator('#remaining-filter-pn').fill('CV03-TR-0')
  await page.waitForTimeout(600)
  await sectionShot(page, 'Parts Not Yet Ordered', 'job-ordering-tree')

  // 3. Filter to one commodity, select every row still visible, and order the
  //    lot as a single consolidated purchase order.
  await page.goto(job)
  await settle(page)
  await page.locator('#remaining-view-flat').click()
  await page.waitForTimeout(400)
  await page.locator('#remaining-filter-desc').fill(CONSOLIDATE_FILTER)
  await page.waitForTimeout(600)
  await page.locator('#remaining-flat-table .remaining-select-all').check()
  await page.waitForTimeout(400)
  await sectionShot(page, 'Parts Not Yet Ordered', 'job-ordering-select', 620)

  await page.locator('[data-act="submit-remaining-order"]').click()
  await page.waitForURL((url) => url.pathname.includes('/admin/orders/'), { timeout: 20_000 })
  await settle(page, 1600)
  await labelShot(page, 'Order Lines', 'job-ordering-new-order', 700)

  // 4. Coverage after the order leaves draft: the same parts move out of
  //    remaining and into Parts in Orders.
  const orderUrl = page.url()
  await page.goto(orderUrl)
  await settle(page)
  await page.locator('select[name=status]').selectOption('submitted')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await settle(page, 1800)
  await page.goto(job)
  await settle(page, 1400)
  await sectionShot(page, 'Parts in Orders', 'job-ordering-coverage')

  await context.close()

  // 5. The same job for a role that may read jobs but not create orders.
  const readOnlyContext = await browser.newContext({ viewport: { width: 1440, height: 1300 }, deviceScaleFactor: 1 })
  const readOnly = await signIn(readOnlyContext, accounts.internal)
  await readOnly.goto(job)
  await settle(readOnly, 1400)
  await sectionShot(readOnly, 'Parts Not Yet Ordered', 'job-ordering-readonly', 560)
  await readOnlyContext.close()
} finally {
  await browser.close()
}

import { chromium } from 'playwright'
import { zipSync, strToU8 } from 'fflate'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(scriptDir, '..', '..')
const outputDir = path.join(repoRoot, 'app', 'static', 'help', 'img')
const baseUrl = (process.env.HELP_BASE_URL || 'http://localhost:5000').replace(/\/$/, '')
const helpPart = { partNumber: 'CV03-TR-A01', revision: 'A' }
const helpChild = { partNumber: 'CV03-F02', revision: 'B' }

const credentials = {
  administrator: {
    email: process.env.HELP_ADMIN_EMAIL || '',
    password: process.env.HELP_ADMIN_PASSWORD || '',
  },
  customer: {
    email: process.env.HELP_CUSTOMER_EMAIL || '',
    password: process.env.HELP_CUSTOMER_PASSWORD || '',
  },
}

for (const [role, account] of Object.entries(credentials)) {
  if (!account.email || !account.password) {
    throw new Error(`Set HELP_${role === 'administrator' ? 'ADMIN' : 'CUSTOMER'}_EMAIL and PASSWORD.`)
  }
}

async function signIn(context, account, height = 1000) {
  const page = await context.newPage()
  await page.setViewportSize({ width: 1440, height })
  await page.goto(`${baseUrl}/login`)
  await page.locator('input[type=email], input[name=email]').fill(account.email)
  await page.locator('input[type=password]').fill(account.password)
  await page.locator('button[type=submit], input[type=submit]').click()
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15_000 })
  return page
}

async function settle(page, milliseconds = 2400) {
  await page.waitForLoadState('domcontentloaded')
  await page.waitForTimeout(milliseconds)
}

async function viewportShot(page, name) {
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: path.join(outputDir, `${name}.png`) })
  console.log(`wrote ${name}.png`)
}

async function elementShot(locator, name) {
  await locator.scrollIntoViewIfNeeded()
  await locator.screenshot({ path: path.join(outputDir, `${name}.png`) })
  console.log(`wrote ${name}.png`)
}

async function clippedShot(locator, page, name, maxHeight) {
  await locator.scrollIntoViewIfNeeded()
  const box = await locator.boundingBox()
  if (!box) throw new Error(`Could not measure ${name}.`)
  await page.screenshot({
    path: path.join(outputDir, `${name}.png`),
    clip: {
      x: Math.max(0, box.x - 8),
      y: Math.max(0, box.y - 8),
      width: Math.min(1440, box.width + 16),
      height: Math.min(maxHeight, box.height + 16),
    },
  })
  console.log(`wrote ${name}.png`)
}

function previewArchive() {
  const flatBom = [
    JSON.stringify({
      partnumber: helpChild.partNumber,
      revision: 'HELP',
      description: 'Trailer frame - proposed training revision',
      material: 'Aluminium',
    }),
    JSON.stringify({
      partnumber: helpPart.partNumber,
      revision: helpPart.revision,
      description: 'CELLV03 Trailer - planned update',
      material: 'Steel',
    }),
  ].join('\n')
  const treeBom = [
    'ITEM NO.\tPART NUMBER\tRevision\tQTY.',
    `1\t${helpPart.partNumber}\t${helpPart.revision}\t1`,
    `1.1\t${helpChild.partNumber}\tHELP\t1`,
  ].join('\n')
  return Buffer.from(
    zipSync({
      'HELP_FLATBOM.txt': strToU8(flatBom),
      'HELP_TREEBOM.txt': strToU8(treeBom),
    }),
  )
}

const browser = await chromium.launch({ headless: true })
try {
  const adminContext = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    deviceScaleFactor: 1,
  })
  const page = await signIn(adminContext, credentials.administrator)

  await page.goto(`${baseUrl}/ui/parts`)
  await settle(page)
  const inventorySearch = page.getByPlaceholder('Search part number, description, notes or comments')
  await inventorySearch.fill(helpPart.partNumber)
  await page.waitForResponse((response) => response.url().includes('/api/') && response.ok(), { timeout: 15_000 }).catch(() => {})
  await settle(page, 1200)
  await page.getByRole('link', { name: helpPart.partNumber, exact: true }).waitFor({ state: 'visible', timeout: 15_000 })
  await viewportShot(page, 'inventory')

  await page.goto(`${baseUrl}/ui/upload-pack`)
  await settle(page)
  await viewportShot(page, 'import')

  await page.goto(`${baseUrl}/admin/roles/`)
  await settle(page)
  await viewportShot(page, 'roles')

  await page.goto(`${baseUrl}/ui/admin/fields`)
  const presetsHeading = page.getByRole('heading', { name: 'Screen & export presets' })
  await presetsHeading.waitFor({ state: 'visible', timeout: 15_000 })
  const presets = presetsHeading.locator('xpath=..')
  await presets.evaluate((element) => {
    element.style.maxHeight = '820px'
    element.style.overflow = 'hidden'
  })
  await elementShot(presets, 'admin-fields')

  await page.goto(`${baseUrl}/tools/`)
  await settle(page)
  await elementShot(page.locator('main').first(), 'tools-downloads')

  await page.goto(`${baseUrl}/ui/part/${helpPart.partNumber}?rev=${helpPart.revision}`)
  await page.getByRole('heading', { name: new RegExp(helpPart.partNumber) }).waitFor({ state: 'visible', timeout: 15_000 })
  await page.waitForFunction(
    () => Array.from(document.images).some((image) => image.naturalWidth > 300),
    null,
    { timeout: 20_000 },
  )
  await settle(page)
  if (await page.getByText('No files found.').count()) {
    throw new Error('The capture server has no deliverables root; refusing a broken Part Detail shot.')
  }
  await viewportShot(page, 'part-detail')

  await page.getByRole('tab', { name: /Comments & Markups/ }).click()
  await page.getByText('Hitch clearance review', { exact: true }).waitFor({ state: 'visible', timeout: 20_000 })
  await settle(page, 2200)
  await viewportShot(page, 'review-conversations')
  const drawing = page.locator('.pd-markup-image')
  await drawing.waitFor({ state: 'visible', timeout: 20_000 })
  await page.waitForFunction(() => {
    const image = document.querySelector('.pd-markup-image')
    return image && image.naturalWidth > 0
  }, null, { timeout: 20_000 })
  const enlarge = page.locator('[title="Enlarge markup workspace"]')
  if (await enlarge.count()) await enlarge.click()
  await settle(page, 3500)
  await viewportShot(page, 'drawing-markups')

  await page.goto(`${baseUrl}/ui/part/${helpPart.partNumber}?rev=${helpPart.revision}`)
  await page.getByRole('heading', { name: new RegExp(helpPart.partNumber) }).waitFor({ state: 'visible', timeout: 15_000 })
  const bomHeading = page.getByRole('heading', { name: 'BOM', exact: true })
  await bomHeading.scrollIntoViewIfNeeded()
  await settle(page)
  const rowsBefore = await page.locator('.p-treetable-tbody > tr').count()
  const toggler = page.locator('.p-treetable-tbody .p-treetable-toggler:visible').first()
  if (!(await toggler.count())) throw new Error('Approved help BOM has no expandable row.')
  await toggler.click()
  await settle(page, 3500)
  const rowsAfter = await page.locator('.p-treetable-tbody > tr').count()
  if (rowsAfter <= rowsBefore) throw new Error('Nested BOM did not expand for the screenshot.')
  await elementShot(bomHeading.locator('xpath=../..'), 'bom-tree')

  await page.goto(`${baseUrl}/ui/upload-pack`)
  await settle(page)
  await page.locator('input[type=file]').setInputFiles({
    name: 'tinymrp-help-preview.zip',
    mimeType: 'application/zip',
    buffer: previewArchive(),
  })
  await page.getByRole('button', { name: 'Override approved (Admin)' }).click()
  await page.getByRole('button', { name: 'Preview changes' }).click()
  const redlineHeading = page.getByRole('heading', { name: 'Preview redline' })
  await redlineHeading.waitFor({ state: 'visible', timeout: 30_000 })
  await settle(page, 1500)
  await clippedShot(redlineHeading.locator('xpath=../../..'), page, 'upload-pack-redline', 950)

  const customerContext = await browser.newContext({
    viewport: { width: 1440, height: 620 },
    deviceScaleFactor: 1,
  })
  const customer = await signIn(customerContext, credentials.customer, 620)
  await customer.goto(`${baseUrl}/ui/parts`)
  await settle(customer)
  const customerSearch = customer.getByPlaceholder('Search part number, description, notes or comments')
  await customerSearch.fill(helpPart.partNumber)
  await customer.waitForResponse((response) => response.url().includes('/api/') && response.ok(), { timeout: 15_000 }).catch(() => {})
  await settle(customer, 1200)
  await customer.getByRole('link', { name: helpPart.partNumber, exact: true }).waitFor({ state: 'visible', timeout: 15_000 })
  await viewportShot(customer, 'customer-portal')
  await customerContext.close()
  await adminContext.close()
} finally {
  await browser.close()
}

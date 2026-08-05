import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import DashboardPage from './DashboardPage'
import { mockApi } from '../test/mockApi'

/**
 * QA-FE-01. The dashboard is the first screen a user sees, so "failed to load"
 * rendering as a page full of zeros is a genuinely misleading outcome: it says
 * the shop has no parts rather than that we could not ask.
 */

const summary = {
  counts: { total_parts: 42, updated_7d: 7, approved: 30 },
  doc_coverage: { pdf: 10, png: 8, dxf: 5, step: 3, datasheet: 1 },
  data_health: { missing_material: 2, missing_process: 1, missing_description: 0 },
  top_processes: [{ process: 'Milling', count: 12 }],
  recent_parts: [
    { part_number: 'PN-1', revision: 'A', description: 'Bracket', updated_at: '2026-08-01' },
  ],
  top_hardware: [
    { part_number: 'BOLT-1', revision: 'A', description: 'M8 bolt', where_used_count: 9, total_qty: 40 },
  ],
}

const routes = {
  'GET /api/dashboard/summary': summary,
  'GET /api/field-config': { permissions: { can_admin: false } },
}

const renderPage = () =>
  render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  )

describe('DashboardPage', () => {
  it('renders the summary once loaded', async () => {
    mockApi(routes)
    renderPage()

    expect(await screen.findByText('42')).toBeInTheDocument()
    expect(screen.getByText('Bracket')).toBeInTheDocument()
    expect(screen.getByText('M8 bolt')).toBeInTheDocument()
  })

  it('shows an error instead of a page of zeros when the summary fails', async () => {
    // The defect this guards: a failed load looking like an empty database.
    mockApi({
      ...routes,
      'GET /api/dashboard/summary': { status: 500, body: { error: { message: 'Database unreachable' } } },
    })
    renderPage()

    // Rendered as "Dashboard error: <message>", so the text spans nodes.
    expect(await screen.findByText(/Database unreachable/)).toBeInTheDocument()
  })

  it('still says something useful when the error body is empty', async () => {
    // readApiResponse synthesises "Request failed (<status>)" for a bodyless
    // error, so the page's own generic fallback is effectively unreachable
    // through the API path. The user still gets a status, never a blank.
    mockApi({ ...routes, 'GET /api/dashboard/summary': { status: 503, body: {} } })
    renderPage()

    expect(await screen.findByText(/Request failed \(503\)/)).toBeInTheDocument()
  })

  it('still renders the dashboard when the permission lookup fails', async () => {
    // Permissions are decoration here; losing them must not blank the page.
    mockApi({
      ...routes,
      'GET /api/field-config': { status: 403, body: { error: { message: 'nope' } } },
    })
    renderPage()

    expect(await screen.findByText('42')).toBeInTheDocument()
  })

  it('does not set state after unmounting', async () => {
    // The `cancelled` guard exists to stop a late response updating a dead
    // component, which React reports as an act()/state-update warning.
    const warn = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockApi(routes)
    const { unmount } = renderPage()
    unmount()

    await waitFor(() => {
      expect(warn).not.toHaveBeenCalledWith(
        expect.stringContaining('unmounted component'),
        expect.anything(),
      )
    })
  })
})

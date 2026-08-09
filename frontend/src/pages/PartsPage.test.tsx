import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import PartsPage from './PartsPage'
import { mockApi } from '../test/mockApi'

/**
 * The parts inventory is the page this project exists to make fast, and the
 * one most likely to lie convincingly.
 *
 * The failure worth pinning is the same one the dashboard had: a load that
 * FAILS rendering as an empty table says "this company has no parts" instead
 * of "we could not ask". On an inventory screen that is a business answer,
 * not a UI glitch, and nothing about an empty table looks broken.
 */

const rows = [
  { part_number: 'PN-100', revision: 'A', description: 'Bracket', approved: true },
  { part_number: 'PN-200', revision: 'B', description: 'Housing', approved: false },
]

const routes = {
  'POST /api/parts_lazy': { data: rows, totalRecords: rows.length },
  'GET /api/field-config': { permissions: { can_admin: false } },
}

const renderPage = () =>
  render(
    <MemoryRouter>
      <PartsPage />
    </MemoryRouter>,
  )

describe('PartsPage', () => {
  it('renders the parts it was given', async () => {
    mockApi(routes)
    renderPage()

    expect(await screen.findByText('PN-100')).toBeInTheDocument()
    expect(screen.getByText('Bracket')).toBeInTheDocument()
  })

  it('shows an error instead of an empty inventory when the load fails', async () => {
    // The defect: "failed to load" and "you have no parts" must not look alike.
    mockApi({
      ...routes,
      'POST /api/parts_lazy': {
        status: 500,
        body: { error: { message: 'Database unreachable' } },
      },
    })
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent(/Database unreachable/)
  })

  it('still says something useful when the error carries no message', async () => {
    mockApi({
      ...routes,
      'POST /api/parts_lazy': { status: 500, body: {} },
    })
    renderPage()

    // Any explanation beats a silent empty table. The status-derived message
    // is what apiErrorMessage produces when the body carries none, and it is
    // more useful than a generic fallback would be.
    expect(await screen.findByRole('alert')).toHaveTextContent(/request failed \(500\)/i)
  })
})

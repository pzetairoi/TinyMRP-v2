import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import AdminAddinPage from './AdminAddinPage'
import { mockApi } from '../test/mockApi'

/**
 * This page manages the SolidWorks add-in's users, tokens and numbering
 * schemes - and unlike AdminFieldsPage it does NOT gate on a `can_admin` flag
 * client-side; it renders unconditionally and relies on the backend 403-ing
 * the underlying calls. That is a legitimate design (the client can never be
 * the real enforcement point) but it means the ONE thing worth pinning here
 * is the failure mode the rest of this plan has spent an entire batch on:
 * a failed load and a genuinely empty list render THE SAME "No users." /
 * "No schemes." row. The error banner above the tables is what keeps that
 * from being silent, so these tests exist to prove it stays there.
 */

const users = {
  users: [{ id: 'u1', email: 'engineer@example.com', roles: ['engineering'] }],
}

const schemes = {
  schemes: [
    { id: 's1', name: 'Standard parts', is_active: true, separator: '-', pattern_segments: [] },
  ],
}

const renderPage = () =>
  render(
    <MemoryRouter>
      <AdminAddinPage />
    </MemoryRouter>,
  )

describe('AdminAddinPage', () => {
  it('renders the users and numbering schemes it was given', async () => {
    mockApi({
      'GET /api/admin/users': users,
      'GET /api/numbering/schemes': schemes,
    })
    renderPage()

    expect(await screen.findByText('engineer@example.com')).toBeInTheDocument()
    expect(screen.getByText('Standard parts')).toBeInTheDocument()
  })

  it('says the user list failed rather than showing "No users." unexplained', async () => {
    // The defect this pins: without the banner, a 403 or a 500 here is
    // indistinguishable from an instance with zero users - on a page whose
    // "Revoke all API tokens" button is a real, destructive action.
    mockApi({
      'GET /api/admin/users': {
        status: 403,
        body: { error: { message: 'Administrator access is required.' } },
      },
      'GET /api/numbering/schemes': schemes,
    })
    renderPage()

    expect(await screen.findByText(/Administrator access is required/)).toBeInTheDocument()
    expect(screen.getByText('No users.')).toBeInTheDocument()
  })

  it('says the scheme list failed rather than showing "No schemes." unexplained', async () => {
    mockApi({
      'GET /api/admin/users': users,
      'GET /api/numbering/schemes': {
        status: 500,
        body: { error: { message: 'Numbering schemes unavailable' } },
      },
    })
    renderPage()

    expect(await screen.findByText(/Numbering schemes unavailable/)).toBeInTheDocument()
    expect(screen.getByText('No schemes.')).toBeInTheDocument()
    // A load failure on one list must not blank out a list that DID load.
    expect(screen.getByText('engineer@example.com')).toBeInTheDocument()
  })
})

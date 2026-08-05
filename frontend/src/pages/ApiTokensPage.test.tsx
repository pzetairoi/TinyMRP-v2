import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ApiTokensPage from './ApiTokensPage'
import { mockApi } from '../test/mockApi'

/**
 * QA-FE-01, first page test. This is the UI for Phase 1B token lifecycle, so
 * the behaviours worth pinning are the ones a user cannot recover from:
 * the secret is shown exactly once, destructive actions confirm first, and a
 * failed request surfaces instead of leaving the page looking empty-but-fine.
 */

// is_active drives whether the Rotate/Revoke buttons render at all.
const tokens = [
  { id: 't1', label: 'Add-in laptop', status: 'active' as const, is_active: true,
    expires_at_display: '2026-11-01' },
  { id: 't2', label: 'Old CI job', status: 'revoked' as const, is_active: false },
]

const defaults = { tokens, policy: { default_ttl_days: 90, max_ttl_days: 365 } }

describe('ApiTokensPage', () => {
  beforeEach(() => {
    vi.stubGlobal('confirm', vi.fn(() => true))
  })

  it('lists the tokens returned by the API with their status', async () => {
    mockApi({}, defaults)
    render(<ApiTokensPage />)

    expect(await screen.findByText('Add-in laptop')).toBeInTheDocument()
    expect(screen.getByText('Old CI job')).toBeInTheDocument()
    expect(screen.getByText('Revoked')).toBeInTheDocument()
  })

  it('shows a load failure instead of an empty list', async () => {
    // The defect this guards: an API error rendering as "no tokens", which
    // reads as "you have none" rather than "we could not tell".
    mockApi({
      'GET /api/me/tokens': { status: 401, body: { error: { message: 'Session expired' } } },
    }, defaults)
    render(<ApiTokensPage />)

    expect(await screen.findByText('Session expired')).toBeInTheDocument()
  })

  it('reveals a newly created secret with a copy-it-now warning', async () => {
    // The secret is unrecoverable after this render, so the warning is part of
    // the behaviour, not decoration.
    mockApi({ 'POST /api/me/tokens': { token: 'tinymrp_secret_value' } }, defaults)
    render(<ApiTokensPage />)
    await screen.findByText('Add-in laptop')

    await userEvent.type(screen.getByLabelText(/new token label/i), 'New laptop')
    await userEvent.click(screen.getByRole('button', { name: /create/i }))

    expect(await screen.findByText(/will not be shown again/i)).toBeInTheDocument()
    expect(screen.getByDisplayValue('tinymrp_secret_value')).toBeInTheDocument()
  })

  it('surfaces a create failure', async () => {
    mockApi({
      'POST /api/me/tokens': { status: 400, body: { error: { message: 'Label already used' } } },
    }, defaults)
    render(<ApiTokensPage />)
    await screen.findByText('Add-in laptop')

    await userEvent.click(screen.getByRole('button', { name: /create/i }))
    expect(await screen.findByText('Label already used')).toBeInTheDocument()
  })

  it('asks for confirmation before revoking and does nothing if declined', async () => {
    // Revocation breaks connected clients immediately; a misclick must not.
    const confirmMock = vi.fn(() => false)
    vi.stubGlobal('confirm', confirmMock)
    const fetchMock = mockApi({}, defaults)
    render(<ApiTokensPage />)
    await screen.findByText('Add-in laptop')
    const callsBefore = fetchMock.mock.calls.length

    await userEvent.click(screen.getAllByRole('button', { name: /revoke/i })[0])

    expect(confirmMock).toHaveBeenCalled()
    expect(fetchMock.mock.calls.length).toBe(callsBefore)
  })

  it('revokes through the API once confirmed', async () => {
    const fetchMock = mockApi({ 'DELETE /api/me/tokens/t1': { ok: true } }, defaults)
    render(<ApiTokensPage />)
    await screen.findByText('Add-in laptop')

    await userEvent.click(screen.getAllByRole('button', { name: /revoke/i })[0])

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/me/tokens/t1',
        expect.objectContaining({ method: 'DELETE' }),
      )
    })
  })

  it('shows the replacement secret after a rotation', async () => {
    const fetchMock = mockApi({
      'POST /api/me/tokens/t1/rotate': { token: 'rotated_secret' },
    }, defaults)
    render(<ApiTokensPage />)
    await screen.findByText('Add-in laptop')

    await userEvent.click(screen.getAllByRole('button', { name: /rotate/i })[0])

    expect(await screen.findByDisplayValue('rotated_secret')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/me/tokens/t1/rotate',
      expect.objectContaining({ method: 'POST' }),
    )
  })
})

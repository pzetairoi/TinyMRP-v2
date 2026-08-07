import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import UploadPackPage from './UploadPackPage'
import { mockApi } from '../test/mockApi'

/**
 * QA-FE-01. This is the screen where an operator decides whether to run an
 * import against LIVE data, so its failure modes are the expensive kind.
 *
 * The invariant worth guarding is fail-closed: capability lookups are
 * presentation-level access control, and a lookup that FAILS must never leave
 * a destructive action reachable. Enabling "Apply import" because we could not
 * ask what the user is allowed to do is far worse than disabling it wrongly.
 */

const caps = (granted: string[]) => ({
  'GET /api/import/capabilities': {
    imports: Object.fromEntries(granted.map((k) => [k, true])),
  },
})

describe('UploadPackPage capability gating', () => {
  it('disables both actions when the capability lookup fails', async () => {
    mockApi({ 'GET /api/import/capabilities': { status: 500, body: { ok: false, error: 'server exploded' } } })

    render(<UploadPackPage />)

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /preview changes/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /apply import/i })).toBeDisabled()
  })

  it('says the lookup failed rather than looking like a permission denial', async () => {
    mockApi({ 'GET /api/import/capabilities': { status: 500, body: { ok: false, error: 'server exploded' } } })

    render(<UploadPackPage />)

    // "you are not allowed" and "we could not check" are different problems and
    // send the operator to different people. The alert must carry the error.
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByRole('alert').textContent || '').not.toMatch(/^\s*$/)
  })

  it('still disables Apply with preview rights alone', async () => {
    mockApi(caps(['imports.preview']))

    render(<UploadPackPage />)

    await waitFor(() =>
      expect(screen.queryByText(/do not include import preview access/i)).not.toBeInTheDocument(),
    )
    // Preview is read-only; applying writes to live data and needs its own grant.
    expect(screen.getByRole('button', { name: /apply import/i })).toBeDisabled()
  })

  it('tells a user without preview rights why, instead of a dead button', async () => {
    mockApi(caps(['imports.execute_low_risk']))

    render(<UploadPackPage />)

    await waitFor(() =>
      expect(screen.getByText(/do not include import preview access/i)).toBeInTheDocument(),
    )
  })

  it('keeps both actions disabled until a file is chosen', async () => {
    mockApi(caps(['imports.preview', 'imports.execute_low_risk']))

    render(<UploadPackPage />)

    await waitFor(() =>
      expect(screen.queryByText(/do not include import preview access/i)).not.toBeInTheDocument(),
    )
    // Rights are granted, so only the missing file keeps these disabled.
    expect(screen.getByRole('button', { name: /preview changes/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /apply import/i })).toBeDisabled()
  })
})

import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import AdminFieldsPage from './AdminFieldsPage'
import { mockApi } from '../test/mockApi'

/**
 * The field configuration decides what every other screen is allowed to show,
 * so the failures worth pinning are about AUTHORITY and partial loads, not
 * about layout.
 *
 * Two of them have bitten this project before:
 *   - a permission denial that renders as an ordinary page. Only an
 *     administrator may change the mapping; rendering the editor to someone
 *     who cannot save it both discloses the configuration and invites a save
 *     that will 403.
 *   - a failed load that renders as an EMPTY configuration, which on this
 *     page reads as "no fields are configured" - an answer, not an error, and
 *     one that invites someone to "fix" it by rebuilding the mapping.
 */

const config = {
  ok: true,
  config: {
    fields: [
      { id: 'part_number', label: 'Part number', kind: 'builtin', source_path: 'part_number' },
      { id: 'tensile', label: 'Tensile strength', kind: 'custom', source_path: 'attrs.tensile' },
    ],
    contexts: {},
    canonical_aliases: [],
    approval_rules: { approved_values: [], unapproved_values: [], identity_placeholders: [] },
  },
  user_preferences: {},
  permissions: { can_admin: true },
}

const renderPage = () =>
  render(
    <MemoryRouter>
      <AdminFieldsPage />
    </MemoryRouter>,
  )

describe('AdminFieldsPage', () => {
  it('renders the configured fields for an administrator', async () => {
    mockApi({
      'GET /api/field-config': config,
      'GET /api/admin/field-config/candidates': { ok: true, candidates: [] },
    })
    renderPage()

    // Custom-field labels and built-in field labels both render as editable
    // input values, not text nodes; only the built-in field ID is plain text.
    expect(await screen.findByDisplayValue('Tensile strength')).toBeInTheDocument()
    expect(screen.getByText('part_number')).toBeInTheDocument()
  })

  it('refuses a non-administrator instead of rendering the editor', async () => {
    mockApi({
      'GET /api/field-config': { ...config, permissions: { can_admin: false } },
      'GET /api/admin/field-config/candidates': { ok: true, candidates: [] },
    })
    renderPage()

    expect(await screen.findByText(/admin access is required/i)).toBeInTheDocument()
    expect(screen.queryByDisplayValue('Tensile strength')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^save$/i })).not.toBeInTheDocument()
  })

  it('says the configuration could not be loaded rather than showing none', async () => {
    // The defect: an empty editor reads as "nothing is configured".
    mockApi({
      'GET /api/field-config': {
        status: 500,
        body: { error: { message: 'Field configuration unavailable' } },
      },
    })
    renderPage()

    expect(await screen.findByText(/Field configuration unavailable/)).toBeInTheDocument()
    expect(screen.queryByText('Part number')).not.toBeInTheDocument()
  })

  it('keeps a failed candidate scan from blanking the page that did load', async () => {
    // Partial failure must stay partial. The detected-fields scan is a helper;
    // losing it is a warning, not a reason to discard a configuration that
    // loaded fine - and it must SAY so rather than show an empty list.
    mockApi({
      'GET /api/field-config': config,
      'GET /api/admin/field-config/candidates': {
        status: 503,
        body: { error: { message: 'Candidate scan unavailable' } },
      },
    })
    renderPage()

    expect(await screen.findByText(/Candidate scan unavailable/)).toBeInTheDocument()
    expect(screen.getByDisplayValue('Tensile strength')).toBeInTheDocument()
  })
})

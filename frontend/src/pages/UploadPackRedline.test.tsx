import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import UploadPackPage from './UploadPackPage'
import { mockApi } from '../test/mockApi'

/**
 * The redline itself, rendered from a real response shape.
 *
 * The capability tests cover the buttons before an upload happens; nothing
 * covered what the page does once a plan arrives. A crash there took the whole
 * screen down — preview AND apply — because a `<details>` fires `toggle` the
 * moment it mounts, and the handler read `event.currentTarget` inside a
 * setState updater, where React has already nulled it. These tests render a
 * plan so that class of failure cannot ship again.
 */

const CAPS = {
  'GET /api/import/capabilities': {
    imports: {
      'imports.preview': true,
      'imports.execute_low_risk': true,
      'imports.execute_approved': true,
      'imports.override_approved': true,
    },
  },
}

const part = (over: Record<string, unknown> = {}) => ({
  part_number: 'IMPTEST-P01',
  revision: 'B',
  target_state: 'existing_unapproved',
  properties: [
    { field_id: 'material', label: 'Material', before: 'Steel', after: 'Aluminium', action: 'replace', reason: 'Overwrite' },
    { field_id: 'cost', label: 'Cost', before: '10.00', after: '', action: 'clear', reason: 'Not carried by the pack' },
  ],
  approval: [],
  bom: { action: 'unchanged', reason: '', changes: [] },
  files: [],
  changed: true,
  blocked: false,
  allowed: true,
  blocked_change_count: 0,
  ...over,
})

const plan = (parts: unknown[]) => ({
  parts,
  duplicates: [],
  required_permissions: ['parts.update'],
  missing_permissions: [],
  allowed: true,
  blocked_change_count: 0,
  summary: { parts: parts.length, new: 0, changed: 1, blocked: 1, modified_approved: 0 },
})

/** Stub XMLHttpRequest, which is what the page uses so it can show progress. */
function stubUpload(response: Record<string, unknown>) {
  class FakeXhr {
    static instances: FakeXhr[] = []
    upload = { onprogress: null as unknown }
    onload: (() => void) | null = null
    onerror: (() => void) | null = null
    status = 200
    response: unknown = response
    responseType = ''
    sent: FormData | null = null
    open() {}
    send(body: FormData) {
      this.sent = body
      FakeXhr.instances.push(this)
      this.onload?.()
    }
  }
  vi.stubGlobal('XMLHttpRequest', FakeXhr as unknown as typeof XMLHttpRequest)
  return FakeXhr
}

async function previewWith(payload: Record<string, unknown>) {
  mockApi(CAPS)
  stubUpload(payload)
  const { container } = render(<UploadPackPage />)
  await waitFor(() =>
    expect(screen.queryByText(/do not include import preview access/i)).not.toBeInTheDocument(),
  )
  const input = container.querySelector('input[type="file"]') as HTMLInputElement
  await userEvent.upload(input, new File(['zip'], 'pack.zip', { type: 'application/zip' }))
  await userEvent.click(screen.getByRole('button', { name: /preview changes/i }))
  return container
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('UploadPackPage redline', () => {
  it('renders the grouped plan without crashing', async () => {
    await previewWith({
      dry_run: true,
      zip: 'pack.zip',
      plan: plan([part(), part({ part_number: 'IMPTEST-P02', blocked: true, changed: false })]),
    })

    // The banner must say plainly that nothing was written.
    expect(await screen.findByText('PREVIEW')).toBeInTheDocument()
    expect(screen.getByText(/nothing has been written/i)).toBeInTheDocument()
    // Groups carry their counts, and a blocked part is in the blocked group.
    expect(screen.getByText('Blocked')).toBeInTheDocument()
    expect(screen.getByText('Modified')).toBeInTheDocument()
    expect(screen.getByText('IMPTEST-P02 — B')).toBeInTheDocument()
  })

  it('survives opening and closing a group', async () => {
    await previewWith({ dry_run: true, zip: 'pack.zip', plan: plan([part()]) })

    const summary = await screen.findByText('Modified')
    await userEvent.click(summary)
    await userEvent.click(summary)

    expect(screen.getByText('IMPTEST-P01 — B')).toBeInTheDocument()
  })

  it('shows a removal as a clear row with its old value', async () => {
    const container = await previewWith({ dry_run: true, zip: 'pack.zip', plan: plan([part()]) })

    // Overwriting removes what the pack does not carry; a reviewer has to be
    // able to see which value is going.
    await userEvent.click(await screen.findByText('IMPTEST-P01 — B'))
    const table = within(container as HTMLElement)
    expect(table.getByText('Cost')).toBeInTheDocument()
    // Rendered lowercase and capitalised by CSS.
    expect(table.getByText('clear')).toBeInTheDocument()
    expect(table.getByText('10.00')).toBeInTheDocument()
  })

  it('sends the approved override only when the tick is on', async () => {
    // The tick is the only thing standing between an import and released
    // data, so what the page actually SENDS has to be checked, not just the
    // helper that computes it.
    mockApi(CAPS)
    const xhr = stubUpload({ dry_run: true, zip: 'pack.zip', plan: plan([part()]) })
    const { container } = render(<UploadPackPage />)
    await waitFor(() =>
      expect(screen.queryByText(/do not include import preview access/i)).not.toBeInTheDocument(),
    )
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, new File(['zip'], 'pack.zip', { type: 'application/zip' }))

    await userEvent.click(screen.getByRole('button', { name: /overwrite with the pack/i }))
    await userEvent.click(screen.getByRole('button', { name: /preview changes/i }))
    const drafts = xhr.instances.at(-1)!.sent!
    expect(drafts.get('data_mode')).toBe('replace_unapproved')
    expect(drafts.get('bom_mode')).toBe('replace_unapproved')
    expect(drafts.get('file_mode')).toBe('replace_unapproved')
    expect(drafts.get('approval_mode')).toBe('import_unapproved')

    await userEvent.click(screen.getByLabelText(/also overwrite/i))
    await userEvent.click(screen.getByRole('button', { name: /preview changes/i }))
    const approved = xhr.instances.at(-1)!.sent!
    expect(approved.get('data_mode')).toBe('replace_all')
    expect(approved.get('bom_mode')).toBe('replace_all')
    expect(approved.get('file_mode')).toBe('replace_all')
    expect(approved.get('approval_mode')).toBe('replace_all')
  })

  it('keeps the tick out of an Add run entirely', async () => {
    mockApi(CAPS)
    const xhr = stubUpload({ dry_run: true, zip: 'pack.zip', plan: plan([part()]) })
    const { container } = render(<UploadPackPage />)
    await waitFor(() =>
      expect(screen.queryByText(/do not include import preview access/i)).not.toBeInTheDocument(),
    )
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, new File(['zip'], 'pack.zip', { type: 'application/zip' }))

    // Ticked while overwriting, then switched back to Add: the override must
    // not survive the switch.
    await userEvent.click(screen.getByRole('button', { name: /overwrite with the pack/i }))
    await userEvent.click(screen.getByLabelText(/also overwrite/i))
    await userEvent.click(screen.getByRole('button', { name: /add without overwriting/i }))
    await userEvent.click(screen.getByRole('button', { name: /preview changes/i }))

    const sent = xhr.instances.at(-1)!.sent!
    expect(sent.get('data_mode')).toBe('fill_blanks')
    expect(sent.get('approval_mode')).toBe('import_unapproved')
    expect(screen.getByLabelText(/also overwrite/i)).not.toBeChecked()
  })

  it('reports an applied import as written, with its counts', async () => {
    await previewWith({
      dry_run: false,
      zip: 'pack.zip',
      plan: plan([part()]),
      metrics: {
        parts_created: 2,
        parts_updated: 1,
        links_created: 3,
        files_written: 4,
        files_discovered: 5,
        operation_id: 'abcdef1234',
      },
    })

    expect(await screen.findByText('IMPORTED')).toBeInTheDocument()
    expect(screen.getByText(/2 part\(s\) created/)).toBeInTheDocument()
    expect(screen.getByText(/4 file\(s\) written/)).toBeInTheDocument()
  })
})

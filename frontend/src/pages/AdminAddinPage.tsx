import { useEffect, useState } from 'react'
import { apiFetch } from '../lib/api'
import type { ApiError } from '../lib/api'

type User = {
  id: string
  email: string
  roles?: string[]
}

type Token = {
  id: string
  label: string
  created_at?: string
  created_at_display?: string
  last_used_at?: string
  last_used_at_display?: string
  revoked_at?: string
  revoked_at_display?: string
  expires_at?: string
  expires_at_display?: string
}

type Scheme = {
  id?: string
  name: string
  description?: string
  is_active?: boolean
  is_preset?: boolean
  is_recommended?: boolean
  separator?: string
  scope_mode?: string
  scope_keys?: string[]
  seq?: {
    padding?: number
    base?: number
    start_at?: number
    reset_policy?: string
  }
  revision?: {
    policy?: string
    start?: string
  }
  validation_rules?: {
    max_length?: number
    allowed_charset?: string
    require_seq_segment?: boolean
  }
  pattern_segments?: Segment[]
}

type Segment = {
  kind?: string
  value?: string
  field?: string
  casing?: string
  pad_left?: number
  pad_char?: string
  padding?: number
  base?: number
  start_at?: number
  auto_counter?: boolean
  fmt?: string
}

type SegmentKind = 'literal' | 'seq' | 'field' | 'date'

const KIND_LABELS: Record<SegmentKind, string> = {
  literal: 'Fixed text',
  seq: 'Auto counter',
  field: 'Value from CAD form',
  date: 'Date stamp',
}

const DATE_FORMATS: { value: string; label: string }[] = [
  { value: 'YYYY', label: 'Year (2026)' },
  { value: 'YY', label: 'Short year (26)' },
  { value: 'MM', label: 'Month (07)' },
  { value: 'YYYYMM', label: 'Year + month (202607)' },
]

const EMPTY_SCHEME: Scheme = {
  name: '',
  description: '',
  is_active: true,
  separator: '-',
  scope_mode: 'global',
  scope_keys: [],
  seq: { padding: 6, base: 10, start_at: 1, reset_policy: 'never' },
  revision: { policy: 'none', start: '' },
  validation_rules: { max_length: 32, allowed_charset: 'A-Z0-9-', require_seq_segment: true },
  pattern_segments: [],
}

const DEFAULT_NEW_SEGMENTS: Segment[] = [
  { kind: 'literal', value: 'PART' },
  { kind: 'seq', padding: 6, base: 10, start_at: 1, auto_counter: true },
]

function getSegmentKind(segment?: Segment): SegmentKind {
  const kind = (segment?.kind || '').trim().toLowerCase()
  if (kind === 'seq' || kind === 'field' || kind === 'date') return kind
  return 'literal'
}

function createEmptySegment(kind: SegmentKind = 'literal'): Segment {
  if (kind === 'seq') return { kind: 'seq', padding: 6, base: 10, start_at: 1, auto_counter: false }
  if (kind === 'field') return { kind: 'field', field: '', casing: 'upper' }
  if (kind === 'date') return { kind: 'date', fmt: 'YYYY' }
  return { kind: 'literal', value: '' }
}

function cloneSegment(segment?: Segment): Segment {
  return { ...createEmptySegment(getSegmentKind(segment)), ...(segment || {}) }
}

function cloneScheme(scheme?: Partial<Scheme>): Scheme {
  return {
    ...EMPTY_SCHEME,
    ...scheme,
    scope_keys: [...(scheme?.scope_keys || EMPTY_SCHEME.scope_keys || [])],
    seq: { ...EMPTY_SCHEME.seq, ...(scheme?.seq || {}) },
    revision: { ...EMPTY_SCHEME.revision, ...(scheme?.revision || {}) },
    validation_rules: { ...EMPTY_SCHEME.validation_rules, ...(scheme?.validation_rules || {}) },
    pattern_segments: (scheme?.pattern_segments || []).map(cloneSegment),
  }
}

// Exactly one counter is assigned by the server. If the user marks several, keep the first;
// if none, promote the first counter.
function normalizeSequenceSegments(items: Segment[]) {
  const next = items.map(cloneSegment)
  const sequenceIndexes = next
    .map((segment, index) => ({ segment, index }))
    .filter(({ segment }) => getSegmentKind(segment) === 'seq')
    .map(({ index }) => index)

  if (!sequenceIndexes.length) {
    return next
  }

  let autoIndex = -1
  sequenceIndexes.forEach((index) => {
    if (!next[index].auto_counter) return
    if (autoIndex === -1) {
      autoIndex = index
      return
    }
    next[index] = { ...next[index], auto_counter: false }
  })

  if (autoIndex === -1) {
    const first = sequenceIndexes[0]
    next[first] = { ...next[first], auto_counter: true }
  }

  return next
}

function padCounter(value: number, width: number, base: number) {
  const safe = Math.max(1, Math.floor(value) || 1)
  const text = base === 36 ? safe.toString(36).toUpperCase() : String(safe)
  return text.padStart(Math.max(width, 1), '0')
}

function formatDateSample(fmt?: string) {
  const now = new Date()
  const yyyy = String(now.getFullYear())
  const mm = String(now.getMonth() + 1).padStart(2, '0')
  if (fmt === 'YY') return yyyy.slice(-2)
  if (fmt === 'MM') return mm
  if (fmt === 'YYYYMM') return `${yyyy}${mm}`
  return yyyy
}

function segmentSample(segment: Segment): string {
  const kind = getSegmentKind(segment)
  if (kind === 'literal') return (segment.value || '').trim()
  if (kind === 'seq') return padCounter(segment.start_at ?? 1, segment.padding ?? 6, segment.base ?? 10)
  if (kind === 'date') return formatDateSample(segment.fmt)
  const name = (segment.field || 'value').trim() || 'value'
  const casing = (segment.casing || 'upper').toLowerCase()
  if (casing === 'lower') return name.toLowerCase()
  if (casing === 'none') return name
  return name.toUpperCase()
}

function buildSampleNumber(segments: Segment[], separator: string) {
  const pieces = segments.map(segmentSample).filter(Boolean)
  return pieces.join(separator || '')
}

function segmentLabel(segment: Segment) {
  const kind = getSegmentKind(segment)
  if (kind === 'literal') return `Fixed text: "${segment.value || ''}"`
  if (kind === 'seq') {
    const digits = segment.padding ?? 6
    const style = (segment.base ?? 10) === 36 ? 'letters+numbers' : 'numbers'
    const auto = segment.auto_counter ? 'assigned by server' : `starts at ${segment.start_at ?? 1}`
    return `Auto counter: ${digits} digits, ${style}, ${auto}`
  }
  if (kind === 'date') {
    const fmt = DATE_FORMATS.find((f) => f.value === segment.fmt)
    return `Date stamp: ${fmt ? fmt.label : segment.fmt || 'YYYY'}`
  }
  return `CAD form value: "${segment.field || ''}"`
}

function revisionSample(policy?: string, start?: string) {
  const p = (policy || 'none').toLowerCase()
  if (p === 'alpha') return (start || 'A').toUpperCase()
  if (p === 'numeric') return start && start.trim() ? start.trim() : '01'
  return ''
}

function formatApiError(err: unknown, fallback: string) {
  const apiError = err as ApiError
  if (apiError?.details?.length) {
    return `${apiError.message || fallback} ${apiError.details.join(' ')}`
  }
  return apiError?.message || fallback
}

function createBuilderState(source?: Scheme) {
  if (!source) {
    return {
      scheme: cloneScheme({ pattern_segments: DEFAULT_NEW_SEGMENTS }),
      segments: normalizeSequenceSegments(DEFAULT_NEW_SEGMENTS),
    }
  }
  const scheme = cloneScheme(source)
  scheme.id = undefined
  scheme.name = source.name ? `${source.name} copy` : ''
  scheme.is_active = true
  scheme.is_preset = false
  scheme.is_recommended = false
  return {
    scheme,
    segments: normalizeSequenceSegments(scheme.pattern_segments || []),
  }
}

export default function AdminAddinPage() {
  const [users, setUsers] = useState<User[]>([])
  const [selectedUser, setSelectedUser] = useState<User | null>(null)
  const [tokens, setTokens] = useState<Token[]>([])
  const [schemes, setSchemes] = useState<Scheme[]>([])
  const [enabledDrafts, setEnabledDrafts] = useState<Record<string, boolean>>({})
  const [copyFromId, setCopyFromId] = useState('')
  const [editingScheme, setEditingScheme] = useState<Scheme>(createBuilderState().scheme)
  const [segments, setSegments] = useState<Segment[]>(createBuilderState().segments)
  const [editorIndex, setEditorIndex] = useState(-1) // -1 = adding a new piece
  const [segmentDraft, setSegmentDraft] = useState<Segment>(createEmptySegment())
  const [savingEnabledChanges, setSavingEnabledChanges] = useState(false)
  const [serverExample, setServerExample] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void loadUsers()
    void loadSchemes()
  }, [])

  const changedEnabledCount = schemes.filter((scheme) => {
    if (!scheme.id) return false
    return (enabledDrafts[scheme.id] ?? !!scheme.is_active) !== !!scheme.is_active
  }).length

  const sampleNumber = buildSampleNumber(segments, editingScheme.separator || '-')
  const sampleRevision = revisionSample(editingScheme.revision?.policy, editingScheme.revision?.start)
  const revisionPolicy = (editingScheme.revision?.policy || 'none').toLowerCase()

  async function loadUsers() {
    setError(null)
    try {
      const resp = await apiFetch<{ users: User[] }>('/api/admin/users')
      setUsers(resp.users || [])
    } catch (err) {
      setError(formatApiError(err, 'Failed to load users.'))
    }
  }

  async function loadUserTokens(user: User) {
    setError(null)
    try {
      const resp = await apiFetch<{ tokens: Token[] }>(`/api/admin/users/${user.id}/tokens`)
      setSelectedUser(user)
      setTokens(resp.tokens || [])
    } catch (err) {
      setError(formatApiError(err, 'Failed to load tokens.'))
    }
  }

  async function revokeToken(userId: string, tokenId: string) {
    setError(null)
    setMessage(null)
    try {
      await apiFetch(`/api/admin/users/${userId}/tokens/${tokenId}`, { method: 'DELETE' })
      setMessage('Token revoked.')
      if (selectedUser) {
        await loadUserTokens(selectedUser)
      }
    } catch (err) {
      setError(formatApiError(err, 'Failed to revoke token.'))
    }
  }

  async function loadSchemes() {
    setError(null)
    try {
      const resp = await apiFetch<{ schemes: Scheme[] }>('/api/numbering/schemes')
      const nextSchemes = resp.schemes || []
      const nextEnabledDrafts: Record<string, boolean> = {}
      for (const scheme of nextSchemes) {
        if (scheme.id) {
          nextEnabledDrafts[scheme.id] = !!scheme.is_active
        }
      }
      setSchemes(nextSchemes)
      setEnabledDrafts(nextEnabledDrafts)
    } catch (err) {
      setError(formatApiError(err, 'Failed to load schemes.'))
    }
  }

  async function saveEnabledChanges() {
    setError(null)
    setMessage(null)

    const changedSchemes = schemes.filter((scheme) => {
      if (!scheme.id) return false
      return (enabledDrafts[scheme.id] ?? !!scheme.is_active) !== !!scheme.is_active
    })

    if (!changedSchemes.length) {
      setMessage('Nothing to save: no scheme was enabled or disabled.')
      return
    }

    setSavingEnabledChanges(true)
    try {
      for (const scheme of changedSchemes) {
        await apiFetch(`/api/numbering/schemes/${scheme.id}`, {
          method: 'PUT',
          body: JSON.stringify({
            name: scheme.name,
            is_active: enabledDrafts[scheme.id!],
          }),
        })
      }
      await loadSchemes()
      setMessage(`${changedSchemes.length} scheme${changedSchemes.length === 1 ? '' : 's'} updated.`)
    } catch (err) {
      setError(formatApiError(err, 'Failed to save changes.'))
    } finally {
      setSavingEnabledChanges(false)
    }
  }

  async function deleteScheme(scheme: Scheme) {
    setError(null)
    setMessage(null)
    if (!scheme.id) return
    if (!window.confirm(`Delete the scheme "${scheme.name}"? Parts already numbered with it are not affected, but this cannot be undone.`)) {
      return
    }
    try {
      await apiFetch(`/api/numbering/schemes/${scheme.id}`, { method: 'DELETE' })
      setMessage(`Scheme "${scheme.name}" deleted.`)
      if (copyFromId === scheme.id) {
        setCopyFromId('')
      }
      await loadSchemes()
    } catch (err) {
      setError(formatApiError(err, 'Failed to delete scheme.'))
    }
  }

  function startBuilderFrom(sourceId: string) {
    setCopyFromId(sourceId)
    setServerExample(null)
    setError(null)
    setMessage(null)
    const source = sourceId ? schemes.find((scheme) => scheme.id === sourceId) : undefined
    const next = createBuilderState(source)
    setEditingScheme(next.scheme)
    setSegments(next.segments)
    setEditorIndex(-1)
    setSegmentDraft(createEmptySegment())
  }

  function updateEditingScheme(patch: Partial<Scheme>) {
    setServerExample(null)
    setEditingScheme((prev) => ({ ...prev, ...patch }))
  }

  function getLocalSchemeErrors(requireName: boolean) {
    const errors: string[] = []
    if (requireName && !(editingScheme.name || '').trim()) {
      errors.push('Give the scheme a name.')
    }

    if (!segments.length) {
      errors.push('Add at least one piece to the number pattern.')
      return errors
    }

    let hasSequence = false
    segments.forEach((segment, index) => {
      const kind = getSegmentKind(segment)
      if (kind === 'literal' && !(segment.value || '').trim()) {
        errors.push(`Piece ${index + 1}: the fixed text is empty.`)
      }
      if (kind === 'field' && !(segment.field || '').trim()) {
        errors.push(`Piece ${index + 1}: enter the CAD form field name (e.g. project).`)
      }
      if (kind === 'seq') {
        hasSequence = true
        const digits = Number(segment.padding ?? 6)
        if (!Number.isFinite(digits) || digits < 1) {
          errors.push(`Piece ${index + 1}: the counter needs at least 1 digit.`)
        }
        const start = Number(segment.start_at ?? 1)
        if (!Number.isFinite(start) || start < 1) {
          errors.push(`Piece ${index + 1}: the counter must start at 1 or higher.`)
        }
      }
    })

    if (!hasSequence) {
      errors.push('Add an auto counter piece: it is what makes each number unique.')
    }

    return errors
  }

  function buildSchemePayload() {
    const normalizedSegments = normalizeSequenceSegments(segments)
    const autoSeqSegment = normalizedSegments.find((segment) => getSegmentKind(segment) === 'seq' && segment.auto_counter)
    const firstSeqSegment = normalizedSegments.find((segment) => getSegmentKind(segment) === 'seq')
    const seqSource = autoSeqSegment || firstSeqSegment

    const policy = (editingScheme.revision?.policy || 'none').toLowerCase()
    const revisionStart = policy === 'none' ? '' : (editingScheme.revision?.start || '').trim()

    return {
      name: (editingScheme.name || '').trim(),
      is_active: !!editingScheme.is_active,
      separator: editingScheme.separator || '-',
      scope_mode: editingScheme.scope_mode || 'global',
      scope_keys: [...(editingScheme.scope_keys || [])],
      seq: {
        padding: Number(seqSource?.padding ?? 6),
        base: Number(seqSource?.base ?? 10),
        start_at: Number(seqSource?.start_at ?? 1),
        reset_policy: editingScheme.seq?.reset_policy || 'never',
      },
      revision: {
        policy,
        start: revisionStart,
      },
      validation_rules: {
        max_length: Number(editingScheme.validation_rules?.max_length ?? 32),
        allowed_charset: editingScheme.validation_rules?.allowed_charset || 'A-Z0-9-',
        require_seq_segment: editingScheme.validation_rules?.require_seq_segment ?? true,
      },
      pattern_segments: normalizedSegments.map((segment) => {
        const kind = getSegmentKind(segment)
        if (kind === 'literal') {
          return { kind, value: segment.value || '' }
        }
        if (kind === 'seq') {
          return {
            kind,
            padding: Number(segment.padding ?? 6),
            base: Number(segment.base ?? 10),
            start_at: Number(segment.start_at ?? 1),
            auto_counter: !!segment.auto_counter,
          }
        }
        if (kind === 'date') {
          return { kind, fmt: segment.fmt || 'YYYY' }
        }
        return {
          kind: 'field',
          field: (segment.field || '').trim(),
          casing: segment.casing || 'upper',
        }
      }),
    }
  }

  async function checkSchemeWithServer() {
    setError(null)
    setMessage(null)
    setServerExample(null)
    const localErrors = getLocalSchemeErrors(false)
    if (localErrors.length) {
      setError(localErrors.join(' '))
      return
    }
    try {
      const payload = buildSchemePayload()
      const resp = await apiFetch<{ example: { part_number_example?: string; revision_example?: string } }>(
        '/api/numbering/schemes/validate',
        {
          method: 'POST',
          body: JSON.stringify(payload),
        },
      )
      const example = resp.example || {}
      const pieces = [example.part_number_example || '']
      if (example.revision_example) {
        pieces.push(`revision ${example.revision_example}`)
      }
      setServerExample(pieces.filter(Boolean).join(' — '))
      setMessage('The scheme is valid.')
    } catch (err) {
      setError(formatApiError(err, 'The scheme is not valid yet.'))
    }
  }

  async function createScheme() {
    setError(null)
    setMessage(null)

    const localErrors = getLocalSchemeErrors(true)
    if (localErrors.length) {
      setError(localErrors.join(' '))
      return
    }

    try {
      const payload = buildSchemePayload()
      await apiFetch<{ scheme: Scheme }>('/api/numbering/schemes', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setMessage(`Scheme "${payload.name}" created.`)
      await loadSchemes()
      startBuilderFrom('')
    } catch (err) {
      setError(formatApiError(err, 'Failed to create the scheme.'))
    }
  }

  function applyDraft() {
    const kind = getSegmentKind(segmentDraft)
    if (kind === 'literal' && !(segmentDraft.value || '').trim()) {
      setError('Enter the fixed text first.')
      return
    }
    if (kind === 'field' && !(segmentDraft.field || '').trim()) {
      setError('Enter the CAD form field name first (e.g. project).')
      return
    }

    setError(null)
    setServerExample(null)
    const nextSegment = cloneSegment(segmentDraft)
    if (editorIndex >= 0) {
      setSegments((prev) => normalizeSequenceSegments(prev.map((segment, index) => (index === editorIndex ? nextSegment : segment))))
    } else {
      setSegments((prev) => normalizeSequenceSegments([...prev, nextSegment]))
    }
    setEditorIndex(-1)
    setSegmentDraft(createEmptySegment())
  }

  function editSegment(index: number) {
    setEditorIndex(index)
    setSegmentDraft(cloneSegment(segments[index]))
  }

  function cancelEdit() {
    setEditorIndex(-1)
    setSegmentDraft(createEmptySegment())
  }

  function removeSegment(index: number) {
    setServerExample(null)
    setSegments((prev) => normalizeSequenceSegments(prev.filter((_, i) => i !== index)))
    if (editorIndex === index) {
      cancelEdit()
    }
  }

  function moveSegment(index: number, delta: number) {
    const target = index + delta
    if (target < 0 || target >= segments.length) return
    setServerExample(null)
    const next = [...segments]
    const [item] = next.splice(index, 1)
    next.splice(target, 0, item)
    setSegments(normalizeSequenceSegments(next))
    if (editorIndex === index) {
      setEditorIndex(target)
    }
  }

  function setDraftKind(kind: SegmentKind) {
    setSegmentDraft((prev) => (getSegmentKind(prev) === kind ? prev : createEmptySegment(kind)))
  }

  function renderTokenDate(display?: string, fallback?: string) {
    return display || fallback || '-'
  }

  const draftKind = getSegmentKind(segmentDraft)

  return (
    <div className="p-3">
      <h3 className="mb-3">Add-in Admin</h3>
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-danger">{error}</div>}

      <div className="card p-3 mb-4">
        <h5>Users</h5>
        <div className="table-responsive">
          <table className="table table-sm">
            <thead>
              <tr>
                <th>Email</th>
                <th>Roles</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.email}</td>
                  <td>{user.roles?.join(', ') || '-'}</td>
                  <td>
                    <button className="btn btn-sm btn-outline-secondary" onClick={() => void loadUserTokens(user)}>
                      View tokens
                    </button>
                  </td>
                </tr>
              ))}
              {!users.length && (
                <tr>
                  <td colSpan={3} className="text-muted text-center">
                    No users.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {selectedUser && (
          <div className="mt-3">
            <h6>Tokens for {selectedUser.email}</h6>
            <div className="table-responsive">
              <table className="table table-sm">
                <thead>
                  <tr>
                    <th>Label</th>
                    <th>Created</th>
                    <th>Last used</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {tokens.map((token) => (
                    <tr key={token.id}>
                      <td>{token.label || '(no label)'}</td>
                      <td>{renderTokenDate(token.created_at_display, token.created_at)}</td>
                      <td>{renderTokenDate(token.last_used_at_display, token.last_used_at)}</td>
                      <td>{token.revoked_at ? 'Revoked' : 'Active'}</td>
                      <td>
                        {!token.revoked_at && (
                          <button
                            className="btn btn-sm btn-outline-danger"
                            onClick={() => void revokeToken(selectedUser.id, token.id)}
                          >
                            Revoke
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {!tokens.length && (
                    <tr>
                      <td colSpan={5} className="text-muted text-center">
                        No tokens.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <div className="card p-3">
        <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-2">
          <h5 className="mb-0">Part numbering schemes</h5>
          <button
            className="btn btn-sm btn-primary"
            onClick={() => void saveEnabledChanges()}
            disabled={savingEnabledChanges || changedEnabledCount === 0}
          >
            Save changes{changedEnabledCount > 0 ? ` (${changedEnabledCount})` : ''}
          </button>
        </div>
        <p className="text-muted small mb-2">
          A scheme cannot be modified once created, because numbers already issued depend on it. To change one, create
          a new scheme below (you can start from a copy), then disable or delete the old one.
        </p>
        <div className="table-responsive">
          <table className="table table-sm align-middle">
            <thead>
              <tr>
                <th>Name</th>
                <th>Example</th>
                <th>Enabled</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {schemes.map((scheme) => (
                <tr key={scheme.id}>
                  <td>{scheme.name}</td>
                  <td className="text-muted">
                    <code>{buildSampleNumber(scheme.pattern_segments || [], scheme.separator || '-') || '-'}</code>
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      checked={scheme.id ? enabledDrafts[scheme.id] ?? !!scheme.is_active : !!scheme.is_active}
                      onChange={(e) => {
                        if (!scheme.id) return
                        setEnabledDrafts((prev) => ({ ...prev, [scheme.id!]: e.target.checked }))
                      }}
                    />
                  </td>
                  <td className="text-end">
                    <button className="btn btn-sm btn-outline-danger" onClick={() => void deleteScheme(scheme)} disabled={!scheme.id}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {!schemes.length && (
                <tr>
                  <td colSpan={4} className="text-muted text-center">
                    No schemes.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card p-3 mt-4">
        <h5>Create a new scheme</h5>
        <p className="text-muted small">
          A part number is built from pieces joined by the separator. Example: fixed text <code>PART</code> + a
          6-digit auto counter with separator <code>-</code> gives <code>PART-000001</code>.
        </p>

        <div className="row g-2 mb-3">
          <div className="col-md-4">
            <label className="form-label small">Start from</label>
            <select className="form-select" value={copyFromId} onChange={(e) => startBuilderFrom(e.target.value)}>
              <option value="">Blank</option>
              {schemes.map((scheme) => (
                <option key={scheme.id} value={scheme.id}>
                  Copy of: {scheme.name}
                </option>
              ))}
            </select>
          </div>
          <div className="col-md-4">
            <label className="form-label small">Scheme name</label>
            <input
              className="form-control"
              placeholder="e.g. Machined parts"
              value={editingScheme.name || ''}
              onChange={(e) => updateEditingScheme({ name: e.target.value })}
            />
          </div>
          <div className="col-md-2">
            <label className="form-label small">Separator</label>
            <input
              className="form-control"
              value={editingScheme.separator || '-'}
              onChange={(e) => updateEditingScheme({ separator: e.target.value })}
            />
          </div>
          <div className="col-md-2">
            <label className="form-label small d-block">Enabled</label>
            <div className="form-check pt-2">
              <input
                className="form-check-input"
                type="checkbox"
                checked={!!editingScheme.is_active}
                onChange={(e) => updateEditingScheme({ is_active: e.target.checked })}
                id="schemeActiveCheck"
              />
              <label className="form-check-label" htmlFor="schemeActiveCheck">
                Ready to use
              </label>
            </div>
          </div>
        </div>

        <div className="mb-3">
          <h6>Number pattern</h6>
          <div className="row g-3">
            <div className="col-md-6">
              <ul className="list-group">
                {segments.map((segment, index) => (
                  <li
                    key={`${segment.kind || 'segment'}-${index}`}
                    className={`list-group-item d-flex justify-content-between align-items-center ${
                      index === editorIndex ? 'active' : ''
                    }`}
                  >
                    <span onClick={() => editSegment(index)} style={{ cursor: 'pointer', flexGrow: 1 }}>
                      {segmentLabel(segment)}
                    </span>
                    <span className="d-flex gap-1">
                      <button
                        className="btn btn-sm btn-outline-secondary py-0"
                        title="Move up"
                        onClick={() => moveSegment(index, -1)}
                        disabled={index === 0}
                      >
                        ↑
                      </button>
                      <button
                        className="btn btn-sm btn-outline-secondary py-0"
                        title="Move down"
                        onClick={() => moveSegment(index, 1)}
                        disabled={index === segments.length - 1}
                      >
                        ↓
                      </button>
                      <button
                        className="btn btn-sm btn-outline-danger py-0"
                        title="Remove"
                        onClick={() => removeSegment(index)}
                      >
                        ✕
                      </button>
                    </span>
                  </li>
                ))}
                {!segments.length && <li className="list-group-item text-muted">No pieces yet - add one on the right.</li>}
              </ul>
              <div className="mt-2 small text-muted">Click a piece to edit it. Use the arrows to reorder.</div>
            </div>

            <div className="col-md-6">
              <label className="form-label small">{editorIndex >= 0 ? `Editing piece ${editorIndex + 1}` : 'Add a piece'}</label>
              <select
                className="form-select mb-2"
                value={draftKind}
                onChange={(e) => setDraftKind(e.target.value as SegmentKind)}
              >
                {(Object.keys(KIND_LABELS) as SegmentKind[]).map((kind) => (
                  <option key={kind} value={kind}>
                    {KIND_LABELS[kind]}
                  </option>
                ))}
              </select>

              {draftKind === 'literal' && (
                <>
                  <label className="form-label small">Text</label>
                  <input
                    className="form-control mb-2"
                    placeholder="e.g. PART"
                    value={segmentDraft.value || ''}
                    onChange={(e) => setSegmentDraft({ ...segmentDraft, kind: 'literal', value: e.target.value })}
                  />
                </>
              )}

              {draftKind === 'seq' && (
                <div className="row g-2">
                  <div className="col-md-6">
                    <label className="form-label small">Digits</label>
                    <input
                      className="form-control mb-2"
                      type="number"
                      min={1}
                      value={segmentDraft.padding ?? 6}
                      onChange={(e) =>
                        setSegmentDraft({ ...segmentDraft, kind: 'seq', padding: Math.max(1, Number(e.target.value) || 1) })
                      }
                    />
                  </div>
                  <div className="col-md-6">
                    <label className="form-label small">Counting style</label>
                    <select
                      className="form-select mb-2"
                      value={segmentDraft.base ?? 10}
                      onChange={(e) => setSegmentDraft({ ...segmentDraft, kind: 'seq', base: Number(e.target.value) })}
                    >
                      <option value={10}>Numbers (0-9)</option>
                      <option value={36}>Letters + numbers (0-9, A-Z)</option>
                    </select>
                  </div>
                  <div className="col-md-6">
                    <label className="form-label small">Starts at</label>
                    <input
                      className="form-control mb-2"
                      type="number"
                      min={1}
                      value={segmentDraft.start_at ?? 1}
                      onChange={(e) =>
                        setSegmentDraft({ ...segmentDraft, kind: 'seq', start_at: Math.max(1, Number(e.target.value) || 1) })
                      }
                    />
                  </div>
                  <div className="col-md-6">
                    <label className="form-label small d-block">Numbering</label>
                    <div className="form-check pt-2">
                      <input
                        className="form-check-input"
                        id="segmentAutoCounter"
                        type="checkbox"
                        checked={!!segmentDraft.auto_counter}
                        onChange={(e) => setSegmentDraft({ ...segmentDraft, kind: 'seq', auto_counter: e.target.checked })}
                      />
                      <label className="form-check-label small" htmlFor="segmentAutoCounter">
                        Server assigns the next free number
                      </label>
                    </div>
                  </div>
                  <div className="col-12">
                    <div className="small text-muted mb-2">One counter per scheme is assigned by the server; it is what makes numbers unique.</div>
                  </div>
                </div>
              )}

              {draftKind === 'field' && (
                <div className="row g-2">
                  <div className="col-md-6">
                    <label className="form-label small">CAD form field</label>
                    <input
                      className="form-control mb-2"
                      placeholder="e.g. project, type, family"
                      value={segmentDraft.field || ''}
                      onChange={(e) => setSegmentDraft({ ...segmentDraft, kind: 'field', field: e.target.value })}
                    />
                  </div>
                  <div className="col-md-6">
                    <label className="form-label small">Letter case</label>
                    <select
                      className="form-select mb-2"
                      value={segmentDraft.casing || 'upper'}
                      onChange={(e) => setSegmentDraft({ ...segmentDraft, kind: 'field', casing: e.target.value })}
                    >
                      <option value="upper">UPPERCASE</option>
                      <option value="lower">lowercase</option>
                      <option value="none">As typed</option>
                    </select>
                  </div>
                  <div className="col-12">
                    <div className="small text-muted mb-2">
                      The value is typed in the SolidWorks add-in when a number is requested (e.g. project = MECS).
                    </div>
                  </div>
                </div>
              )}

              {draftKind === 'date' && (
                <>
                  <label className="form-label small">Format</label>
                  <select
                    className="form-select mb-2"
                    value={segmentDraft.fmt || 'YYYY'}
                    onChange={(e) => setSegmentDraft({ ...segmentDraft, kind: 'date', fmt: e.target.value })}
                  >
                    {DATE_FORMATS.map((fmt) => (
                      <option key={fmt.value} value={fmt.value}>
                        {fmt.label}
                      </option>
                    ))}
                  </select>
                </>
              )}

              <div className="d-flex gap-2 flex-wrap">
                <button className="btn btn-sm btn-primary" onClick={applyDraft}>
                  {editorIndex >= 0 ? 'Update piece' : 'Add piece'}
                </button>
                {editorIndex >= 0 && (
                  <button className="btn btn-sm btn-outline-secondary" onClick={cancelEdit}>
                    Cancel edit
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="row g-2 mb-3">
          <div className="col-md-4">
            <label className="form-label small">Revision for new parts</label>
            <select
              className="form-select"
              value={revisionPolicy}
              onChange={(e) =>
                updateEditingScheme({
                  revision: {
                    policy: e.target.value,
                    start: e.target.value === 'alpha' ? 'A' : e.target.value === 'numeric' ? '01' : '',
                  },
                })
              }
            >
              <option value="none">No revision (recommended)</option>
              <option value="alpha">Letters: A, B, C...</option>
              <option value="numeric">Numbers: 01, 02, 03...</option>
            </select>
          </div>
          {revisionPolicy !== 'none' && (
            <div className="col-md-2">
              <label className="form-label small">First revision</label>
              <input
                className="form-control"
                value={editingScheme.revision?.start || ''}
                onChange={(e) =>
                  updateEditingScheme({ revision: { policy: revisionPolicy, start: e.target.value } })
                }
              />
            </div>
          )}
          <div className="col-md-6">
            <label className="form-label small d-block">Preview</label>
            <div className="pt-1">
              <code>{sampleNumber || '-'}</code>
              {sampleRevision && (
                <span className="text-muted small"> (first revision: {sampleRevision})</span>
              )}
              {serverExample && <div className="small text-success">Server check: {serverExample}</div>}
            </div>
          </div>
        </div>

        <div className="d-flex gap-2 flex-wrap">
          <button className="btn btn-outline-secondary" onClick={() => void checkSchemeWithServer()}>
            Check &amp; preview
          </button>
          <button className="btn btn-primary" onClick={() => void createScheme()}>
            Create scheme
          </button>
        </div>
      </div>
    </div>
  )
}

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
  last_used_at?: string
  revoked_at?: string
}

type Scheme = {
  id?: string
  name: string
  description?: string
  is_active?: boolean
  is_preset?: boolean
  is_recommended?: boolean
  visibility?: string
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
  fmt?: string
}

const SIMPLE_SEGMENT_KINDS = new Set(['literal', 'seq'])

const EMPTY_SCHEME: Scheme = {
  name: '',
  description: '',
  is_active: true,
  separator: '-',
  scope_mode: 'global',
  scope_keys: [],
  seq: { padding: 6, base: 10, start_at: 1, reset_policy: 'never' },
  revision: { policy: 'alpha', start: 'A' },
  validation_rules: { max_length: 32, allowed_charset: 'A-Z0-9-', require_seq_segment: true },
  pattern_segments: [],
}

const DEFAULT_NEW_SEGMENTS: Segment[] = [
  { kind: 'literal', value: 'PART' },
  { kind: 'seq', padding: 6, base: 10 },
]

function createEmptySegment(kind: 'literal' | 'seq' = 'literal'): Segment {
  if (kind === 'seq') {
    return { kind: 'seq', padding: 6, base: 10 }
  }
  return { kind: 'literal', value: '' }
}

function cloneSegment(segment?: Segment): Segment {
  const kind = getSegmentKind(segment)
  if (kind === 'seq') {
    return { ...createEmptySegment('seq'), ...segment }
  }
  if (kind === 'literal') {
    return { ...createEmptySegment('literal'), ...segment }
  }
  return { ...(segment || {}) }
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

function getSegmentKind(segment?: Segment) {
  return (segment?.kind || '').trim().toLowerCase()
}

function getUnsupportedSegmentKinds(items: Segment[]) {
  const kinds = new Set<string>()
  for (const segment of items) {
    const kind = getSegmentKind(segment)
    if (kind && !SIMPLE_SEGMENT_KINDS.has(kind)) {
      kinds.add(kind)
    }
  }
  return Array.from(kinds)
}

function segmentLabel(segment: Segment, index: number) {
  const kind = getSegmentKind(segment)
  if (!kind) return `Segment ${index + 1}`
  if (kind === 'literal') return `Literal: ${segment.value || ''}`
  if (kind === 'seq') return `Sequence: pad ${segment.padding ?? 6}, base ${segment.base ?? 10}`
  if (kind === 'field') return `Legacy field: ${segment.field || ''}`
  if (kind === 'date') return `Legacy date: ${segment.fmt || ''}`
  return `Legacy ${kind}`
}

function formatApiError(err: unknown, fallback: string) {
  const apiError = err as ApiError
  if (apiError?.details?.length) {
    return `${apiError.message || fallback} ${apiError.details.join(' ')}`
  }
  return apiError?.message || fallback
}

function createNewSchemeState() {
  const scheme = cloneScheme({
    seq: { ...EMPTY_SCHEME.seq, start_at: 1 },
    pattern_segments: DEFAULT_NEW_SEGMENTS,
  })
  const segments = DEFAULT_NEW_SEGMENTS.map(cloneSegment)
  return {
    scheme,
    segments,
    draft: cloneSegment(DEFAULT_NEW_SEGMENTS[0]),
  }
}

export default function AdminAddinPage() {
  const [users, setUsers] = useState<User[]>([])
  const [selectedUser, setSelectedUser] = useState<User | null>(null)
  const [tokens, setTokens] = useState<Token[]>([])
  const [schemes, setSchemes] = useState<Scheme[]>([])
  const [enabledDrafts, setEnabledDrafts] = useState<Record<string, boolean>>({})
  const [selectedSchemeId, setSelectedSchemeId] = useState('')
  const [editingScheme, setEditingScheme] = useState<Scheme>(cloneScheme())
  const [segments, setSegments] = useState<Segment[]>([])
  const [selectedSegmentIndex, setSelectedSegmentIndex] = useState(-1)
  const [segmentDraft, setSegmentDraft] = useState<Segment>(createEmptySegment())
  const [savingEnabledChanges, setSavingEnabledChanges] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void loadUsers()
    void loadSchemes()
  }, [])

  useEffect(() => {
    if (!selectedSchemeId) {
      const next = createNewSchemeState()
      setEditingScheme(next.scheme)
      setSegments(next.segments)
      setSelectedSegmentIndex(-1)
      setSegmentDraft(next.draft)
      return
    }

    const found = schemes.find((scheme) => scheme.id === selectedSchemeId)
    if (!found) {
      return
    }

    const nextScheme = cloneScheme(found)
    setEditingScheme(nextScheme)
    setSegments(nextScheme.pattern_segments || [])
    setSelectedSegmentIndex(-1)
    setSegmentDraft(createEmptySegment())
  }, [selectedSchemeId, schemes])

  const legacySegmentKinds = getUnsupportedSegmentKinds(segments)
  const hasLegacySegments = legacySegmentKinds.length > 0
  const changedEnabledCount = schemes.filter((scheme) => {
    if (!scheme.id) return false
    return (enabledDrafts[scheme.id] ?? !!scheme.is_active) !== !!scheme.is_active
  }).length

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
      setMessage('No enabled changes to save.')
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
      setError(formatApiError(err, 'Failed to save enabled changes.'))
    } finally {
      setSavingEnabledChanges(false)
    }
  }

  function updateEditingScheme(patch: Partial<Scheme>) {
    setEditingScheme((prev) => ({ ...prev, ...patch }))
  }

  function getLocalSchemeErrors(requireName: boolean) {
    const errors: string[] = []
    if (requireName && !(editingScheme.name || '').trim()) {
      errors.push('Scheme name is required.')
    }

    if (!segments.length) {
      errors.push('Add at least one segment.')
      return errors
    }

    const startAt = Number(editingScheme.seq?.start_at ?? 1)
    if (!Number.isFinite(startAt) || startAt < 1) {
      errors.push('Start at must be 1 or greater.')
    }

    let hasSequence = false
    segments.forEach((segment, index) => {
      const kind = getSegmentKind(segment)
      if (kind === 'literal') {
        if (!(segment.value || '').trim()) {
          errors.push(`Segment ${index + 1}: literal value is required.`)
        }
        return
      }

      if (kind === 'seq') {
        hasSequence = true
        const padding = Number(segment.padding ?? 6)
        const base = Number(segment.base ?? 10)
        if (!Number.isFinite(padding) || padding < 1) {
          errors.push(`Segment ${index + 1}: sequence padding must be 1 or greater.`)
        }
        if (base !== 10 && base !== 36) {
          errors.push(`Segment ${index + 1}: sequence base must be 10 or 36.`)
        }
        return
      }

      errors.push(`Segment ${index + 1}: only literal and sequence segments are supported here.`)
    })

    if (!hasSequence) {
      errors.push('Add at least one sequence segment.')
    }

    return errors
  }

  function buildSchemePayload() {
    const firstSeqSegment = segments.find((segment) => getSegmentKind(segment) === 'seq')
    const nextSeqPadding = Number(firstSeqSegment?.padding ?? editingScheme.seq?.padding ?? 6)
    const nextSeqBase = Number(firstSeqSegment?.base ?? editingScheme.seq?.base ?? 10)

    return {
      name: (editingScheme.name || '').trim(),
      is_active: !!editingScheme.is_active,
      separator: editingScheme.separator || '-',
      scope_mode: editingScheme.scope_mode || 'global',
      scope_keys: [...(editingScheme.scope_keys || [])],
      seq: {
        padding: nextSeqPadding,
        base: nextSeqBase,
        start_at: Number(editingScheme.seq?.start_at ?? 1),
        reset_policy: editingScheme.seq?.reset_policy || 'never',
      },
      revision: {
        policy: editingScheme.revision?.policy || 'alpha',
        start: editingScheme.revision?.start || 'A',
      },
      validation_rules: {
        max_length: Number(editingScheme.validation_rules?.max_length ?? 32),
        allowed_charset: editingScheme.validation_rules?.allowed_charset || 'A-Z0-9-',
        require_seq_segment: editingScheme.validation_rules?.require_seq_segment ?? true,
      },
      pattern_segments: segments.map((segment) => {
        const kind = getSegmentKind(segment)
        if (kind === 'literal') {
          return { kind, value: segment.value || '' }
        }
        if (kind === 'seq') {
          return {
            kind,
            padding: Number(segment.padding ?? nextSeqPadding),
            base: Number(segment.base ?? nextSeqBase),
          }
        }
        if (kind === 'field') {
          return {
            kind,
            field: segment.field || '',
            casing: segment.casing || 'upper',
            pad_left: segment.pad_left,
            pad_char: segment.pad_char || '',
          }
        }
        if (kind === 'date') {
          return { kind, fmt: segment.fmt || '' }
        }
        return { ...segment, kind }
      }),
    }
  }

  async function validateEditingScheme() {
    setError(null)
    setMessage(null)
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
      const sample = [example.part_number_example, example.revision_example ? `rev ${example.revision_example}` : '']
        .filter(Boolean)
        .join(' ')
      setMessage(sample ? `Valid. Example: ${sample}` : 'Valid.')
    } catch (err) {
      setError(formatApiError(err, 'Validation failed.'))
    }
  }

  async function saveEditingScheme() {
    setError(null)
    setMessage(null)

    if (hasLegacySegments) {
      setError(
        `This scheme uses legacy segment types: ${legacySegmentKinds.join(
          ', ',
        )}. It can still be used for allocation, but it cannot be saved from the simplified builder.`,
      )
      return
    }

    const localErrors = getLocalSchemeErrors(true)
    if (localErrors.length) {
      setError(localErrors.join(' '))
      return
    }

    const payload = buildSchemePayload()
    try {
      let nextSelectedSchemeId = selectedSchemeId
      if (selectedSchemeId) {
        await apiFetch(`/api/numbering/schemes/${selectedSchemeId}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        })
        setMessage('Scheme saved.')
      } else {
        const resp = await apiFetch<{ scheme: Scheme }>('/api/numbering/schemes', {
          method: 'POST',
          body: JSON.stringify(payload),
        })
        setMessage('Scheme created.')
        nextSelectedSchemeId = resp.scheme?.id || ''
      }
      await loadSchemes()
      if (nextSelectedSchemeId) {
        setSelectedSchemeId(nextSelectedSchemeId)
      }
    } catch (err) {
      setError(formatApiError(err, 'Failed to save scheme.'))
    }
  }

  async function deleteEditingScheme() {
    setError(null)
    setMessage(null)
    if (!selectedSchemeId) {
      setError('Select a scheme first.')
      return
    }

    if (!window.confirm('Delete this numbering scheme? This cannot be undone.')) {
      return
    }

    try {
      await apiFetch(`/api/numbering/schemes/${selectedSchemeId}`, { method: 'DELETE' })
      setMessage('Scheme deleted.')
      setSelectedSchemeId('')
      await loadSchemes()
    } catch (err) {
      setError(formatApiError(err, 'Failed to delete scheme.'))
    }
  }

  function setDraftKind(kind: 'literal' | 'seq') {
    setSegmentDraft((prev) => {
      if (kind === 'seq') {
        return {
          kind: 'seq',
          padding: Number(prev.padding ?? editingScheme.seq?.padding ?? 6),
          base: Number(prev.base ?? editingScheme.seq?.base ?? 10),
        }
      }
      return {
        kind: 'literal',
        value: prev.value || '',
      }
    })
  }

  function addSegment(kindOverride?: 'literal' | 'seq') {
    if (hasLegacySegments) return
    const kind = kindOverride || (getSegmentKind(segmentDraft) === 'seq' ? 'seq' : 'literal')
    if (kind === 'literal' && !(segmentDraft.value || '').trim()) {
      setError('Enter a literal value before adding a literal segment.')
      return
    }

    setError(null)
    const nextSegment =
      kind === 'seq'
        ? {
            kind: 'seq',
            padding: Number(segmentDraft.padding ?? editingScheme.seq?.padding ?? 6),
            base: Number(segmentDraft.base ?? editingScheme.seq?.base ?? 10),
          }
        : {
            kind: 'literal',
            value: segmentDraft.value || '',
          }

    const nextSegments = [...segments, nextSegment]
    setSegments(nextSegments)
    setSelectedSegmentIndex(nextSegments.length - 1)
    setSegmentDraft(cloneSegment(nextSegment))
  }

  function updateSegment() {
    if (hasLegacySegments || selectedSegmentIndex < 0) return
    const kind = getSegmentKind(segmentDraft) === 'seq' ? 'seq' : 'literal'
    if (kind === 'literal' && !(segmentDraft.value || '').trim()) {
      setError('Literal value is required.')
      return
    }

    setError(null)
    const nextSegment =
      kind === 'seq'
        ? {
            kind: 'seq',
            padding: Number(segmentDraft.padding ?? editingScheme.seq?.padding ?? 6),
            base: Number(segmentDraft.base ?? editingScheme.seq?.base ?? 10),
          }
        : {
            kind: 'literal',
            value: segmentDraft.value || '',
          }

    setSegments((prev) => prev.map((segment, index) => (index === selectedSegmentIndex ? nextSegment : segment)))
    setSegmentDraft(cloneSegment(nextSegment))
  }

  function removeSegment() {
    if (hasLegacySegments || selectedSegmentIndex < 0) return
    setSegments((prev) => prev.filter((_, index) => index !== selectedSegmentIndex))
    setSelectedSegmentIndex(-1)
    setSegmentDraft(createEmptySegment())
  }

  function moveSegment(delta: number) {
    if (hasLegacySegments || selectedSegmentIndex < 0) return
    const target = selectedSegmentIndex + delta
    if (target < 0 || target >= segments.length) return
    const next = [...segments]
    const [item] = next.splice(selectedSegmentIndex, 1)
    next.splice(target, 0, item)
    setSegments(next)
    setSelectedSegmentIndex(target)
  }

  function selectSegment(index: number) {
    setSelectedSegmentIndex(index)
    const selectedSegment = segments[index]
    if (selectedSegment && SIMPLE_SEGMENT_KINDS.has(getSegmentKind(selectedSegment))) {
      setSegmentDraft(cloneSegment(selectedSegment))
    }
  }

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
                      <td>{token.created_at || '-'}</td>
                      <td>{token.last_used_at || '-'}</td>
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
        <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
          <h5 className="mb-0">Numbering schemes</h5>
          <button
            className="btn btn-sm btn-primary"
            onClick={() => void saveEnabledChanges()}
            disabled={savingEnabledChanges}
          >
            Save enabled changes
          </button>
        </div>
        {changedEnabledCount > 0 && <div className="text-muted small mb-2">{changedEnabledCount} pending change(s).</div>}
        <div className="table-responsive">
          <table className="table table-sm">
            <thead>
              <tr>
                <th>Name</th>
                <th>Enabled</th>
                <th>Edit</th>
              </tr>
            </thead>
            <tbody>
              {schemes.map((scheme) => (
                <tr key={scheme.id}>
                  <td>{scheme.name}</td>
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
                  <td>
                    <button
                      className="btn btn-sm btn-outline-primary"
                      onClick={() => setSelectedSchemeId(scheme.id || '')}
                      disabled={!scheme.id}
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
              {!schemes.length && (
                <tr>
                  <td colSpan={3} className="text-muted text-center">
                    No schemes.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card p-3 mt-4">
        <h5>Scheme builder</h5>
        <div className="mb-3">
          <label className="form-label">Select scheme</label>
          <select className="form-select" value={selectedSchemeId} onChange={(e) => setSelectedSchemeId(e.target.value)}>
            <option value="">New scheme</option>
            {schemes.map((scheme) => (
              <option key={scheme.id} value={scheme.id}>
                {scheme.name}
              </option>
            ))}
          </select>
        </div>

        <div className="row g-2 mb-3">
          <div className="col-md-4">
            <label className="form-label small">Name</label>
            <input
              className="form-control"
              value={editingScheme.name || ''}
              onChange={(e) => updateEditingScheme({ name: e.target.value })}
            />
          </div>
          <div className="col-md-3">
            <label className="form-label small">Separator</label>
            <input
              className="form-control"
              value={editingScheme.separator || '-'}
              onChange={(e) => updateEditingScheme({ separator: e.target.value })}
            />
          </div>
          <div className="col-md-2">
            <label className="form-label small">Start at</label>
            <input
              className="form-control"
              type="number"
              min={1}
              value={editingScheme.seq?.start_at ?? 1}
              onChange={(e) =>
                updateEditingScheme({
                  seq: {
                    ...editingScheme.seq,
                    start_at: Math.max(1, Number(e.target.value) || 1),
                  },
                })
              }
            />
          </div>
          <div className="col-md-3">
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
                Enabled
              </label>
            </div>
          </div>
        </div>

        {hasLegacySegments && (
          <div className="alert alert-warning small">
            This scheme uses legacy segment types: {legacySegmentKinds.join(', ')}. It can still be used for allocation,
            but it must be converted before saving in the simplified builder.
          </div>
        )}

        <div className="mb-3">
          <h6>Segments</h6>
          <div className="row g-3">
            <div className="col-md-6">
              <ul className="list-group">
                {segments.map((segment, index) => (
                  <li
                    key={`${segment.kind || 'segment'}-${index}`}
                    className={`list-group-item ${index === selectedSegmentIndex ? 'active' : ''}`}
                    onClick={() => selectSegment(index)}
                    style={{ cursor: 'pointer' }}
                  >
                    {segmentLabel(segment, index)}
                  </li>
                ))}
                {!segments.length && <li className="list-group-item text-muted">No segments yet.</li>}
              </ul>
              <div className="mt-2 d-flex gap-2 flex-wrap">
                <button className="btn btn-sm btn-outline-secondary" onClick={() => moveSegment(-1)} disabled={hasLegacySegments}>
                  Up
                </button>
                <button className="btn btn-sm btn-outline-secondary" onClick={() => moveSegment(1)} disabled={hasLegacySegments}>
                  Down
                </button>
                <button className="btn btn-sm btn-outline-danger" onClick={removeSegment} disabled={hasLegacySegments}>
                  Remove
                </button>
              </div>
            </div>

            <div className="col-md-6">
              {hasLegacySegments ? (
                <div className="alert alert-light border small mb-0">
                  Legacy segment definitions are read-only here. You can still enable or disable the scheme from the
                  table above.
                </div>
              ) : (
                <>
                  <label className="form-label small">Kind</label>
                  <select
                    className="form-select mb-2"
                    value={getSegmentKind(segmentDraft) === 'seq' ? 'seq' : 'literal'}
                    onChange={(e) => setDraftKind(e.target.value === 'seq' ? 'seq' : 'literal')}
                  >
                    <option value="literal">literal</option>
                    <option value="seq">seq</option>
                  </select>

                  {getSegmentKind(segmentDraft) === 'seq' ? (
                    <div className="row g-2">
                      <div className="col-md-6">
                        <label className="form-label small">Padding</label>
                        <input
                          className="form-control mb-2"
                          type="number"
                          min={1}
                          value={segmentDraft.padding ?? 6}
                          onChange={(e) =>
                            setSegmentDraft({
                              kind: 'seq',
                              padding: Number(e.target.value) || 6,
                              base: Number(segmentDraft.base ?? 10),
                            })
                          }
                        />
                      </div>
                      <div className="col-md-6">
                        <label className="form-label small">Base</label>
                        <select
                          className="form-select mb-2"
                          value={segmentDraft.base ?? 10}
                          onChange={(e) =>
                            setSegmentDraft({
                              kind: 'seq',
                              padding: Number(segmentDraft.padding ?? 6),
                              base: Number(e.target.value),
                            })
                          }
                        >
                          <option value={10}>10</option>
                          <option value={36}>36</option>
                        </select>
                      </div>
                    </div>
                  ) : (
                    <>
                      <label className="form-label small">Literal value</label>
                      <input
                        className="form-control mb-2"
                        value={segmentDraft.value || ''}
                        onChange={(e) => setSegmentDraft({ kind: 'literal', value: e.target.value })}
                      />
                    </>
                  )}

                  <div className="d-flex gap-2 flex-wrap">
                    <button
                      className="btn btn-sm btn-outline-primary"
                      onClick={() => {
                        setDraftKind('literal')
                        addSegment('literal')
                      }}
                    >
                      Add literal segment
                    </button>
                    <button
                      className="btn btn-sm btn-outline-primary"
                      onClick={() => {
                        setDraftKind('seq')
                        addSegment('seq')
                      }}
                    >
                      Add sequence segment
                    </button>
                    <button className="btn btn-sm btn-outline-secondary" onClick={updateSegment}>
                      Update selected
                    </button>
                    <button
                      className="btn btn-sm btn-outline-secondary"
                      onClick={() => {
                        setSelectedSegmentIndex(-1)
                        setSegmentDraft(createEmptySegment())
                      }}
                    >
                      Clear
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="d-flex gap-2 flex-wrap">
          <button className="btn btn-outline-secondary" onClick={() => void validateEditingScheme()}>
            Validate / preview
          </button>
          <button className="btn btn-primary" onClick={() => void saveEditingScheme()} disabled={hasLegacySegments}>
            Save scheme
          </button>
          <button className="btn btn-outline-danger" onClick={() => void deleteEditingScheme()} disabled={!selectedSchemeId}>
            Delete scheme
          </button>
        </div>
      </div>
    </div>
  )
}

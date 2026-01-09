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

const EMPTY_SCHEME: Scheme = {
  name: '',
  description: '',
  is_active: true,
  is_preset: false,
  is_recommended: false,
  visibility: 'advanced_only',
  separator: '-',
  scope_mode: 'global',
  scope_keys: [],
  seq: { padding: 6, base: 10, start_at: 1, reset_policy: 'never' },
  revision: { policy: 'alpha', start: 'A' },
  validation_rules: { max_length: 32, allowed_charset: 'A-Z0-9-', require_seq_segment: true },
  pattern_segments: [],
}

const EMPTY_SEGMENT: Segment = {
  kind: 'literal',
  value: '',
  field: 'type',
  casing: 'upper',
  pad_left: undefined,
  pad_char: '',
  padding: 6,
  base: 10,
  fmt: 'YYYY',
}

export default function AdminAddinPage() {
  const [users, setUsers] = useState<User[]>([])
  const [selectedUser, setSelectedUser] = useState<User | null>(null)
  const [tokens, setTokens] = useState<Token[]>([])
  const [schemes, setSchemes] = useState<Scheme[]>([])
  const [selectedSchemeId, setSelectedSchemeId] = useState('')
  const [editingScheme, setEditingScheme] = useState<Scheme>({ ...EMPTY_SCHEME })
  const [scopeKeysText, setScopeKeysText] = useState('')
  const [segments, setSegments] = useState<Segment[]>([])
  const [selectedSegmentIndex, setSelectedSegmentIndex] = useState(-1)
  const [segmentDraft, setSegmentDraft] = useState<Segment>({ ...EMPTY_SEGMENT })
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadUsers()
    loadSchemes()
  }, [])

  useEffect(() => {
    if (!selectedSchemeId) {
      setEditingScheme({ ...EMPTY_SCHEME })
      setScopeKeysText('')
      setSegments([])
      setSelectedSegmentIndex(-1)
      setSegmentDraft({ ...EMPTY_SEGMENT })
      return
    }
    const found = schemes.find((scheme) => scheme.id === selectedSchemeId)
    if (found) {
      setEditingScheme({ ...EMPTY_SCHEME, ...found })
      setScopeKeysText((found.scope_keys || []).join(', '))
      setSegments(found.pattern_segments || [])
      setSelectedSegmentIndex(-1)
      setSegmentDraft({ ...EMPTY_SEGMENT })
    }
  }, [selectedSchemeId, schemes])

  async function loadUsers() {
    setError(null)
    try {
      const resp = await apiFetch<{ users: User[] }>('/api/admin/users')
      setUsers(resp.users || [])
    } catch (err) {
      setError((err as ApiError).message || 'Failed to load users.')
    }
  }

  async function loadUserTokens(user: User) {
    setError(null)
    try {
      const resp = await apiFetch<{ tokens: Token[] }>(`/api/admin/users/${user.id}/tokens`)
      setSelectedUser(user)
      setTokens(resp.tokens || [])
    } catch (err) {
      setError((err as ApiError).message || 'Failed to load tokens.')
    }
  }

  async function revokeToken(userId: string, tokenId: string) {
    setError(null)
    setMessage(null)
    try {
      await apiFetch(`/api/admin/users/${userId}/tokens/${tokenId}`, { method: 'DELETE' })
      setMessage('Token revoked.')
      if (selectedUser) {
        loadUserTokens(selectedUser)
      }
    } catch (err) {
      setError((err as ApiError).message || 'Failed to revoke token.')
    }
  }

  async function loadSchemes() {
    setError(null)
    try {
      const resp = await apiFetch<{ schemes: Scheme[] }>('/api/numbering/schemes')
      setSchemes(resp.schemes || [])
    } catch (err) {
      setError((err as ApiError).message || 'Failed to load schemes.')
    }
  }

  async function updateScheme(scheme: Scheme) {
    setError(null)
    setMessage(null)
    try {
      await apiFetch(`/api/numbering/schemes/${scheme.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: scheme.name,
          is_preset: scheme.is_preset,
          is_recommended: scheme.is_recommended,
          visibility: scheme.visibility,
        }),
      })
      setMessage('Scheme updated.')
    } catch (err) {
      setError((err as ApiError).message || 'Failed to update scheme.')
    }
  }

  function updateEditingScheme(patch: Partial<Scheme>) {
    setEditingScheme((prev) => ({ ...prev, ...patch }))
  }

  function segmentLabel(seg: Segment, index: number) {
    if (!seg) return `Segment ${index + 1}`
    switch ((seg.kind || '').toLowerCase()) {
      case 'literal':
        return `Literal: ${seg.value || ''}`
      case 'field':
        return `Field: ${seg.field || ''}`
      case 'seq':
        return `Seq: ${seg.padding || ''}`
      case 'date':
        return `Date: ${seg.fmt || ''}`
      default:
        return seg.kind || `Segment ${index + 1}`
    }
  }

  function buildSchemePayload() {
    const scopeKeys = scopeKeysText
      .split(',')
      .map((key) => key.trim())
      .filter(Boolean)
    return {
      name: (editingScheme.name || '').trim(),
      description: (editingScheme.description || '').trim(),
      is_active: !!editingScheme.is_active,
      is_preset: !!editingScheme.is_preset,
      is_recommended: !!editingScheme.is_recommended,
      visibility: editingScheme.visibility || 'advanced_only',
      separator: editingScheme.separator || '-',
      scope_mode: editingScheme.scope_mode || 'global',
      scope_keys: scopeKeys,
      seq: {
        padding: Number(editingScheme.seq?.padding || 6),
        base: Number(editingScheme.seq?.base || 10),
        start_at: Number(editingScheme.seq?.start_at || 1),
        reset_policy: editingScheme.seq?.reset_policy || 'never',
      },
      revision: {
        policy: editingScheme.revision?.policy || 'alpha',
        start: editingScheme.revision?.start || 'A',
      },
      validation_rules: {
        max_length: Number(editingScheme.validation_rules?.max_length || 32),
        allowed_charset: editingScheme.validation_rules?.allowed_charset || 'A-Z0-9-',
        require_seq_segment: !!editingScheme.validation_rules?.require_seq_segment,
      },
      pattern_segments: segments.map((seg) => {
        const payload: Segment = { kind: seg.kind }
        if (seg.kind === 'literal') payload.value = seg.value || ''
        if (seg.kind === 'field') {
          payload.field = seg.field || ''
          if (seg.casing) payload.casing = seg.casing
          if (seg.pad_left) payload.pad_left = Number(seg.pad_left)
          if (seg.pad_char) payload.pad_char = seg.pad_char
        }
        if (seg.kind === 'seq') {
          if (seg.padding) payload.padding = Number(seg.padding)
          if (seg.base) payload.base = Number(seg.base)
        }
        if (seg.kind === 'date') payload.fmt = seg.fmt || ''
        return payload
      }),
    }
  }

  async function validateEditingScheme() {
    setError(null)
    setMessage(null)
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
      setError((err as ApiError).message || 'Validation failed.')
    }
  }

  async function saveEditingScheme() {
    setError(null)
    setMessage(null)
    try {
      const payload = buildSchemePayload()
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
        const newId = resp.scheme?.id || ''
        await loadSchemes()
        if (newId) setSelectedSchemeId(newId)
      }
      await loadSchemes()
    } catch (err) {
      setError((err as ApiError).message || 'Failed to save scheme.')
    }
  }

  async function deactivateEditingScheme() {
    setError(null)
    setMessage(null)
    if (!selectedSchemeId) {
      setError('Select a scheme first.')
      return
    }
    try {
      await apiFetch(`/api/numbering/schemes/${selectedSchemeId}`, { method: 'DELETE' })
      setMessage('Scheme deactivated.')
      setSelectedSchemeId('')
      await loadSchemes()
    } catch (err) {
      setError((err as ApiError).message || 'Failed to deactivate scheme.')
    }
  }

  function addSegment() {
    setSegments((prev) => [...prev, { ...segmentDraft }])
    setSegmentDraft({ ...EMPTY_SEGMENT })
    setSelectedSegmentIndex(-1)
  }

  function updateSegment() {
    if (selectedSegmentIndex < 0) return
    setSegments((prev) => prev.map((seg, idx) => (idx === selectedSegmentIndex ? { ...segmentDraft } : seg)))
  }

  function removeSegment() {
    if (selectedSegmentIndex < 0) return
    setSegments((prev) => prev.filter((_, idx) => idx !== selectedSegmentIndex))
    setSelectedSegmentIndex(-1)
    setSegmentDraft({ ...EMPTY_SEGMENT })
  }

  function moveSegment(delta: number) {
    if (selectedSegmentIndex < 0) return
    const target = selectedSegmentIndex + delta
    if (target < 0 || target >= segments.length) return
    const next = [...segments]
    const [item] = next.splice(selectedSegmentIndex, 1)
    next.splice(target, 0, item)
    setSegments(next)
    setSelectedSegmentIndex(target)
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
                    <button className="btn btn-sm btn-outline-secondary" onClick={() => loadUserTokens(user)}>
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
                            onClick={() => revokeToken(selectedUser.id, token.id)}
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
        <h5>Scheme presets</h5>
        <div className="table-responsive">
          <table className="table table-sm">
            <thead>
              <tr>
                <th>Name</th>
                <th>Preset</th>
                <th>Recommended</th>
                <th>Visibility</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {schemes.map((scheme, idx) => (
                <tr key={scheme.id}>
                  <td>{scheme.name}</td>
                  <td>
                    <input
                      type="checkbox"
                      checked={!!scheme.is_preset}
                      onChange={(e) => {
                        const next = [...schemes]
                        next[idx] = { ...scheme, is_preset: e.target.checked }
                        setSchemes(next)
                      }}
                    />
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      checked={!!scheme.is_recommended}
                      onChange={(e) => {
                        const next = [...schemes]
                        next[idx] = { ...scheme, is_recommended: e.target.checked }
                        setSchemes(next)
                      }}
                    />
                  </td>
                  <td>
                    <select
                      className="form-select form-select-sm"
                      value={scheme.visibility || 'advanced_only'}
                      onChange={(e) => {
                        const next = [...schemes]
                        next[idx] = { ...scheme, visibility: e.target.value }
                        setSchemes(next)
                      }}
                    >
                      <option value="quickstart">quickstart</option>
                      <option value="advanced_only">advanced_only</option>
                    </select>
                  </td>
                  <td>
                    <button className="btn btn-sm btn-outline-primary" onClick={() => updateScheme(scheme)}>
                      Save
                    </button>
                  </td>
                </tr>
              ))}
              {!schemes.length && (
                <tr>
                  <td colSpan={5} className="text-muted text-center">
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
          <div className="col-md-6">
            <label className="form-label small">Name</label>
            <input
              className="form-control"
              value={editingScheme.name || ''}
              onChange={(e) => updateEditingScheme({ name: e.target.value })}
            />
          </div>
          <div className="col-md-6">
            <label className="form-label small">Description</label>
            <input
              className="form-control"
              value={editingScheme.description || ''}
              onChange={(e) => updateEditingScheme({ description: e.target.value })}
            />
          </div>
          <div className="col-md-3">
            <label className="form-label small">Active</label>
            <div className="form-check">
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
          <div className="col-md-3">
            <label className="form-label small">Preset</label>
            <div className="form-check">
              <input
                className="form-check-input"
                type="checkbox"
                checked={!!editingScheme.is_preset}
                onChange={(e) => updateEditingScheme({ is_preset: e.target.checked })}
                id="schemePresetCheck"
              />
              <label className="form-check-label" htmlFor="schemePresetCheck">
                Preset
              </label>
            </div>
          </div>
          <div className="col-md-3">
            <label className="form-label small">Recommended</label>
            <div className="form-check">
              <input
                className="form-check-input"
                type="checkbox"
                checked={!!editingScheme.is_recommended}
                onChange={(e) => updateEditingScheme({ is_recommended: e.target.checked })}
                id="schemeRecommendedCheck"
              />
              <label className="form-check-label" htmlFor="schemeRecommendedCheck">
                Recommended
              </label>
            </div>
          </div>
          <div className="col-md-3">
            <label className="form-label small">Visibility</label>
            <select
              className="form-select"
              value={editingScheme.visibility || 'advanced_only'}
              onChange={(e) => updateEditingScheme({ visibility: e.target.value })}
            >
              <option value="quickstart">quickstart</option>
              <option value="advanced_only">advanced_only</option>
            </select>
          </div>
        </div>

        <div className="row g-2 mb-3">
          <div className="col-md-3">
            <label className="form-label small">Separator</label>
            <input
              className="form-control"
              value={editingScheme.separator || ''}
              onChange={(e) => updateEditingScheme({ separator: e.target.value })}
            />
          </div>
          <div className="col-md-4">
            <label className="form-label small">Scope mode</label>
            <select
              className="form-select"
              value={editingScheme.scope_mode || 'global'}
              onChange={(e) => updateEditingScheme({ scope_mode: e.target.value })}
            >
              <option value="global">global</option>
              <option value="by_type">by_type</option>
              <option value="by_family">by_family</option>
              <option value="by_project">by_project</option>
              <option value="custom_keys">custom_keys</option>
            </select>
          </div>
          <div className="col-md-5">
            <label className="form-label small">Scope keys (comma-separated)</label>
            <input className="form-control" value={scopeKeysText} onChange={(e) => setScopeKeysText(e.target.value)} />
          </div>
        </div>

        <div className="row g-2 mb-3">
          <div className="col-md-3">
            <label className="form-label small">Seq padding</label>
            <input
              className="form-control"
              type="number"
              value={editingScheme.seq?.padding ?? 6}
              onChange={(e) => updateEditingScheme({ seq: { ...editingScheme.seq, padding: Number(e.target.value) } })}
            />
          </div>
          <div className="col-md-3">
            <label className="form-label small">Seq base</label>
            <select
              className="form-select"
              value={editingScheme.seq?.base ?? 10}
              onChange={(e) => updateEditingScheme({ seq: { ...editingScheme.seq, base: Number(e.target.value) } })}
            >
              <option value={10}>10</option>
              <option value={36}>36</option>
            </select>
          </div>
          <div className="col-md-3">
            <label className="form-label small">Start at</label>
            <input
              className="form-control"
              type="number"
              value={editingScheme.seq?.start_at ?? 1}
              onChange={(e) => updateEditingScheme({ seq: { ...editingScheme.seq, start_at: Number(e.target.value) } })}
            />
          </div>
          <div className="col-md-3">
            <label className="form-label small">Reset policy</label>
            <select
              className="form-select"
              value={editingScheme.seq?.reset_policy ?? 'never'}
              onChange={(e) => updateEditingScheme({ seq: { ...editingScheme.seq, reset_policy: e.target.value } })}
            >
              <option value="never">never</option>
              <option value="yearly">yearly</option>
              <option value="monthly">monthly</option>
              <option value="by_project">by_project</option>
            </select>
          </div>
        </div>

        <div className="row g-2 mb-3">
          <div className="col-md-3">
            <label className="form-label small">Revision policy</label>
            <select
              className="form-select"
              value={editingScheme.revision?.policy ?? 'alpha'}
              onChange={(e) => updateEditingScheme({ revision: { ...editingScheme.revision, policy: e.target.value } })}
            >
              <option value="alpha">alpha</option>
              <option value="numeric">numeric</option>
              <option value="none">none</option>
            </select>
          </div>
          <div className="col-md-3">
            <label className="form-label small">Revision start</label>
            <input
              className="form-control"
              value={editingScheme.revision?.start ?? 'A'}
              onChange={(e) => updateEditingScheme({ revision: { ...editingScheme.revision, start: e.target.value } })}
            />
          </div>
          <div className="col-md-3">
            <label className="form-label small">Max length</label>
            <input
              className="form-control"
              type="number"
              value={editingScheme.validation_rules?.max_length ?? 32}
              onChange={(e) =>
                updateEditingScheme({
                  validation_rules: { ...editingScheme.validation_rules, max_length: Number(e.target.value) },
                })
              }
            />
          </div>
          <div className="col-md-3">
            <label className="form-label small">Allowed charset</label>
            <input
              className="form-control"
              value={editingScheme.validation_rules?.allowed_charset ?? 'A-Z0-9-'}
              onChange={(e) =>
                updateEditingScheme({
                  validation_rules: { ...editingScheme.validation_rules, allowed_charset: e.target.value },
                })
              }
            />
          </div>
          <div className="col-md-3">
            <label className="form-label small">Require seq</label>
            <div className="form-check">
              <input
                className="form-check-input"
                type="checkbox"
                checked={!!editingScheme.validation_rules?.require_seq_segment}
                onChange={(e) =>
                  updateEditingScheme({
                    validation_rules: { ...editingScheme.validation_rules, require_seq_segment: e.target.checked },
                  })
                }
                id="requireSeqCheck"
              />
              <label className="form-check-label" htmlFor="requireSeqCheck">
                Required
              </label>
            </div>
          </div>
        </div>

        <div className="mb-3">
          <h6>Segments</h6>
          <div className="row g-2">
            <div className="col-md-6">
              <ul className="list-group">
                {segments.map((seg, idx) => (
                  <li
                    key={`${seg.kind}-${idx}`}
                    className={`list-group-item ${idx === selectedSegmentIndex ? 'active' : ''}`}
                    onClick={() => {
                      setSelectedSegmentIndex(idx)
                      setSegmentDraft({ ...seg })
                    }}
                    style={{ cursor: 'pointer' }}
                  >
                    {segmentLabel(seg, idx)}
                  </li>
                ))}
                {!segments.length && <li className="list-group-item text-muted">No segments yet.</li>}
              </ul>
              <div className="mt-2 d-flex gap-2 flex-wrap">
                <button className="btn btn-sm btn-outline-secondary" onClick={() => moveSegment(-1)}>
                  Up
                </button>
                <button className="btn btn-sm btn-outline-secondary" onClick={() => moveSegment(1)}>
                  Down
                </button>
                <button className="btn btn-sm btn-outline-danger" onClick={removeSegment}>
                  Remove
                </button>
              </div>
            </div>
            <div className="col-md-6">
              <label className="form-label small">Kind</label>
              <select
                className="form-select mb-2"
                value={segmentDraft.kind || 'literal'}
                onChange={(e) => setSegmentDraft({ ...segmentDraft, kind: e.target.value })}
              >
                <option value="literal">literal</option>
                <option value="field">field</option>
                <option value="seq">seq</option>
                <option value="date">date</option>
              </select>
              <label className="form-label small">Literal value</label>
              <input
                className="form-control mb-2"
                value={segmentDraft.value || ''}
                onChange={(e) => setSegmentDraft({ ...segmentDraft, value: e.target.value })}
                disabled={segmentDraft.kind !== 'literal'}
              />
              <label className="form-label small">Field</label>
              <input
                className="form-control mb-2"
                value={segmentDraft.field || ''}
                onChange={(e) => setSegmentDraft({ ...segmentDraft, field: e.target.value })}
                disabled={segmentDraft.kind !== 'field'}
              />
              <label className="form-label small">Casing</label>
              <select
                className="form-select mb-2"
                value={segmentDraft.casing || 'upper'}
                onChange={(e) => setSegmentDraft({ ...segmentDraft, casing: e.target.value })}
                disabled={segmentDraft.kind !== 'field'}
              >
                <option value="upper">upper</option>
                <option value="lower">lower</option>
                <option value="none">none</option>
              </select>
              <div className="row g-2">
                <div className="col-md-6">
                  <label className="form-label small">Pad left</label>
                  <input
                    className="form-control mb-2"
                    type="number"
                    value={segmentDraft.pad_left ?? ''}
                    onChange={(e) => setSegmentDraft({ ...segmentDraft, pad_left: Number(e.target.value) || undefined })}
                    disabled={segmentDraft.kind !== 'field'}
                  />
                </div>
                <div className="col-md-6">
                  <label className="form-label small">Pad char</label>
                  <input
                    className="form-control mb-2"
                    value={segmentDraft.pad_char || ''}
                    onChange={(e) => setSegmentDraft({ ...segmentDraft, pad_char: e.target.value })}
                    disabled={segmentDraft.kind !== 'field'}
                  />
                </div>
              </div>
              <div className="row g-2">
                <div className="col-md-6">
                  <label className="form-label small">Seq padding</label>
                  <input
                    className="form-control mb-2"
                    type="number"
                    value={segmentDraft.padding ?? 6}
                    onChange={(e) => setSegmentDraft({ ...segmentDraft, padding: Number(e.target.value) })}
                    disabled={segmentDraft.kind !== 'seq'}
                  />
                </div>
                <div className="col-md-6">
                  <label className="form-label small">Seq base</label>
                  <select
                    className="form-select mb-2"
                    value={segmentDraft.base ?? 10}
                    onChange={(e) => setSegmentDraft({ ...segmentDraft, base: Number(e.target.value) })}
                    disabled={segmentDraft.kind !== 'seq'}
                  >
                    <option value={10}>10</option>
                    <option value={36}>36</option>
                  </select>
                </div>
              </div>
              <label className="form-label small">Date format</label>
              <select
                className="form-select mb-2"
                value={segmentDraft.fmt || 'YYYY'}
                onChange={(e) => setSegmentDraft({ ...segmentDraft, fmt: e.target.value })}
                disabled={segmentDraft.kind !== 'date'}
              >
                <option value="YYYY">YYYY</option>
                <option value="YY">YY</option>
                <option value="MM">MM</option>
                <option value="YYYYMM">YYYYMM</option>
              </select>

              <div className="d-flex gap-2 flex-wrap">
                <button className="btn btn-sm btn-outline-primary" onClick={addSegment}>
                  Add segment
                </button>
                <button className="btn btn-sm btn-outline-secondary" onClick={updateSegment}>
                  Update
                </button>
                <button className="btn btn-sm btn-outline-secondary" onClick={() => setSegmentDraft({ ...EMPTY_SEGMENT })}>
                  Clear
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="d-flex gap-2 flex-wrap">
          <button className="btn btn-outline-secondary" onClick={validateEditingScheme}>
            Validate
          </button>
          <button className="btn btn-primary" onClick={saveEditingScheme}>
            Save scheme
          </button>
          <button className="btn btn-outline-danger" onClick={deactivateEditingScheme}>
            Deactivate
          </button>
        </div>
      </div>
    </div>
  )
}

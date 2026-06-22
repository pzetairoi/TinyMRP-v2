import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../lib/api'
import type { ApiError } from '../lib/api'
import {
  loadFieldCandidates,
  loadFieldConfig,
  type CanonicalAliasEntry,
  type FieldCandidate,
  type FieldConfigPayload,
  type FieldContext,
  type FieldDefinition,
} from '../lib/fieldConfig'

const ARENA_FIXED_FIELD_IDS = new Set(['thumbnail', 'part_number', 'description', 'qty', 'level'])

function slugFieldId(value: string) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

function normalizeSourcePath(value: string) {
  const parts = String(value || '')
    .split('.')
    .map((part) => String(part || '').trim())
    .filter(Boolean)
  if (parts.length < 2) return ''
  const [head, ...tail] = parts
  if (!['attrs', 'part'].includes(head.toLowerCase())) return ''
  const normalizedTail = tail.map((part) => slugFieldId(part)).filter(Boolean)
  if (!normalizedTail.length) return ''
  return [head.toLowerCase(), ...normalizedTail].join('.')
}

function cloneContexts(contexts: Record<string, FieldContext>) {
  return Object.fromEntries(
    Object.entries(contexts || {}).map(([key, value]) => [
      key,
      {
        ...value,
        required_field_ids: [...(value.required_field_ids || [])],
        allowed_field_ids: [...(value.allowed_field_ids || [])],
        default_field_ids: [...(value.default_field_ids || [])],
        available_fields: [...(value.available_fields || [])],
      },
    ]),
  ) as Record<string, FieldContext>
}

function cloneCanonicalAliases(entries: CanonicalAliasEntry[] | undefined) {
  return (entries || []).map((entry) => ({
    ...entry,
    aliases: [...(entry.aliases || [])],
  }))
}

export default function AdminFieldsPage() {
  const [config, setConfig] = useState<FieldConfigPayload | null>(null)
  const [fieldCandidates, setFieldCandidates] = useState<FieldCandidate[]>([])
  const [selectedCandidateId, setSelectedCandidateId] = useState('')
  const [candidateError, setCandidateError] = useState<string | null>(null)
  const [canAdmin, setCanAdmin] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    ;(async () => {
      try {
        const resp = await loadFieldConfig()
        setConfig({
          fields: [...(resp.config.fields || [])],
          contexts: cloneContexts(resp.config.contexts || {}),
          canonical_aliases: cloneCanonicalAliases(resp.config.canonical_aliases),
        })
        setCanAdmin(!!resp.permissions?.can_admin)
        if (resp.permissions?.can_admin) {
          try {
            const candidatesResp = await loadFieldCandidates()
            setFieldCandidates(candidatesResp.candidates || [])
          } catch (candidateErr) {
            setCandidateError((candidateErr as ApiError).message || 'Failed to load detected part fields.')
          }
        }
      } catch (err) {
        setError((err as ApiError).message || 'Failed to load field configuration.')
      }
    })()
  }, [])

  const fields = config?.fields || []
  const builtinFields = useMemo(() => fields.filter((field) => field.kind !== 'custom'), [fields])
  const customFields = useMemo(() => fields.filter((field) => field.kind === 'custom'), [fields])
  const canonicalAliases = config?.canonical_aliases || []
  const availableFieldCandidates = useMemo(() => {
    const configuredIds = new Set(fields.map((field) => slugFieldId(field.id)))
    const configuredSources = new Set(fields.map((field) => normalizeSourcePath(field.source_path || '')).filter(Boolean))
    return fieldCandidates.filter((candidate) => {
      const candidateId = slugFieldId(candidate.id)
      const candidateSource = normalizeSourcePath(candidate.source_path || '')
      if (!candidateId || !candidateSource) return false
      return !configuredIds.has(candidateId) && !configuredSources.has(candidateSource)
    })
  }, [fieldCandidates, fields])
  const selectedCandidate = useMemo(
    () => availableFieldCandidates.find((candidate) => candidate.id === selectedCandidateId) || null,
    [availableFieldCandidates, selectedCandidateId],
  )

  function updateField(fieldId: string, patch: Partial<FieldDefinition>) {
    setConfig((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        fields: prev.fields.map((field) => (field.id === fieldId ? { ...field, ...patch } : field)),
      }
    })
  }

  function addCustomField() {
    const nextId = `custom_${customFields.length + 1}`
    setConfig((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        fields: [
          ...prev.fields,
          {
            id: nextId,
            label: `Custom ${customFields.length + 1}`,
            arena_header: `Custom ${customFields.length + 1}`,
            kind: 'custom',
            data_type: 'text',
            source_path: `attrs.${nextId}`,
            sortable: true,
            filterable: true,
          },
        ],
      }
    })
  }

  function updateCanonicalAliases(fieldId: string, value: string) {
    setConfig((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        canonical_aliases: (prev.canonical_aliases || []).map((entry) =>
          entry.field_id === fieldId
            ? {
                ...entry,
                aliases: value
                  .split(/[,\n;]/)
                  .map((item) => item.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, ''))
                  .filter((item, idx, arr) => item && arr.indexOf(item) === idx),
              }
            : entry,
        ),
      }
    })
  }

  function addCandidateField() {
    if (!selectedCandidate || !config) return
    setConfig((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        fields: [
          ...prev.fields,
          {
            id: slugFieldId(selectedCandidate.id),
            label: selectedCandidate.label,
            arena_header: selectedCandidate.label,
            kind: 'custom',
            data_type: selectedCandidate.data_type || 'text',
            source_path: selectedCandidate.source_path,
            sortable: true,
            filterable: true,
          },
        ],
      }
    })
    setSelectedCandidateId('')
    setError(null)
    setMessage(`Detected field "${selectedCandidate.label}" added.`)
  }

  function renameCustomField(fieldId: string, nextFieldId: string) {
    const cleaned = slugFieldId(nextFieldId)
    if (!cleaned || cleaned === fieldId) return
    setConfig((prev) => {
      if (!prev) return prev
      const contexts = cloneContexts(prev.contexts)
      for (const ctx of Object.values(contexts)) {
        ctx.allowed_field_ids = ctx.allowed_field_ids.map((id) => (id === fieldId ? cleaned : id))
        ctx.default_field_ids = ctx.default_field_ids.map((id) => (id === fieldId ? cleaned : id))
      }
      return {
        ...prev,
        fields: prev.fields.map((field) => {
          if (field.id !== fieldId) return field
          const currentSource = String(field.source_path || '').trim()
          const nextSource =
            !currentSource || currentSource === `attrs.${fieldId}` || currentSource === 'attrs.new_field'
              ? `attrs.${cleaned}`
              : currentSource
          return { ...field, id: cleaned, source_path: nextSource }
        }),
        contexts,
      }
    })
  }

  function removeCustomField(fieldId: string) {
    setConfig((prev) => {
      if (!prev) return prev
      const contexts = cloneContexts(prev.contexts)
      for (const ctx of Object.values(contexts)) {
        ctx.allowed_field_ids = ctx.allowed_field_ids.filter((id) => id !== fieldId)
        ctx.default_field_ids = ctx.default_field_ids.filter((id) => id !== fieldId)
      }
      return {
        ...prev,
        fields: prev.fields.filter((field) => field.id !== fieldId),
        contexts,
      }
    })
  }

  function toggleAllowed(contextName: string, fieldId: string, checked: boolean) {
    setConfig((prev) => {
      if (!prev) return prev
      const contexts = cloneContexts(prev.contexts)
      const ctx = contexts[contextName]
      if (!ctx) return prev
      const nextAllowed = checked
        ? [...ctx.allowed_field_ids, fieldId].filter((id, idx, arr) => arr.indexOf(id) === idx)
        : ctx.allowed_field_ids.filter((id) => id !== fieldId)
      const required = new Set(ctx.required_field_ids || [])
      if (required.has(fieldId) && !checked) return prev
      ctx.allowed_field_ids = nextAllowed
      ctx.default_field_ids = ctx.default_field_ids.filter((id) => nextAllowed.includes(id))
      return { ...prev, contexts }
    })
  }

  function toggleDefault(contextName: string, fieldId: string, checked: boolean) {
    setConfig((prev) => {
      if (!prev) return prev
      const contexts = cloneContexts(prev.contexts)
      const ctx = contexts[contextName]
      if (!ctx) return prev
      const required = new Set(ctx.required_field_ids || [])
      if (required.has(fieldId) && !checked) return prev
      if (!ctx.allowed_field_ids.includes(fieldId)) return prev
      ctx.default_field_ids = checked
        ? [...ctx.default_field_ids, fieldId].filter((id, idx, arr) => arr.indexOf(id) === idx)
        : ctx.default_field_ids.filter((id) => id !== fieldId)
      return { ...prev, contexts }
    })
  }

  async function saveConfig() {
    if (!config) return
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const payload = {
        builtin_fields: config.fields
          .filter((field) => field.kind !== 'custom')
          .map((field) => ({
            id: field.id,
            label: field.label,
            arena_header: field.arena_header || field.label,
            source_path: field.source_path || '',
          })),
        custom_fields: config.fields
          .filter((field) => field.kind === 'custom')
          .map((field) => ({
            id: slugFieldId(field.id),
            label: field.label,
            arena_header: field.arena_header || field.label,
            source_path: (field.source_path || '').trim() || `attrs.${slugFieldId(field.id)}`,
            data_type: field.data_type || 'text',
            sortable: field.sortable !== false,
            filterable: field.filterable !== false,
          })),
        contexts: Object.fromEntries(
          Object.entries(config.contexts || {}).map(([key, value]) => [
            key,
            {
              allowed_field_ids: value.allowed_field_ids,
              default_field_ids: value.default_field_ids,
            },
          ]),
        ),
        canonical_aliases: (config.canonical_aliases || []).map((entry) => ({
          field_id: entry.field_id,
          aliases: entry.aliases || [],
        })),
      }
      const resp = await apiFetch<{ config: FieldConfigPayload }>('/api/admin/field-config', {
        method: 'PUT',
        body: JSON.stringify(payload),
      })
      setConfig({
        fields: [...(resp.config.fields || [])],
        contexts: cloneContexts(resp.config.contexts || {}),
        canonical_aliases: cloneCanonicalAliases(resp.config.canonical_aliases),
      })
      setMessage('Field configuration saved.')
    } catch (err) {
      setError((err as ApiError).message || 'Failed to save field configuration.')
    } finally {
      setSaving(false)
    }
  }

  async function resetConfig() {
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const resp = await apiFetch<{ config: FieldConfigPayload }>('/api/admin/field-config/reset', {
        method: 'POST',
      })
      setConfig({
        fields: [...(resp.config.fields || [])],
        contexts: cloneContexts(resp.config.contexts || {}),
        canonical_aliases: cloneCanonicalAliases(resp.config.canonical_aliases),
      })
      setMessage('Defaults restored.')
    } catch (err) {
      setError((err as ApiError).message || 'Failed to restore defaults.')
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    if (selectedCandidateId && !availableFieldCandidates.some((candidate) => candidate.id === selectedCandidateId)) {
      setSelectedCandidateId('')
    }
  }, [availableFieldCandidates, selectedCandidateId])

  async function rebuildCanonicalFields() {
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const resp = await apiFetch<{ config: FieldConfigPayload; report: { scanned: number; updated: number } }>(
        '/api/admin/field-config/rebuild-canonical-fields',
        { method: 'POST' },
      )
      setConfig({
        fields: [...(resp.config.fields || [])],
        contexts: cloneContexts(resp.config.contexts || {}),
        canonical_aliases: cloneCanonicalAliases(resp.config.canonical_aliases),
      })
      setMessage(`Canonical fields rebuilt for ${resp.report.updated} of ${resp.report.scanned} parts.`)
    } catch (err) {
      setError((err as ApiError).message || 'Failed to rebuild canonical fields.')
    } finally {
      setSaving(false)
    }
  }

  async function rebuildSearchFields() {
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const resp = await apiFetch<{ config: FieldConfigPayload; report: { scanned: number; updated: number; errors: number } }>(
        '/api/admin/field-config/rebuild-search-fields',
        { method: 'POST' },
      )
      setConfig({
        fields: [...(resp.config.fields || [])],
        contexts: cloneContexts(resp.config.contexts || {}),
        canonical_aliases: cloneCanonicalAliases(resp.config.canonical_aliases),
      })
      setMessage(
        `Searchable part fields rebuilt for ${resp.report.updated} of ${resp.report.scanned} parts.` +
          (resp.report.errors ? ` Errors: ${resp.report.errors}.` : ''),
      )
    } catch (err) {
      setError((err as ApiError).message || 'Failed to rebuild searchable part fields.')
    } finally {
      setSaving(false)
    }
  }

  if (error && !config) {
    return <div className="text-danger">{error}</div>
  }

  if (!config) {
    return <div className="text-muted">Loading field configuration...</div>
  }

  if (!canAdmin) {
    return <div className="text-danger">Admin access is required.</div>
  }

  return (
    <div className="p-3">
      <div className="d-flex align-items-center justify-content-between mb-3">
        <div>
          <h4 className="mb-0">Field Configuration</h4>
          <div className="text-muted small">
            Define the source field mapping once, keep defaults available, and control which fields users can expose in tables, Excel BOM exports, and Arena BOM exports.
          </div>
        </div>
        <div className="d-flex gap-2">
          <button className="btn btn-outline-secondary" onClick={resetConfig} disabled={saving}>
            Restore defaults
          </button>
          <button className="btn btn-primary" onClick={saveConfig} disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-danger">{error}</div>}

      <div className="card p-3 mb-4">
        <div className="d-flex align-items-center justify-content-between mb-3">
          <h5 className="mb-0">Built-in Fields</h5>
          <div className="text-muted small">These are the core fields used across part views and exports.</div>
        </div>
        <div className="table-responsive">
          <table className="table table-sm align-middle">
            <thead>
              <tr>
                <th style={{ width: 180 }}>Field ID</th>
                <th>Label</th>
                <th>Arena header</th>
                <th>Source path</th>
              </tr>
            </thead>
            <tbody>
              {builtinFields.map((field) => (
                <tr key={field.id}>
                  <td className="font-monospace small">{field.id}</td>
                  <td>
                    <input
                      className="form-control form-control-sm"
                      value={field.label || ''}
                      onChange={(e) => updateField(field.id, { label: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="form-control form-control-sm"
                      value={field.arena_header || ''}
                      onChange={(e) => updateField(field.id, { arena_header: e.target.value })}
                      placeholder={field.label || field.id}
                    />
                  </td>
                  <td>
                    <input
                      className="form-control form-control-sm font-monospace"
                      value={field.source_path || ''}
                      disabled={!!field.source_locked || field.kind === 'special'}
                      onChange={(e) => updateField(field.id, { source_path: e.target.value })}
                      placeholder={field.kind === 'special' ? 'Computed field' : 'attrs.some_field'}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card p-3 mb-4">
        <div className="d-flex align-items-center justify-content-between mb-3">
          <div>
            <h5 className="mb-0">Searchable Part Fields</h5>
            <div className="text-muted small">
              Use this after changing field mappings or after upgrading from older data so custom fields and file availability filters work correctly.
            </div>
          </div>
          <button className="btn btn-outline-primary" onClick={rebuildSearchFields} disabled={saving}>
            {saving ? 'Working...' : 'Rebuild searchable part fields'}
          </button>
        </div>
        <div className="small text-muted">
          This rebuild updates canonical mirrors where needed, materialized custom/remapped field values, and file availability coverage on existing parts.
        </div>
      </div>

      <div className="card p-3 mb-4">
        <div className="d-flex align-items-center justify-content-between mb-3">
          <div>
            <h5 className="mb-0">Canonical Import Aliases</h5>
            <div className="text-muted small">
              Map raw imported attribute names to the app canonical fields. Use this for files where fields such as `comments` really mean `process`.
            </div>
          </div>
          <button className="btn btn-outline-primary" onClick={rebuildCanonicalFields} disabled={saving}>
            {saving ? 'Working...' : 'Rebuild canonical fields'}
          </button>
        </div>
        <div className="table-responsive">
          <table className="table table-sm align-middle">
            <thead>
              <tr>
                <th style={{ width: 180 }}>Canonical field</th>
                <th>Aliases</th>
                <th style={{ width: 120 }}>Mode</th>
              </tr>
            </thead>
            <tbody>
              {canonicalAliases.map((entry) => (
                <tr key={entry.field_id}>
                  <td>
                    <div className="fw-semibold">{entry.label}</div>
                    <div className="small text-muted font-monospace">{entry.field_id}</div>
                  </td>
                  <td>
                    <textarea
                      className="form-control form-control-sm font-monospace"
                      rows={2}
                      value={(entry.aliases || []).join(', ')}
                      onChange={(e) => updateCanonicalAliases(entry.field_id, e.target.value)}
                      placeholder="process, comments, secondprocess"
                    />
                  </td>
                  <td className="small text-muted">{entry.multi_value ? 'Multi-value' : 'Single value'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card p-3 mb-4">
        <div className="d-flex align-items-center justify-content-between mb-3">
          <h5 className="mb-0">Custom Fields</h5>
          <div className="d-flex flex-wrap gap-2">
            <button className="btn btn-sm btn-outline-primary" onClick={addCustomField}>
              Add manual field
            </button>
          </div>
        </div>
        <div className="row g-2 align-items-center mb-3">
          <div className="col-lg-6">
            <select
              className="form-select form-select-sm"
              value={selectedCandidateId}
              onChange={(e) => setSelectedCandidateId(e.target.value)}
            >
              <option value="">Add from detected part field...</option>
              {availableFieldCandidates.map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {candidate.label} [{candidate.source_path}]
                </option>
              ))}
            </select>
          </div>
          <div className="col-auto">
            <button className="btn btn-sm btn-primary" onClick={addCandidateField} disabled={!selectedCandidate}>
              Add detected field
            </button>
          </div>
        </div>
        <div className="small text-muted mb-3">
          Detected fields are collected from non-empty part attributes and normalized with the same rules used by filters and exports.
        </div>
        {selectedCandidate && (
          <div className="small text-muted mb-3">
            Type: <span className="font-monospace">{selectedCandidate.data_type || 'text'}</span> · Source:{' '}
            <span className="font-monospace">{selectedCandidate.source_path}</span> · Seen on {selectedCandidate.part_count} part
            {selectedCandidate.part_count === 1 ? '' : 's'}
            {selectedCandidate.sample_value ? ` · Sample: ${selectedCandidate.sample_value}` : ''}
            {selectedCandidate.raw_keys?.length ? ` · Seen as: ${selectedCandidate.raw_keys.join(', ')}` : ''}
          </div>
        )}
        {candidateError && <div className="alert alert-warning py-2">{candidateError}</div>}
        <div className="table-responsive">
          <table className="table table-sm align-middle">
            <thead>
              <tr>
                <th style={{ width: 160 }}>Field ID</th>
                <th>Label</th>
                <th>Arena header</th>
                <th>Source path</th>
                <th style={{ width: 140 }}>Type</th>
                <th style={{ width: 100 }}>Sortable</th>
                <th style={{ width: 100 }}>Filterable</th>
                <th style={{ width: 80 }} />
              </tr>
            </thead>
            <tbody>
              {customFields.map((field) => (
                <tr key={field.id}>
                  <td>
                    <input
                      className="form-control form-control-sm font-monospace"
                      value={field.id}
                      onChange={(e) => renameCustomField(field.id, e.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      className="form-control form-control-sm"
                      value={field.label || ''}
                      onChange={(e) => updateField(field.id, { label: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="form-control form-control-sm"
                      value={field.arena_header || ''}
                      onChange={(e) => updateField(field.id, { arena_header: e.target.value })}
                      placeholder={field.label || field.id}
                    />
                  </td>
                  <td>
                    <input
                      className="form-control form-control-sm font-monospace"
                      value={field.source_path || ''}
                      onChange={(e) => updateField(field.id, { source_path: e.target.value })}
                    />
                  </td>
                  <td>
                    <select
                      className="form-select form-select-sm"
                      value={field.data_type || 'text'}
                      onChange={(e) => updateField(field.id, { data_type: e.target.value })}
                    >
                      <option value="text">text</option>
                      <option value="number">number</option>
                      <option value="boolean">boolean</option>
                      <option value="link">link</option>
                    </select>
                  </td>
                  <td>
                    <div className="form-check">
                      <input
                        className="form-check-input"
                        type="checkbox"
                        checked={field.sortable !== false}
                        onChange={(e) => updateField(field.id, { sortable: e.target.checked })}
                      />
                    </div>
                  </td>
                  <td>
                    <div className="form-check">
                      <input
                        className="form-check-input"
                        type="checkbox"
                        checked={field.filterable !== false}
                        onChange={(e) => updateField(field.id, { filterable: e.target.checked })}
                      />
                    </div>
                  </td>
                  <td className="text-end">
                    <button className="btn btn-sm btn-outline-danger" onClick={() => removeCustomField(field.id)}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
              {!customFields.length && (
                <tr>
                  <td colSpan={8} className="text-muted small">
                    No custom fields yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card p-3">
        <h5 className="mb-3">View Defaults</h5>
        <div className="text-muted small mb-3">
          `Allowed` controls which fields users can add in each view. `Default` controls the preset users get when they reset to the admin baseline.
        </div>
        <div className="row g-3">
          {Object.entries(config.contexts || {}).map(([contextName, ctx]) => {
            const required = new Set(ctx.required_field_ids || [])
            const selectableFields = contextName === 'arena_bom'
              ? fields.filter((field) => !ARENA_FIXED_FIELD_IDS.has(field.id))
              : fields
            return (
              <div key={contextName} className="col-12">
                <div className="border rounded p-3">
                  <div className="fw-semibold mb-2">{ctx.label}</div>
                  {contextName === 'arena_bom' ? (
                    <div className="small text-muted mb-2">
                      Fixed Arena columns such as item number, item name, level, and quantity are always included separately.
                    </div>
                  ) : null}
                  <div className="row g-3">
                    <div className="col-lg-6">
                      <div className="small text-muted mb-2">Allowed fields</div>
                      <div className="row g-2">
                        {selectableFields.map((field) => (
                          <div key={`${contextName}-allow-${field.id}`} className="col-md-6">
                            <div className="form-check">
                              <input
                                className="form-check-input"
                                type="checkbox"
                                id={`${contextName}-allow-${field.id}`}
                                checked={ctx.allowed_field_ids.includes(field.id)}
                                disabled={required.has(field.id)}
                                onChange={(e) => toggleAllowed(contextName, field.id, e.target.checked)}
                              />
                              <label className="form-check-label small" htmlFor={`${contextName}-allow-${field.id}`}>
                                {field.label}
                                {required.has(field.id) ? ' (required)' : ''}
                              </label>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="col-lg-6">
                      <div className="small text-muted mb-2">Default preset</div>
                      <div className="row g-2">
                        {selectableFields
                          .filter((field) => ctx.allowed_field_ids.includes(field.id))
                          .map((field) => (
                            <div key={`${contextName}-default-${field.id}`} className="col-md-6">
                              <div className="form-check">
                                <input
                                  className="form-check-input"
                                  type="checkbox"
                                  id={`${contextName}-default-${field.id}`}
                                  checked={ctx.default_field_ids.includes(field.id)}
                                  disabled={required.has(field.id)}
                                  onChange={(e) => toggleDefault(contextName, field.id, e.target.checked)}
                                />
                                <label className="form-check-label small" htmlFor={`${contextName}-default-${field.id}`}>
                                  {field.label}
                                </label>
                              </div>
                            </div>
                          ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

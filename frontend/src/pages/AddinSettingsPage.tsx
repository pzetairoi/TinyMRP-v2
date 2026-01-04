import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../lib/api'
import type { ApiError } from '../lib/api'

type Scheme = {
  id: string
  name: string
  pattern_segments?: Array<{ kind?: string; field?: string }>
  scope_mode?: string
  scope_keys?: string[]
  is_preset?: boolean
  is_recommended?: boolean
  visibility?: string
}

type UserSettings = {
  default_scheme_id: string
  default_context: Record<string, string>
  sw_property_map: Record<string, string>
  apply_mode: string
  ui_preferences?: { show_advanced?: boolean }
}

const CONTEXT_FIELDS = [
  { key: 'type', label: 'Type' },
  { key: 'family', label: 'Family' },
  { key: 'subfamily', label: 'Subfamily' },
  { key: 'project', label: 'Project' },
  { key: 'site', label: 'Site' },
]

const APPLY_MODES = [
  { value: 'active_config', label: 'Active configuration' },
  { value: 'all_configs', label: 'All configurations' },
  { value: 'selected_configs', label: 'Selected configurations' },
]

function requiredContextKeys(scheme?: Scheme) {
  const out = new Set<string>()
  if (!scheme) return out
  scheme.pattern_segments?.forEach((seg) => {
    if (seg.kind === 'field' && seg.field) out.add(seg.field)
  })
  if (scheme.scope_mode === 'by_type') out.add('type')
  if (scheme.scope_mode === 'by_family') out.add('family')
  if (scheme.scope_mode === 'by_project') out.add('project')
  if (scheme.scope_mode === 'custom_keys') {
    scheme.scope_keys?.forEach((k) => k && out.add(k))
  }
  return out
}

function cleanContext(context: Record<string, string>) {
  const out: Record<string, string> = {}
  Object.entries(context || {}).forEach(([key, value]) => {
    const trimmed = (value || '').trim()
    if (trimmed) out[key] = trimmed
  })
  return out
}

export default function AddinSettingsPage() {
  const [schemes, setSchemes] = useState<Scheme[]>([])
  const [schemeId, setSchemeId] = useState('')
  const [context, setContext] = useState<Record<string, string>>({})
  const [contextJson, setContextJson] = useState('{}')
  const [propertyMap, setPropertyMap] = useState<Record<string, string>>({
    part_number_prop: 'PartNumber',
    revision_prop: 'Revision',
    display_code_prop: 'DisplayCode',
  })
  const [applyMode, setApplyMode] = useState('active_config')
  const [activeTab, setActiveTab] = useState<'quick' | 'advanced'>('quick')
  const [preview, setPreview] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const quickSchemes = useMemo(
    () => schemes.filter((s) => s.is_preset && s.visibility !== 'advanced_only'),
    [schemes],
  )
  const selectedScheme = schemes.find((s) => s.id === schemeId)
  const requiredKeys = requiredContextKeys(selectedScheme)
  const visibleContextFields = requiredKeys.size
    ? CONTEXT_FIELDS.filter((f) => requiredKeys.has(f.key))
    : CONTEXT_FIELDS

  useEffect(() => {
    loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (activeTab === 'quick') {
      setContextJson(JSON.stringify(context || {}, null, 2))
    }
  }, [context, activeTab])

  async function loadAll() {
    setLoading(true)
    setError(null)
    try {
      const schemesResp = await apiFetch<{ schemes: Scheme[] }>('/api/numbering/schemes')
      setSchemes(schemesResp.schemes || [])

      const settingsResp = await apiFetch<{ settings: UserSettings }>('/api/me/settings')
      const settings = settingsResp.settings
      setSchemeId(settings.default_scheme_id || '')
      setContext(settings.default_context || {})
      setPropertyMap(settings.sw_property_map || propertyMap)
      setApplyMode(settings.apply_mode || 'active_config')
      setContextJson(JSON.stringify(settings.default_context || {}, null, 2))
    } catch (err) {
      setError((err as ApiError).message || 'Failed to load settings.')
    } finally {
      setLoading(false)
    }
  }

  async function saveSettings() {
    setMessage(null)
    setError(null)
    try {
      const payload = {
        default_scheme_id: schemeId,
        default_context: cleanContext(context),
        sw_property_map: propertyMap,
        apply_mode: applyMode,
        ui_preferences: { show_advanced: activeTab === 'advanced' },
      }
      await apiFetch('/api/me/settings', {
        method: 'PUT',
        body: JSON.stringify(payload),
      })
      setMessage('Settings saved.')
    } catch (err) {
      setError((err as ApiError).message || 'Failed to save settings.')
    }
  }

  async function previewNext() {
    setMessage(null)
    setError(null)
    if (!schemeId) {
      setError('Select a scheme first.')
      return
    }
    try {
      const resp = await apiFetch<{
        candidate_part_number: string
        candidate_revision: string
        display_code_candidate: string
      }>('/api/numbering/preview', {
        method: 'POST',
        body: JSON.stringify({ scheme_id: schemeId, context: cleanContext(context) }),
      })
      setPreview(
        `Preview: ${resp.candidate_part_number} ${resp.candidate_revision || ''} ${resp.display_code_candidate || ''}`.trim(),
      )
    } catch (err) {
      setError((err as ApiError).message || 'Preview failed.')
    }
  }

  function applyContextJson() {
    try {
      const parsed = JSON.parse(contextJson || '{}')
      if (typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('Context JSON must be an object.')
      }
      setContext(parsed)
      setMessage('Context JSON applied.')
      setError(null)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  return (
    <div className="p-3">
      <h3 className="mb-3">Add-in Settings</h3>
      {loading && <div className="alert alert-info">Loading...</div>}
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-danger">{error}</div>}

      <ul className="nav nav-tabs mb-3">
        <li className="nav-item">
          <button className={`nav-link ${activeTab === 'quick' ? 'active' : ''}`} onClick={() => setActiveTab('quick')}>
            Quick Start
          </button>
        </li>
        <li className="nav-item">
          <button className={`nav-link ${activeTab === 'advanced' ? 'active' : ''}`} onClick={() => setActiveTab('advanced')}>
            Advanced
          </button>
        </li>
      </ul>

      {activeTab === 'quick' && (
        <div className="card p-3 mb-3">
          <div className="mb-3">
            <label className="form-label">Preset Scheme</label>
            <select
              className="form-select"
              value={quickSchemes.some((s) => s.id === schemeId) ? schemeId : ''}
              onChange={(e) => setSchemeId(e.target.value)}
            >
              <option value="">Select a preset</option>
              {quickSchemes.map((scheme) => (
                <option key={scheme.id} value={scheme.id}>
                  {scheme.name}
                </option>
              ))}
            </select>
            {!quickSchemes.some((s) => s.id === schemeId) && schemeId && (
              <div className="form-text">Current scheme is advanced-only. Switch to Advanced to edit.</div>
            )}
          </div>

          <div className="mb-3">
            <label className="form-label">Context</label>
            <div className="row g-2">
              {visibleContextFields.map((field) => (
                <div className="col-md-4" key={field.key}>
                  <label className="form-label small">{field.label}</label>
                  <input
                    className="form-control"
                    value={context[field.key] || ''}
                    onChange={(e) => setContext({ ...context, [field.key]: e.target.value })}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="mb-3">
            <label className="form-label">Property Mapping</label>
            <div className="row g-2">
              <div className="col-md-4">
                <label className="form-label small">Part number property</label>
                <input
                  className="form-control"
                  value={propertyMap.part_number_prop || ''}
                  onChange={(e) => setPropertyMap({ ...propertyMap, part_number_prop: e.target.value })}
                />
              </div>
              <div className="col-md-4">
                <label className="form-label small">Revision property</label>
                <input
                  className="form-control"
                  value={propertyMap.revision_prop || ''}
                  onChange={(e) => setPropertyMap({ ...propertyMap, revision_prop: e.target.value })}
                />
              </div>
              <div className="col-md-4">
                <label className="form-label small">Display code property</label>
                <input
                  className="form-control"
                  value={propertyMap.display_code_prop || ''}
                  onChange={(e) => setPropertyMap({ ...propertyMap, display_code_prop: e.target.value })}
                />
              </div>
            </div>
          </div>

          <div className="mb-3">
            <label className="form-label">Apply Mode</label>
            <select className="form-select" value={applyMode} onChange={(e) => setApplyMode(e.target.value)}>
              {APPLY_MODES.map((mode) => (
                <option key={mode.value} value={mode.value}>
                  {mode.label}
                </option>
              ))}
            </select>
          </div>

          <div className="d-flex gap-2 flex-wrap">
            <button className="btn btn-primary" onClick={saveSettings}>
              Save Settings
            </button>
            <button className="btn btn-outline-secondary" onClick={previewNext}>
              Preview Next
            </button>
            <button className="btn btn-outline-secondary" onClick={loadAll}>
              Reload
            </button>
          </div>
          {preview && <div className="mt-3 alert alert-secondary">{preview}</div>}
        </div>
      )}

      {activeTab === 'advanced' && (
        <div className="card p-3 mb-3">
          <div className="mb-3">
            <label className="form-label">Scheme</label>
            <select className="form-select" value={schemeId} onChange={(e) => setSchemeId(e.target.value)}>
              <option value="">Select a scheme</option>
              {schemes.map((scheme) => (
                <option key={scheme.id} value={scheme.id}>
                  {scheme.name}
                </option>
              ))}
            </select>
          </div>

          <div className="mb-3">
            <label className="form-label">Context JSON</label>
            <textarea
              className="form-control"
              rows={6}
              value={contextJson}
              onChange={(e) => setContextJson(e.target.value)}
            />
            <button className="btn btn-sm btn-outline-secondary mt-2" onClick={applyContextJson}>
              Apply JSON
            </button>
          </div>

          <div className="mb-3">
            <label className="form-label">Property Mapping</label>
            <div className="row g-2">
              <div className="col-md-4">
                <label className="form-label small">Part number property</label>
                <input
                  className="form-control"
                  value={propertyMap.part_number_prop || ''}
                  onChange={(e) => setPropertyMap({ ...propertyMap, part_number_prop: e.target.value })}
                />
              </div>
              <div className="col-md-4">
                <label className="form-label small">Revision property</label>
                <input
                  className="form-control"
                  value={propertyMap.revision_prop || ''}
                  onChange={(e) => setPropertyMap({ ...propertyMap, revision_prop: e.target.value })}
                />
              </div>
              <div className="col-md-4">
                <label className="form-label small">Display code property</label>
                <input
                  className="form-control"
                  value={propertyMap.display_code_prop || ''}
                  onChange={(e) => setPropertyMap({ ...propertyMap, display_code_prop: e.target.value })}
                />
              </div>
            </div>
          </div>

          <div className="mb-3">
            <label className="form-label">Apply Mode</label>
            <select className="form-select" value={applyMode} onChange={(e) => setApplyMode(e.target.value)}>
              {APPLY_MODES.map((mode) => (
                <option key={mode.value} value={mode.value}>
                  {mode.label}
                </option>
              ))}
            </select>
          </div>

          <div className="d-flex gap-2 flex-wrap">
            <button className="btn btn-primary" onClick={saveSettings}>
              Save Settings
            </button>
            <button className="btn btn-outline-secondary" onClick={previewNext}>
              Preview Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

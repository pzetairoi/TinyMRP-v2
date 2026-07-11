import { useEffect, useMemo, useState } from 'react'
import { DataTable } from 'primereact/datatable'
import type { DataTableFilterMeta } from 'primereact/datatable'
import { Column } from 'primereact/column'
import { FilterMatchMode } from 'primereact/api'
import FieldSelector from '../components/FieldSelector'
import {
  contextFields,
  defaultFieldIds,
  fieldValue,
  fieldFilterPlaceholder,
  formatFieldValue,
  loadFieldConfig,
  requiredFieldIds,
  saveFieldPreferences,
  selectedFieldIds,
  updateContextSelection,
  type FieldConfigPayload,
  type FieldDefinition,
  type FieldPreferences,
} from '../lib/fieldConfig'

type Part = {
  id?: string;
  part_number: string;
  description: string;
  category: string;
  revision?: string;
  material?: string;
  finish?: string;
  mass?: string | number;
  process?: string;
  processes?: string[];
  thumb_urls?: string[];
  has_pdf?: boolean;
  has_png?: boolean;
  has_dxf?: boolean;
  has_step?: boolean;
  has_edr?: boolean;
  has_3mf?: boolean;
  has_ply?: boolean;
  has_stl?: boolean;
  has_datasheet?: boolean;
  [key: string]: any;
}

const FALLBACK_PART_FIELDS: FieldDefinition[] = [
  { id: 'thumbnail', label: 'Thumbnail', kind: 'special', filterable: false, sortable: false },
  { id: 'part_number', label: 'Part Number', kind: 'builtin', filterable: true, sortable: true },
  { id: 'revision', label: 'Revision', kind: 'builtin', filterable: true, sortable: true },
  { id: 'description', label: 'Description', kind: 'builtin', filterable: true, sortable: true },
  { id: 'material', label: 'Material', kind: 'builtin', filterable: true, sortable: true },
  { id: 'finish', label: 'Finish', kind: 'builtin', filterable: true, sortable: true },
  { id: 'process', label: 'Process', kind: 'builtin', filterable: true, sortable: true },
]

function defaultColumnMatchMode(field: FieldDefinition) {
  if (field.data_type === 'boolean' || field.data_type === 'number') return FilterMatchMode.EQUALS
  if (field.data_type === 'date') return FilterMatchMode.DATE_IS
  return FilterMatchMode.CONTAINS
}

function defaultColumnFilterMeta(field: FieldDefinition) {
  return {
    value: field.data_type === 'boolean' ? null : '',
    matchMode: defaultColumnMatchMode(field),
  }
}

function ensureColumnFilters(filters: DataTableFilterMeta, fields: FieldDefinition[]) {
  let changed = false
  const next = { ...filters } as DataTableFilterMeta

  for (const field of fields) {
    if (field.filterable === false) continue
    const current = (next as any)?.[field.id]
    // Unwrap leftover menu-style metas ({operator, constraints}) into flat {value, matchMode}.
    const flat = current && typeof current === 'object' && Array.isArray(current.constraints)
      ? current.constraints[0]
      : current
    const normalized = {
      ...defaultColumnFilterMeta(field),
      ...(flat && typeof flat === 'object' && 'value' in flat
        ? { value: flat.value ?? defaultColumnFilterMeta(field).value }
        : {}),
    }
    if (
      current === flat &&
      current?.value === normalized.value &&
      current?.matchMode === normalized.matchMode
    ) continue
    ;(next as any)[field.id] = normalized
    changed = true
  }

  return changed ? next : filters
}

export default function PartsPage() {
  const sp = new URLSearchParams(window.location.search)
  const pickMode = sp.get('pick') === '1' || sp.get('pick') === 'true'
  const initialQ = sp.get('q') || ''
  const jobId = sp.get('job') || ''
  const jobOnlyDefault = !!jobId

  const [rows, setRows] = useState<Part[]>([])
  const [search, setSearch] = useState(initialQ)
  const [debouncedSearch, setDebouncedSearch] = useState(initialQ)
  const [loading, setLoading] = useState(false)
  const [totalRecords, setTotal] = useState(0)
  const [selectedByKey, setSelectedByKey] = useState<Record<string, Part>>({})
  const [qtyById, setQtyById] = useState<Record<string, number>>({})
  const [jobOnly, setJobOnly] = useState(jobOnlyDefault)
  const [fieldConfig, setFieldConfig] = useState<FieldConfigPayload | null>(null)
  const [fieldPreferences, setFieldPreferences] = useState<FieldPreferences | null>(null)
  const [lazy, setLazy] = useState({
    first: 0, rows: 25, sortField: 'part_number', sortOrder: 1 as 1|-1,
    filters: {
      global:      { value: initialQ, matchMode: FilterMatchMode.CONTAINS },
      part_number: { value: '', matchMode: FilterMatchMode.CONTAINS },
      revision:    { value: '', matchMode: FilterMatchMode.CONTAINS },
      description: { value: '', matchMode: FilterMatchMode.CONTAINS },
      category:    { value: '', matchMode: FilterMatchMode.CONTAINS },
      material:    { value: '', matchMode: FilterMatchMode.CONTAINS },
      finish:      { value: '', matchMode: FilterMatchMode.CONTAINS },
      process:     { value: '', matchMode: FilterMatchMode.CONTAINS },
    } as DataTableFilterMeta
  })
  const fallbackLogo = "/branding/logo"

  const keyFor = (p: Part) => `${p.part_number}::${p.revision || ''}`

  useEffect(() => {
    if (!pickMode) return
    document.body.classList.add('pick-mode')
    const nav = document.querySelector('nav.navbar') as HTMLElement | null
    const prevDisplay = nav ? nav.style.display : ''
    if (nav) {
      nav.style.display = 'none'
    }
    return () => {
      document.body.classList.remove('pick-mode')
      if (nav) {
        nav.style.display = prevDisplay
      }
    }
  }, [pickMode])

  useEffect(() => {
    if (pickMode) return
    document.body.classList.add('wide-page')
    return () => {
      document.body.classList.remove('wide-page')
    }
  }, [pickMode])

  useEffect(() => {
    if (pickMode) return
    ;(async () => {
      try {
        const resp = await loadFieldConfig()
        setFieldConfig(resp.config)
        setFieldPreferences(resp.user_preferences || { contexts: {} })
      } catch {
        setFieldConfig(null)
      }
    })()
  }, [pickMode])

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search), 300)
    return () => window.clearTimeout(timer)
  }, [search])

  useEffect(() => {
    setLazy((s) => {
      const current = String((s.filters as any)?.global?.value || '')
      if (current === debouncedSearch) return s
      return {
        ...s,
        first: 0,
        filters: {
          ...s.filters,
          global: { ...(s.filters as any)?.global, value: debouncedSearch },
        } as DataTableFilterMeta,
      }
    })
  }, [debouncedSearch])

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false

    ;(async () => {
      setLoading(true)
      try {
        const payload: any = { ...lazy }
        if (jobId && jobOnly) {
          payload.job = jobId
          payload.job_only = true
        }
        const res = await fetch('/api/parts_lazy', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload),
          signal: controller.signal,
        })
        const j = await res.json()
        if (cancelled) return
        setRows(j.data || [])
        setTotal(j.totalRecords || 0)
      } catch (err: any) {
        if (cancelled || err?.name === 'AbortError') return
        setRows([])
        setTotal(0)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [lazy.first, lazy.rows, lazy.sortField, lazy.sortOrder, JSON.stringify(lazy.filters), jobId, jobOnly])

  const partsFields = fieldConfig ? contextFields(fieldConfig, 'parts_list') : FALLBACK_PART_FIELDS
  const defaultPartsFieldIds = fieldConfig ? defaultFieldIds(fieldConfig, 'parts_list') : ['thumbnail', 'part_number', 'revision', 'description', 'material', 'finish', 'process']
  const requiredPartsFieldIds = fieldConfig ? requiredFieldIds(fieldConfig, 'parts_list') : ['part_number']
  const selectedPartsFieldIds = fieldConfig
    ? selectedFieldIds(fieldConfig, fieldPreferences, 'parts_list')
    : defaultPartsFieldIds
  const selectedPartsFields = useMemo(() => {
    const byId = new Map(partsFields.map((field) => [field.id, field]))
    return selectedPartsFieldIds
      .map((fieldId) => byId.get(fieldId))
      .filter((field): field is FieldDefinition => Boolean(field))
  }, [partsFields, selectedPartsFieldIds])
  const tableFilters = useMemo(
    () => ensureColumnFilters(lazy.filters, selectedPartsFields),
    [lazy.filters, selectedPartsFields],
  )
  const columnSelectorFieldId = useMemo(
    () => (selectedPartsFields.some((f) => f.id === 'thumbnail') ? 'thumbnail' : selectedPartsFields[0]?.id),
    [selectedPartsFields],
  )

  useEffect(() => {
    setLazy((s) => {
      const filters = ensureColumnFilters(s.filters, selectedPartsFields)
      return filters === s.filters ? s : { ...s, filters }
    })
  }, [selectedPartsFields])

  async function persistPartsFieldSelection(fieldIds: string[]) {
    if (!fieldConfig) return
    const nextPrefs = updateContextSelection(fieldConfig, fieldPreferences, 'parts_list', fieldIds)
    setFieldPreferences(nextPrefs)
    try {
      const resp = await saveFieldPreferences(nextPrefs)
      setFieldPreferences(resp.settings.field_preferences || nextPrefs)
    } catch {}
  }

  function setFilterValue(key: string, value: any) {
    setLazy((s) => ({
      ...s,
      first: 0,
      filters: {
        ...s.filters,
        [key]: { ...(s.filters as any)[key], value },
      } as DataTableFilterMeta,
    }))
  }

  function onAddSelected() {
    try {
      const items = Object.values(selectedByKey).map((p) => {
        const id = keyFor(p)
        const qty = Math.max(1, Math.round(qtyById[id] || 1))
        return { pn: p.part_number, rev: p.revision || '', qty, desc: p.description || '' }
      })
      if (items.length && (window as any).opener && typeof (window as any).opener.postMessage === 'function') {
        ;(window as any).opener.postMessage({ type: 'pick-parts', items }, '*')
      }
    } catch {}
    try { window.close() } catch {}
  }

  function renderImageCell(p: Part) {
    const urls = p.thumb_urls || []
    const src = urls[0] || fallbackLogo
    return (
      <img
        src={src}
        onError={(ev: any) => urls[1] ? (ev.currentTarget.src = urls[1]) : (ev.currentTarget.src = fallbackLogo)}
        alt=""
        style={{ maxHeight: 32, maxWidth: 48, objectFit: 'contain', border: '1px solid #eee', borderRadius: 6, padding: 2, background: '#fff' }}
      />
    )
  }

  function renderFieldCell(field: FieldDefinition, row: Part) {
    const value = fieldValue(row, field.id)
    if (field.id === 'thumbnail') return renderImageCell(row)
    if (field.id === 'part_number') {
      const rev = row.revision || ''
      const qs = rev !== undefined ? `?rev=${encodeURIComponent(rev)}` : ''
      return pickMode
        ? <span>{row.part_number}</span>
        : <a href={`/ui/part/${encodeURIComponent(row.part_number)}${qs}`}>{row.part_number}</a>
    }
    if (field.id === 'process') return row.process || row.processes?.join(', ') || formatFieldValue(value)
    if (field.data_type === 'link') {
      const href = String(value || '').trim()
      return href ? <a href={href} target="_blank" rel="noreferrer">Open</a> : '-'
    }
    if (field.data_type === 'boolean') return formatFieldValue(value)
    return formatFieldValue(value)
  }

  function renderColumnFilter(field: FieldDefinition) {
    const rawValue = (tableFilters as any)?.[field.id]?.value
    if (field.data_type === 'boolean') {
      const value = rawValue === true ? 'true' : rawValue === false ? 'false' : ''
      return (
        <select
          className="form-select form-select-sm"
          value={value}
          onChange={(e) => setFilterValue(field.id, e.target.value === '' ? null : e.target.value === 'true')}
        >
          <option value="">Any</option>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      )
    }
    if (field.data_type === 'number') {
      return (
        <input
          className="form-control form-control-sm"
          type="number"
          value={rawValue == null ? '' : String(rawValue)}
          placeholder={field.label}
          onChange={(e) => setFilterValue(field.id, e.target.value === '' ? null : Number(e.target.value))}
        />
      )
    }
    if (field.data_type === 'date') {
      return (
        <input
          className="form-control form-control-sm"
          type="date"
          value={typeof rawValue === 'string' ? rawValue.slice(0, 10) : ''}
          onChange={(e) => setFilterValue(field.id, e.target.value || null)}
        />
      )
    }
    return (
      <input
        className="form-control form-control-sm"
        type="search"
        value={typeof rawValue === 'string' ? rawValue : ''}
        placeholder={fieldFilterPlaceholder(field)}
        onChange={(e) => setFilterValue(field.id, e.target.value)}
      />
    )
  }

  function fieldStyle(fieldId: string) {
    if (fieldId === 'thumbnail') return { width: 110 }
    if (fieldId === 'part_number') return { minWidth: '12ch', width: '12ch' }
    if (fieldId === 'revision') return { width: 90 }
    if (fieldId === 'description') return { minWidth: '32ch', width: '40%' }
    return undefined
  }

  const header = useMemo(() => (
    <div className={`d-flex flex-column flex-md-row align-items-md-center justify-content-between gap-2 px-2 py-1 ${pickMode ? 'pick-header' : ''}`}>
      {pickMode ? (
        <div className="d-flex flex-wrap align-items-center gap-2 flex-grow-1">
          <div>Select parts</div>
          <input
            className="form-control form-control-sm flex-grow-1"
            style={{ minWidth: 240 }}
            type="search"
            placeholder="Search PN or description"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {jobId && (
            <div className="form-check ms-md-2">
              <input className="form-check-input" type="checkbox" id="jobOnly" checked={jobOnly} onChange={(e) => setJobOnly(e.target.checked)} />
              <label className="form-check-label" htmlFor="jobOnly">Job parts only</label>
            </div>
          )}
        </div>
      ) : (
        <div className="d-flex align-items-center gap-2">
          <input
            className="form-control form-control-sm"
            style={{ width: 260, maxWidth: '100%' }}
            type="search"
            placeholder="Search part number, description, notes or comments"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      )}
      {pickMode && (
        <div className="d-flex gap-2">
          <button className="btn btn-sm btn-primary" onClick={onAddSelected} disabled={!Object.keys(selectedByKey).length}>Add Selected</button>
          <button className="btn btn-sm btn-outline-secondary" onClick={() => { try { window.close() } catch {} }}>Cancel</button>
        </div>
      )}
    </div>
  ), [
    pickMode,
    selectedByKey,
    search,
    jobOnly,
    jobId,
  ])

  if (pickMode) {
    const page = Math.floor(lazy.first / lazy.rows) + 1
    const totalPages = Math.max(1, Math.ceil(totalRecords / Math.max(lazy.rows, 1)))
    const canPrev = lazy.first > 0
    const canNext = lazy.first + lazy.rows < totalRecords
    const start = totalRecords ? lazy.first + 1 : 0
    const end = Math.min(lazy.first + lazy.rows, totalRecords)

    return (
      <div className="p-3 pick-container">
        {header}
        <div className="table-responsive">
          <table className="table table-sm align-middle table-striped">
            <thead>
              <tr>
                <th style={{ width: 48 }}>Sel</th>
                <th style={{ width: 140 }}>Qty</th>
                <th style={{ width: 60 }}></th>
                <th style={{ width: '12ch' }}>Part Number</th>
                <th style={{ width: 90 }}>Rev</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {loading && !rows.length && (
                <tr>
                  <td colSpan={6} className="text-center text-muted py-4">Loading...</td>
                </tr>
              )}
              {rows.map((p) => {
                const key = keyFor(p)
                const checked = !!selectedByKey[key]
                const val = qtyById[key] ?? 1
                const urls = p.thumb_urls || []
                return (
                  <tr key={key} className="pick-row">
                    <td>
                      <input
                        className="form-check-input"
                        type="checkbox"
                        checked={checked}
                        onChange={(e) => {
                          const isChecked = e.target.checked
                          setSelectedByKey((prev) => {
                            const next = { ...prev }
                            if (isChecked) {
                              next[key] = p
                            } else {
                              delete next[key]
                            }
                            return next
                          })
                          if (isChecked) {
                            setQtyById((prev) => (prev[key] === undefined ? { ...prev, [key]: 1 } : prev))
                          }
                        }}
                      />
                    </td>
                    <td>
                      <div className="d-flex align-items-center gap-1 pick-qty">
                        <button
                          type="button"
                          className="btn btn-sm btn-outline-secondary"
                          style={{ padding: '0 6px' }}
                          onClick={() => setQtyById((prev) => ({ ...prev, [key]: Math.max(1, val - 1) }))}
                        >
                          -
                        </button>
                        <input
                          type="number"
                          min={1}
                          step={1}
                          inputMode="numeric"
                          className="form-control form-control-sm text-end"
                          style={{ width: 70 }}
                          value={val}
                          onChange={(e) => {
                            const v = Math.max(1, Math.round(parseFloat(e.target.value) || 1))
                            setQtyById((prev) => ({ ...prev, [key]: v }))
                          }}
                          onInput={(e: any) => {
                            const v = Math.max(1, Math.round(parseFloat(e.target.value) || 1))
                            setQtyById((prev) => ({ ...prev, [key]: v }))
                          }}
                        />
                        <button
                          type="button"
                          className="btn btn-sm btn-outline-secondary"
                          style={{ padding: '0 6px' }}
                          onClick={() => setQtyById((prev) => ({ ...prev, [key]: Math.max(1, val + 1) }))}
                        >
                          +
                        </button>
                      </div>
                    </td>
                    <td>
                      {urls.length ? (
                        <img
                          src={urls[0]}
                          onError={(ev: any) => urls[1] ? (ev.currentTarget.src = urls[1]) : (ev.currentTarget.src = fallbackLogo)}
                          alt=""
                          style={{ maxHeight: 32, maxWidth: 48, objectFit: 'contain', border: '1px solid #eee', borderRadius: 6, padding: 2, background: '#fff' }}
                        />
                      ) : (
                        <img
                          src={fallbackLogo}
                          alt=""
                          style={{ maxHeight: 32, maxWidth: 48, objectFit: 'contain', border: '1px solid #eee', borderRadius: 6, padding: 2, background: '#fff' }}
                        />
                      )}
                    </td>
                    <td>{p.part_number}</td>
                    <td>{p.revision || ''}</td>
                    <td>{p.description || ''}</td>
                  </tr>
                )
              })}
              {!rows.length && !loading && (
                <tr>
                  <td colSpan={6} className="text-center text-muted py-4">No parts found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="d-flex flex-column flex-md-row align-items-md-center justify-content-between gap-2">
          <div className="text-muted small">Showing {start}-{end} of {totalRecords}</div>
          <div className="d-flex align-items-center gap-2">
            <select
              className="form-select form-select-sm"
              style={{ width: 110 }}
              value={lazy.rows}
              onChange={(e) => setLazy((s) => ({ ...s, rows: parseInt(e.target.value, 10) || 25, first: 0 }))}
            >
              {[10, 25, 50, 100].map((n) => (
                <option key={n} value={n}>{n} / page</option>
              ))}
            </select>
            <button className="btn btn-sm btn-outline-secondary" disabled={!canPrev} onClick={() => setLazy((s) => ({ ...s, first: Math.max(0, s.first - s.rows) }))}>Prev</button>
            <div className="small text-muted">Page {page} / {totalPages}</div>
            <button className="btn btn-sm btn-outline-secondary" disabled={!canNext} onClick={() => setLazy((s) => ({ ...s, first: s.first + s.rows }))}>Next</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-3">
      <DataTable value={rows}
        header={header}
        lazy paginator totalRecords={totalRecords} rows={lazy.rows} first={lazy.first}
        loading={loading}
        dataKey="id"
        filters={tableFilters}
        sortField={lazy.sortField} sortOrder={lazy.sortOrder}
        onPage={(e) => setLazy(s => ({...s, first: e.first, rows: e.rows}))}
        onSort={(e) =>
           setLazy(s => ({
             ...s,
             sortField: e.sortField || 'part_number',
             sortOrder: (e.sortOrder === -1 ? -1 : 1) as 1 | -1
           }))
         }
        onFilter={(e) => setLazy(s => ({...s, first: 0, filters: { ...s.filters, ...e.filters }}))}
        filterDisplay="row" removableSort rowsPerPageOptions={[10,25,50,100]}
        stripedRows responsiveLayout="scroll"
        resizableColumns
        tableStyle={{ tableLayout: 'fixed' }}
        rowClassName={pickMode ? () => 'pick-row' : undefined}
      >
        {selectedPartsFields.map((field) => {
          const isThumbnail = field.id === 'thumbnail'
          const showColumnSelector = field.id === columnSelectorFieldId && partsFields.length > 0
          return (
            <Column
              key={field.id}
              field={field.id}
              filterField={field.id}
              header={
                showColumnSelector ? (
                  <div className="d-flex align-items-center gap-2">
                    {!isThumbnail && <span>{field.label}</span>}
                    <FieldSelector
                      title="Parts fields"
                      buttonLabel="Columns"
                      buttonIcon="pi pi-table"
                      buttonClassName="btn btn-sm d-inline-flex align-items-center gap-1 parts-columns-trigger"
                      menuAlign="start"
                      availableFields={partsFields}
                      selectedIds={selectedPartsFieldIds}
                      requiredIds={requiredPartsFieldIds}
                      onChange={persistPartsFieldSelection}
                      onReset={() => persistPartsFieldSelection(defaultPartsFieldIds)}
                    />
                  </div>
                ) : (
                  isThumbnail ? '' : field.label
                )
              }
              sortable={field.sortable !== false}
              filter={field.filterable !== false}
              showFilterMenu={false}
              filterMatchMode={defaultColumnMatchMode(field)}
              filterElement={renderColumnFilter(field)}
              body={(row) => renderFieldCell(field, row as Part)}
              style={fieldStyle(field.id)}
            />
          )
        })}

      </DataTable>
    </div>
  )
}

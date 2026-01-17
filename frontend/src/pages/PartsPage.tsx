import { useEffect, useMemo, useState } from 'react'
import { DataTable } from 'primereact/datatable'
import type { DataTableFilterMeta } from 'primereact/datatable'
import { Column } from 'primereact/column'
import { FilterMatchMode } from 'primereact/api'

type Part = {
  id?: string;
  part_number: string;
  description: string;
  category: string;
  revision?: string;
  material?: string;
  finish?: string;
  mass?: string | number;
  processes?: string[];
  thumb_urls?: string[];
  has_pdf?: boolean;
  has_png?: boolean;
  has_dxf?: boolean;
  has_step?: boolean;
  has_datasheet?: boolean;
}

export default function PartsPage() {
  const sp = new URLSearchParams(window.location.search)
  const pickMode = sp.get('pick') === '1' || sp.get('pick') === 'true'
  const initialQ = sp.get('q') || ''
  const jobId = sp.get('job') || ''
  const jobOnlyDefault = !!jobId

  const [rows, setRows] = useState<Part[]>([])
  const [search, setSearch] = useState(initialQ)
  const [loading, setLoading] = useState(false)
  const [totalRecords, setTotal] = useState(0)
  const [selectedByKey, setSelectedByKey] = useState<Record<string, Part>>({})
  const [qtyById, setQtyById] = useState<Record<string, number>>({})
  const [jobOnly, setJobOnly] = useState(jobOnlyDefault)
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
      has_pdf:     { value: '', matchMode: FilterMatchMode.EQUALS },
    } as DataTableFilterMeta
  })
  const fallbackLogo = "/static/images/logo.png"

  const keyFor = (p: Part) => `${p.part_number}::${p.revision || ''}`

  const coverageBadge = (label: string, on: boolean | undefined) => (
    <span
      className={`badge ${on ? 'bg-success' : 'bg-light text-muted'}`}
      style={{ fontSize: '0.65rem', padding: '0.25rem 0.4rem' }}
      title={label}
    >
      {label}
    </span>
  )

  const coverageBody = (p: Part) => (
    <div className="d-flex flex-wrap gap-1">
      {coverageBadge('PDF', p.has_pdf)}
      {coverageBadge('DXF', p.has_dxf)}
      {coverageBadge('STEP', p.has_step)}
      {coverageBadge('DS', p.has_datasheet)}
    </div>
  )

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
    (async () => {
      setLoading(true)
      const payload: any = { ...lazy }
      if (jobId && jobOnly) {
        payload.job = jobId
        payload.job_only = true
      }
      const res = await fetch('/api/parts_lazy', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      })
      const j = await res.json()
      setRows(j.data || [])
      setTotal(j.totalRecords || 0)
      setLoading(false)
    })()
  }, [lazy.first, lazy.rows, lazy.sortField, lazy.sortOrder, JSON.stringify(lazy.filters), jobId, jobOnly])

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

  function applyQuickFilter(kind: 'missing_pdf' | 'missing_material' | 'hardware' | 'sheet' | 'clear') {
    setLazy((s) => {
      const nextFilters: any = { ...(s.filters as any) }
      if (kind === 'clear') {
        nextFilters.material = { ...(nextFilters.material || {}), value: '' }
        nextFilters.process = { ...(nextFilters.process || {}), value: '' }
        nextFilters.has_pdf = { ...(nextFilters.has_pdf || {}), value: '' }
      }
      if (kind === 'missing_pdf') {
        nextFilters.has_pdf = { ...(nextFilters.has_pdf || {}), value: 'false' }
      }
      if (kind === 'missing_material') {
        nextFilters.material = { ...(nextFilters.material || {}), value: '(missing)' }
      }
      if (kind === 'hardware') {
        nextFilters.process = { ...(nextFilters.process || {}), value: 'hardware' }
      }
      if (kind === 'sheet') {
        nextFilters.process = { ...(nextFilters.process || {}), value: 'sheet metal' }
      }
      return { ...s, first: 0, filters: nextFilters }
    })
  }

  const header = useMemo(() => (
    <div className={`d-flex flex-column flex-md-row align-items-md-center justify-content-between gap-2 p-2 ${pickMode ? 'pick-header' : ''}`}>
      <div className="d-flex align-items-center gap-2">
        <div>{pickMode ? 'Select parts' : 'Parts'}</div>
        <input
          className="form-control form-control-sm"
          style={{ minWidth: 220 }}
          type="search"
          placeholder="Search PN or description"
          value={search}
          onChange={(e) => {
            const val = e.target.value
            setSearch(val)
            setLazy((s) => ({
              ...s,
              first: 0,
              filters: {
                ...s.filters,
                global: { ...(s.filters as any)?.global, value: val },
              } as DataTableFilterMeta,
            }))
          }}
        />
        {pickMode && jobId && (
          <div className="form-check ms-2">
            <input className="form-check-input" type="checkbox" id="jobOnly" checked={jobOnly} onChange={(e) => setJobOnly(e.target.checked)} />
            <label className="form-check-label" htmlFor="jobOnly">Job parts only</label>
          </div>
        )}
        {!pickMode && (
          <div className="d-flex flex-wrap gap-2 ms-2">
            <button className="btn btn-sm btn-outline-secondary" onClick={() => applyQuickFilter('missing_pdf')}>Missing PDF</button>
            <button className="btn btn-sm btn-outline-secondary" onClick={() => applyQuickFilter('missing_material')}>Missing Material</button>
            <button className="btn btn-sm btn-outline-secondary" onClick={() => applyQuickFilter('hardware')}>Hardware</button>
            <button className="btn btn-sm btn-outline-secondary" onClick={() => applyQuickFilter('sheet')}>Sheet metal</button>
            <button className="btn btn-sm btn-outline-secondary" onClick={() => applyQuickFilter('clear')}>Clear</button>
          </div>
        )}
      </div>
      {pickMode && (
        <div className="d-flex gap-2">
          <button className="btn btn-sm btn-primary" onClick={onAddSelected} disabled={!Object.keys(selectedByKey).length}>Add Selected</button>
          <button className="btn btn-sm btn-outline-secondary" onClick={() => { try { window.close() } catch {} }}>Cancel</button>
        </div>
      )}
    </div>
  ), [pickMode, selectedByKey, search, jobOnly])

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
        sortField={lazy.sortField} sortOrder={lazy.sortOrder}
        onPage={(e) => setLazy(s => ({...s, first: e.first, rows: e.rows}))}
        onSort={(e) =>
           setLazy(s => ({
             ...s,
             sortField: e.sortField || 'part_number',
             sortOrder: (e.sortOrder === -1 ? -1 : 1) as 1 | -1
           }))
         }
        onFilter={(e) => setLazy(s => ({...s, first: 0, filters: e.filters}))}
        filterDisplay="row" removableSort rowsPerPageOptions={[10,25,50,100]}
        stripedRows responsiveLayout="scroll"
        rowClassName={pickMode ? () => 'pick-row' : undefined}
      >
        {pickMode && (
        <Column header="Sel" body={(p: any) => {
          const key = `${p.part_number}::${p.revision || ''}`
          const checked = !!selectedByKey[key]
          return (
            <input
              className="form-check-input"
              type="checkbox"
              checked={checked}
              onChange={(e) => {
                const isChecked = e.target.checked
                setSelectedByKey((prev) => {
                  const next = { ...prev }
                  if (isChecked) {
                    next[key] = p as Part
                  } else {
                    delete next[key]
                  }
                  return next
                })
                if (isChecked) {
                  setQtyById((prev) => (prev[key] === undefined ? { ...prev, [key]: 1 } : prev))
                }
              }}
              onClick={(e) => e.stopPropagation()}
              onMouseDown={(e) => e.stopPropagation()}
              onPointerDown={(e) => e.stopPropagation()}
            />
          )
        }} style={{ width: 48 }} />)}
        {pickMode && (
        <Column header="Qty" body={(p: any) => {
          const id = `${p.part_number}::${p.revision || ''}`
          const val = qtyById[id] ?? 1
          return (
            <div className="d-flex align-items-center gap-1 pick-qty" onClick={(e)=>e.stopPropagation()} onMouseDown={(e)=>e.stopPropagation()} onPointerDown={(e)=>e.stopPropagation()}>
              <button
                type="button"
                className="btn btn-sm btn-outline-secondary"
                style={{padding:'0 6px'}}
                onMouseDown={(e) => e.stopPropagation()}
                onPointerDown={(e) => e.stopPropagation()}
                onClick={(e) => {e.preventDefault(); e.stopPropagation(); const v=Math.max(1, val-1); setQtyById(prev=>({...prev,[id]:v}))}}
              >-</button>
              <input
                type="number"
                min={1}
                step={1}
                inputMode="numeric"
                pattern="[0-9]*"
                className="form-control form-control-sm text-end"
                style={{ width: 70 }}
                value={val}
                onClick={(e) => e.stopPropagation()}
                onMouseDown={(e) => e.stopPropagation()}
                onPointerDown={(e) => e.stopPropagation()}
                onKeyDown={(e) => e.stopPropagation()}
                onChange={(e) => {
                  e.stopPropagation()
                  const v = Math.max(1, Math.round(parseFloat(e.target.value) || 1))
                  setQtyById((prev) => ({ ...prev, [id]: v }))
                }}
              />
              <button
                type="button"
                className="btn btn-sm btn-outline-secondary"
                style={{padding:'0 6px'}}
                onMouseDown={(e) => e.stopPropagation()}
                onPointerDown={(e) => e.stopPropagation()}
                onClick={(e) => {e.preventDefault(); e.stopPropagation(); const v=Math.max(1, val+1); setQtyById(prev=>({...prev,[id]:v}))}}
              >+</button>
            </div>
          )
        }} style={{ width: 140 }} />)}

        <Column header="" body={(p: any) => {
          const urls = (p as Part).thumb_urls || []
          const src = urls[0] || fallbackLogo
          return (
            <img
              src={src}
              onError={(ev:any) => urls[1] ? (ev.currentTarget.src = urls[1]) : (ev.currentTarget.src = fallbackLogo)}
              alt=""
              style={{ maxHeight: 32, maxWidth: 48, objectFit: 'contain', border: '1px solid #eee', borderRadius: 6, padding: 2, background: '#fff' }}
            />
          )
        }} style={{ width: 60 }} />
        {!pickMode && (
          <Column header="Docs" body={(p: any) => coverageBody(p as Part)} style={{ width: 150 }} />
        )}
        <Column field="part_number" header="Part Number" sortable filter showFilterMenu={false}
        filterMatchMode="contains" filterMatchModeOptions={["contains"]}
        style={{ minWidth: '12ch', width: '12ch' }}
        body={(p) => {
          const rev = (p as Part).revision || ''
          const qs = rev !== undefined ? `?rev=${encodeURIComponent(rev)}` : ''
          return pickMode
            ? <span>{p.part_number}</span>
            : <a href={`/ui/part/${encodeURIComponent(p.part_number)}${qs}`}>{p.part_number}</a>
        }} />

        <Column field="revision" header="Rev" sortable filter showFilterMenu={false} style={{width: 90}}
                filterMatchMode="contains" filterMatchModeOptions={["contains"]} />

        <Column field="description" header="Description" sortable filter showFilterMenu={false}
                style={{ minWidth: '32ch', width: '40%' }}
                filterMatchMode="contains" filterMatchModeOptions={["contains"]} />

        <Column field="material" header="Material" sortable filter showFilterMenu={false}
                filterMatchMode="contains" filterMatchModeOptions={["contains"]} />
        <Column field="finish" header="Finish" sortable filter showFilterMenu={false}
                filterMatchMode="contains" filterMatchModeOptions={["contains"]} />
        <Column field="processes" filterField="process" header="Process" sortable filter fieldType="text" showFilterMenu={false}
                body={(p) => (p as Part).processes?.join(', ') || ''}
                filterMatchMode="contains" filterMatchModeOptions={["contains"]} />

      </DataTable>
    </div>
  )
}

import { useEffect, useMemo, useState } from 'react'
import { DataTable } from 'primereact/datatable'
import type { DataTableFilterMeta } from 'primereact/datatable'
import { Column } from 'primereact/column'
import { FilterMatchMode } from 'primereact/api'
import { Link } from 'react-router-dom'

type Part = { id?: string; part_number: string; description: string; category: string; revision?: string; material?: string; finish?: string; mass?: string | number; processes?: string[]; thumb_urls?: string[] }

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
  const [selection, setSelection] = useState<Part[]>([])
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
    } as DataTableFilterMeta
  })

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
      const items = (selection || []).map((p) => {
        const id = `${p.part_number}::${p.revision || ''}`
        const qty = Math.max(1, Math.round(qtyById[id] || 1))
        return { pn: p.part_number, rev: p.revision || '', qty, desc: p.description || '' }
      })
      if (items.length && (window as any).opener && typeof (window as any).opener.postMessage === 'function') {
        ;(window as any).opener.postMessage({ type: 'pick-parts', items }, '*')
      }
    } catch {}
    try { window.close() } catch {}
  }

  const header = useMemo(() => (
    <div className="d-flex flex-column flex-md-row align-items-md-center justify-content-between gap-2 p-2">
      <div className="d-flex align-items-center gap-2">
        <div>Parts</div>
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
      </div>
      {pickMode && (
        <div className="d-flex gap-2">
          <button className="btn btn-sm btn-primary" onClick={onAddSelected} disabled={!selection.length}>Add Selected</button>
          <button className="btn btn-sm btn-outline-secondary" onClick={() => { try { window.close() } catch {} }}>Cancel</button>
        </div>
      )}
    </div>
  ), [pickMode, selection, search])

  return (
    <div className="p-3">
      <DataTable value={rows}
        header={header}
        lazy paginator totalRecords={totalRecords} rows={lazy.rows} first={lazy.first}
        loading={loading}
        dataKey="id"
        selection={selection}
        onSelectionChange={(e) => {
          const next = e.value as Part[]
          setSelection(next)
          setQtyById((prev) => {
            const updated = { ...prev }
            next.forEach((p) => {
              const id = p.id || `${p.part_number}::${p.revision || ''}`
              if (updated[id] === undefined) updated[id] = 1
            })
            return updated
          })
        }}
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
      >
        {pickMode && (
        <Column selectionMode="multiple" style={{ width: 48 }} />)}
        {pickMode && (
        <Column header="Qty" body={(p: any) => {
          const id = (p.id as string) || `${p.part_number}::${p.revision || ''}`
          const val = qtyById[id] ?? 1
          return (
            <div className="d-flex align-items-center gap-1" onClick={(e)=>e.stopPropagation()} onMouseDown={(e)=>e.stopPropagation()}>
              <button type="button" className="btn btn-sm btn-outline-secondary" style={{padding:'0 6px'}} onClick={(e) => {e.preventDefault(); const v=Math.max(1, val-1); setQtyById(prev=>({...prev,[id]:v}))}}>−</button>
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
                onKeyDown={(e) => e.stopPropagation()}
                onChange={(e) => {
                  e.stopPropagation()
                  const v = Math.max(1, Math.round(parseFloat(e.target.value) || 1))
                  setQtyById((prev) => ({ ...prev, [id]: v }))
                }}
              />
              <button type="button" className="btn btn-sm btn-outline-secondary" style={{padding:'0 6px'}} onClick={(e) => {e.preventDefault(); const v=Math.max(1, val+1); setQtyById(prev=>({...prev,[id]:v}))}}>+</button>
            </div>
          )
        }} style={{ width: 140 }} />)}

        <Column header="" body={(p: any) => {
          const urls = (p as Part).thumb_urls || []
          return urls.length ? (
            <img src={urls[0]} onError={(ev:any) => urls[1] && (ev.currentTarget.src = urls[1])} alt="" style={{ maxHeight: 32, maxWidth: 48, objectFit: 'contain', border: '1px solid #eee', borderRadius: 6, padding: 2, background: '#fff' }} />
          ) : null
        }} style={{ width: 60 }} />
        <Column field="part_number" header="Part Number" sortable filter showFilterMenu={false}
        filterMatchMode="contains" filterMatchModeOptions={["contains"]}
        style={{ minWidth: '12ch', width: '12ch' }}
        body={(p) => {
          const rev = (p as Part).revision || ''
          const qs = rev !== undefined ? `?rev=${encodeURIComponent(rev)}` : ''
          return <a href={`/ui/part/${encodeURIComponent(p.part_number)}${qs}`}>{p.part_number}</a>
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

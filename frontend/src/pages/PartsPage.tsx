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

  const [rows, setRows] = useState<Part[]>([])
  const [loading, setLoading] = useState(false)
  const [totalRecords, setTotal] = useState(0)
  const [selection, setSelection] = useState<Part[]>([])
  const [lazy, setLazy] = useState({
    first: 0, rows: 25, sortField: 'part_number', sortOrder: 1 as 1|-1,
    filters: {
      global:      { value: '', matchMode: FilterMatchMode.CONTAINS },
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
      const res = await fetch('/api/parts_lazy', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(lazy)
      })
      const j = await res.json()
      setRows(j.data || [])
      setTotal(j.totalRecords || 0)
      setLoading(false)
    })()
  }, [lazy.first, lazy.rows, lazy.sortField, lazy.sortOrder, JSON.stringify(lazy.filters)])

  function onAddSelected() {
    try {
      const items = (selection || []).map((p) => ({ pn: p.part_number, rev: p.revision || '' }))
      if (items.length && (window as any).opener && typeof (window as any).opener.postMessage === 'function') {
        ;(window as any).opener.postMessage({ type: 'pick-parts', items }, '*')
      }
    } catch {}
    try { window.close() } catch {}
  }

  const header = useMemo(() => (
    <div className="d-flex align-items-center justify-content-between p-2">
      <div>Parts</div>
      {pickMode && (
        <div className="d-flex gap-2">
          <button className="btn btn-sm btn-primary" onClick={onAddSelected} disabled={!selection.length}>Add Selected</button>
          <button className="btn btn-sm btn-outline-secondary" onClick={() => { try { window.close() } catch {} }}>Cancel</button>
        </div>
      )}
    </div>
  ), [pickMode, selection])

  return (
    <div className="p-3">
      <DataTable value={rows}
        header={header}
        lazy paginator totalRecords={totalRecords} rows={lazy.rows} first={lazy.first}
        loading={loading}
        dataKey="id"
        selectionMode={pickMode ? undefined : undefined}
        selection={selection}
        onSelectionChange={(e) => setSelection(e.value as Part[])}
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

        <Column header="" body={(p: any) => {
          const urls = (p as Part).thumb_urls || []
          return urls.length ? (
            <img src={urls[0]} onError={(ev:any) => urls[1] && (ev.currentTarget.src = urls[1])} alt="" style={{ maxHeight: 32, maxWidth: 48, objectFit: 'contain', border: '1px solid #eee', borderRadius: 6, padding: 2, background: '#fff' }} />
          ) : null
        }} style={{ width: 60 }} />
        <Column field="part_number" header="Part Number" sortable filter showFilterMenu={false}
        filterMatchMode="contains" filterMatchModeOptions={["contains"]}
        body={(p) => {
          const rev = (p as Part).revision || ''
          const qs = rev !== undefined ? `?rev=${encodeURIComponent(rev)}` : ''
          return <a href={`/ui/part/${encodeURIComponent(p.part_number)}${qs}`}>{p.part_number}</a>
        }} />

        <Column field="revision" header="Rev" sortable filter showFilterMenu={false} style={{width: 90}}
                filterMatchMode="contains" filterMatchModeOptions={["contains"]} />

        <Column field="description" header="Description" sortable filter showFilterMenu={false}
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

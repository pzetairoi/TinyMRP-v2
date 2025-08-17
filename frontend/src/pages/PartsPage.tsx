import { useEffect, useState } from 'react'
import { DataTable } from 'primereact/datatable'
import type { DataTableFilterMeta } from 'primereact/datatable'
import { Column } from 'primereact/column'
import { FilterMatchMode } from 'primereact/api'
import { Link } from 'react-router-dom'

type Part = { part_number: string; description: string; category: string }

export default function PartsPage() {
  const [rows, setRows] = useState<Part[]>([])
  const [loading, setLoading] = useState(false)
  const [totalRecords, setTotal] = useState(0)
  const [lazy, setLazy] = useState({
    first: 0, rows: 25, sortField: 'part_number', sortOrder: 1 as 1|-1,
    filters: {
      part_number: { value: '', matchMode: FilterMatchMode.CONTAINS },
      description: { value: '', matchMode: FilterMatchMode.CONTAINS },
      category:    { value: '', matchMode: FilterMatchMode.CONTAINS },
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

  return (
    <div className="p-3">
      <DataTable value={rows}
        header={<div className="p-2">Parts</div>}
        lazy paginator totalRecords={totalRecords} rows={lazy.rows} first={lazy.first}
        loading={loading}
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
        <Column field="part_number" header="Part Number" sortable filter showFilterMenu={false}
        filterMatchMode="contains" filterMatchModeOptions={["contains"]}
        body={(p) => <a href={`/ui/part/${encodeURIComponent(p.part_number)}`}>{p.part_number}</a>} />


        <Column field="description" header="Description" sortable filter showFilterMenu={false}
                filterMatchMode="contains" filterMatchModeOptions={["contains"]} />

        <Column field="category" header="Category" sortable filter showFilterMenu={false}
                filterMatchMode="contains" filterMatchModeOptions={["contains"]} />

      </DataTable>
    </div>
  )
}

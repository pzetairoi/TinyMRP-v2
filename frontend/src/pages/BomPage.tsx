import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Tree } from 'primereact/tree'
import { DataTable } from 'primereact/datatable'
import { Column } from 'primereact/column'
import { FilterMatchMode } from 'primereact/api'

type WURow = [string,string,number,string,string]

export default function BomPage() {
  const { pn = '' } = useParams()
  const [nodes, setNodes] = useState<any[]>([])
  const [wuRows, setWuRows] = useState<WURow[]>([])
  const [total, setTotal] = useState(0)
  const [loadingWU, setLoadingWU] = useState(false)
  const [lazy, setLazy] = useState({ first: 0, rows: 25, sortField: 'parent_pn', sortOrder: 1 as 1|-1,
    filters: {
      parent_pn:   { value: '', matchMode: FilterMatchMode.CONTAINS },
      parent_desc: { value: '', matchMode: FilterMatchMode.CONTAINS },
      alt_group:   { value: '', matchMode: FilterMatchMode.CONTAINS },
    } as any
  })

  // Tree: load root
  useEffect(() => {
    (async () => {
      const r = await fetch(`/api/bom_tree?pn=${encodeURIComponent(pn)}`); setNodes(await r.json())
    })()
  }, [pn])

  const onLoadNode = async (node: any) => {
    const r = await fetch(`/api/bom_tree?parent=${encodeURIComponent(node.key)}`)
    node.children = await r.json()
    setNodes([...nodes])
  }

  // Where-used
  useEffect(() => {
    (async () => {
      setLoadingWU(true)
      const r = await fetch('/api/whereused_lazy', { method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ pn, ...lazy }) })
      const j = await r.json()
      setWuRows(j.data || []); setTotal(j.totalRecords || 0); setLoadingWU(false)
    })()
  }, [pn, lazy.first, lazy.rows, lazy.sortField, lazy.sortOrder, JSON.stringify(lazy.filters)])

  return (
    <div className="p-3">
      <h5 className="mb-3">BOM · {pn}</h5>

      <div className="mb-4">
        <Tree value={nodes} loading={!nodes.length} onExpand={(e: any) => onLoadNode(e.node)} />
      </div>

      <DataTable value={wuRows}
        header={<div className="p-2">Where-used</div>}
        lazy paginator totalRecords={total} rows={lazy.rows} first={lazy.first} loading={loadingWU}
        sortField={lazy.sortField} sortOrder={lazy.sortOrder}
        onPage={(e)=>setLazy(s=>({...s, first:e.first, rows:e.rows}))}
        onSort={(e)=>setLazy(s=>({...s, sortField:e.sortField, sortOrder:e.sortOrder}))}
        onFilter={(e)=>setLazy(s=>({...s, first:0, filters:e.filters}))}
        filterDisplay="row" removableSort rowsPerPageOptions={[10,25,50,100]}
        stripedRows responsiveLayout="scroll"
      >
        <Column field="0" header="Parent PN" sortable filter showFilterMenu={false} />
        <Column field="1" header="Parent Description" sortable filter showFilterMenu={false} />
        <Column field="2" header="Qty" sortable />
        <Column field="3" header="UoM" sortable />
        <Column field="4" header="Alt Group" sortable filter showFilterMenu={false} />
      </DataTable>
    </div>
  )
}

// frontend/src/pages/BomPage.tsx
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { TreeTable } from 'primereact/treetable'
import type { TreeNode } from 'primereact/treenode'
import { DataTable } from 'primereact/datatable'
import { Column } from 'primereact/column'
import { FilterMatchMode } from 'primereact/api'
import ThumbImg from '../components/ThumbImg'

// Import the ImageStrip component to display images for the part
import ImageStrip from "../components/ImageStrip"


// Backend must return Where-Used rows as objects with these keys:
// { parent_pn, parent_desc, qty, uom, alt_group }
// See app/views/whereused.py in the backend patch.

type WURow = {
  parent_pn: string
  parent_desc: string
  qty: number
  uom: string
  alt_group: string
}

type LazyWUState = {
  first: number
  rows: number
  sortField: 'parent_pn' | 'parent_desc' | 'qty' | 'uom' | 'alt_group'
  sortOrder: 1 | -1
  filters: Record<string, { value: string; matchMode: string }>
}

export default function BomPage() {
  // PN comes from router (/ui/bom/:pn). If you are using the Jinja shell, it
  // also exists in window.__INITIAL__.pn; we fall back gracefully.
  const route = useParams()
  const pn = route.pn || (window as any).__INITIAL__?.pn || ''

  // --- BOM Tree ---
  const [nodes, setNodes] = useState<TreeNode[]>([])
  const [expandedKeys, setExpandedKeys] = useState<Record<string, boolean>>({})

  // Lazy loading state for Where-Used table
  const [treeFilters, setTreeFilters] = useState<any>({
   global: { value: '', matchMode: FilterMatchMode.CONTAINS },
  'data.pn': { value: '', matchMode: FilterMatchMode.CONTAINS },
  'data.desc': { value: '', matchMode: FilterMatchMode.CONTAINS },
  'data.alt_group': { value: '', matchMode: FilterMatchMode.CONTAINS },
})

  // Load root
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const r = await fetch(`/api/bom_tree?pn=${encodeURIComponent(pn)}`)
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        const root: TreeNode[] = await r.json()
        if (!cancelled) setNodes(root)
      } catch (e) {
        console.error('bom_tree root failed', e)
        if (!cancelled) setNodes([])
      }
    })()
    return () => {
      cancelled = true
    }
  }, [pn])

  // Helper to immutably set children for a node key
  function setNodeChildren(tree: TreeNode[], key: string, children: TreeNode[]): TreeNode[] {
    return tree.map((n) => {
      if (String(n.key) === String(key)) {
        return { ...n, children }
      }
      if (n.children && n.children.length) {
        return { ...n, children: setNodeChildren(n.children as TreeNode[], key, children) }
      }
      return n
    })
  }

  async function loadChildrenFor(key: string) {
    try {
      const r = await fetch(`/api/bom_tree?parent=${encodeURIComponent(key)}`)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const kids: TreeNode[] = await r.json()
      setNodes((prev) => setNodeChildren(prev, key, kids))
      setExpandedKeys((prev) => ({ ...prev, [key]: true }))
    } catch (e) {
      console.error('bom_tree children failed', e)
    }
  }

  // --- Where-Used ---
  const [wuRows, setWuRows] = useState<WURow[]>([])
  const [wuTotal, setWuTotal] = useState(0)
  const [loadingWU, setLoadingWU] = useState(false)

  const [lazy, setLazy] = useState<LazyWUState>({
    first: 0,
    rows: 25,
    sortField: 'parent_pn',
    sortOrder: 1,
    filters: {
      parent_pn: { value: '', matchMode: FilterMatchMode.CONTAINS },
      parent_desc: { value: '', matchMode: FilterMatchMode.CONTAINS },
      alt_group: { value: '', matchMode: FilterMatchMode.CONTAINS },
    },
  })

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoadingWU(true)
      try {
        const r = await fetch('/api/whereused_lazy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pn, ...lazy }),
        })
        if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`)
        const j = await r.json()
        if (!cancelled) {
          setWuRows(j.data || [])
          setWuTotal(j.totalRecords || 0)
        }
      } catch (e) {
        console.error('whereused_lazy failed', e)
        if (!cancelled) {
          setWuRows([])
          setWuTotal(0)
        }
      } finally {
        if (!cancelled) setLoadingWU(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [pn, lazy.first, lazy.rows, lazy.sortField, lazy.sortOrder, JSON.stringify(lazy.filters)])

  function ImageThumb({ urls }: { urls?: string[] }) {
  if (!urls || !urls.length) return <div style={{ width: 64, height: 40, background: '#f2f2f2', borderRadius: 8 }} />
  // simple fallback: if first fails try the next
  const [i, setI] = useState(0)
  return (
    <img
      src={urls[i]}
      onError={() => i < (urls?.length || 0) - 1 && setI(i + 1)}
      alt=""
      style={{ maxHeight: 40, maxWidth: 64, objectFit: 'contain', border: '1px solid #eee', borderRadius: 8, padding: 4, background: '#fff' }}
    />
  )
}


  return (
    <div className="p-3">
      <h5 className="mb-2">BOM · {pn}</h5>

      {/* Imágenes del PN (usa última revisión si no se especifica) */}
      <ImageStrip pn={pn} />

{/* BOM TreeTable */}

<div className="mb-4">
  <TreeTable
    value={nodes}
    expandedKeys={expandedKeys}
    onToggle={(e: any) => setExpandedKeys(e.value)}
    onExpand={(e: any) => e?.node?.key && loadChildrenFor(String(e.node.key))}
    scrollable
    scrollHeight="60vh"
    resizableColumns
    showGridlines
    size="small"
  >
    <Column
      header=""
      body={(node: any) => {
        const urls = node?.data?.thumb_urls || []
        return urls.length ? (
          <img
            src={urls[0]}
            onError={(ev: any) => urls[1] && (ev.currentTarget.src = urls[1])}
            alt=""
            style={{ maxHeight: 40, maxWidth: 64, objectFit: 'contain', border: '1px solid #eee', borderRadius: 8, padding: 4, background: '#fff' }}
          />
        ) : <div style={{ width: 64, height: 40, background: '#f2f2f2', borderRadius: 8 }} />
      }}
      style={{ width: 70 }}
    />
    <Column
      field="pn"           // <- NOTE: not "data.pn"
      header="Part Number"
      expander             // <- toggler here
      sortable
      body={(node: any) => {
        const cpn = node?.data?.pn || ''
        return <a href={`/ui/part/${encodeURIComponent(cpn)}`}>{cpn}</a>
      }}
      style={{ width: 240 }}
    />
    <Column field="desc" header="Description" sortable />
    <Column field="qty" header="Qty" sortable style={{ width: 100 }} />
    <Column field="uom" header="UoM" sortable style={{ width: 100 }} />
    <Column field="alt_group" header="Alt Group" sortable style={{ width: 140 }} />
  </TreeTable>
</div>





      {/* Where-used */}
      <DataTable
        value={wuRows}
        header={<div className="p-2">Where-used</div>}
        lazy
        paginator
        totalRecords={wuTotal}
        rows={lazy.rows}
        first={lazy.first}
        loading={loadingWU}
        sortField={lazy.sortField}
        sortOrder={lazy.sortOrder}
        onPage={(e) => setLazy((s) => ({ ...s, first: e.first, rows: e.rows }))}
        onSort={(e) =>
          setLazy((s) => ({
            ...s,
            sortField: (e.sortField as LazyWUState['sortField']) || 'parent_pn',
            sortOrder: (e.sortOrder === -1 ? -1 : 1) as 1 | -1,
          }))
        }
        onFilter={(e) => setLazy((s) => ({ ...s, first: 0, filters: e.filters }))}
        filterDisplay="row"
        removableSort
        rowsPerPageOptions={[10, 25, 50, 100]}
        stripedRows
        responsiveLayout="scroll"
      >
        <Column field="parent_pn" header="Parent PN" sortable filter showFilterMenu={false} filterMatchMode="contains" filterMatchModeOptions={["contains"]} />
        <Column field="parent_desc" header="Parent Description" sortable filter showFilterMenu={false} filterMatchMode="contains" filterMatchModeOptions={["contains"]} />
        <Column field="qty" header="Qty" sortable />
        <Column field="uom" header="UoM" sortable />
        <Column field="alt_group" header="Alt Group" sortable filter showFilterMenu={false} filterMatchMode="contains" filterMatchModeOptions={["contains"]} />
      </DataTable>
    </div>
  )
}

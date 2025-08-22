import { useEffect, useMemo, useState } from "react"
import { useParams, Link } from "react-router-dom"
import { DataTable } from "primereact/datatable"
import { Column } from "primereact/column"
import ImageStrip from "../components/ImageStrip"

import { TreeTable } from 'primereact/treetable'
import type { TreeNode } from 'primereact/treenode'
import { Column } from 'primereact/column'
import ThumbImg from '../components/ThumbImg'

const [bomNodes, setBomNodes] = useState<TreeNode[]>([])
const [bomExpanded, setBomExpanded] = useState<Record<string, boolean>>({})



type Part = {
  part_number: string; description: string; revision?: string; category?: string; uom?: string; attrs: Record<string, any>
}
type FileRow = { ext_group: string; ext: string; rel_path?: string; size?: number; mtime?: string; url: string; urls: string[] }
type ChildRow = { child_pn: string; child_desc: string; qty: number; uom: string; alt_group: string }
type WURow = { parent_pn: string; parent_desc: string; qty: number; uom: string; alt_group: string }

export default function PartDetailPage() {
  const route = useParams()
  const pn = route.pn || (window as any).__INITIAL__?.pn || ""
  const [part, setPart] = useState<Part | null>(null)
  const [files, setFiles] = useState<FileRow[]>([])
  const [children, setChildren] = useState<ChildRow[]>([])
  const [wu, setWU] = useState<WURow[]>([])
  const [loading, setLoading] = useState(true)

  // Load BOM tree nodes
  function setNodeChildren(tree: TreeNode[], key: string, children: TreeNode[]): TreeNode[] {
  return tree.map((n) => {
    if (String(n.key) === String(key)) return { ...n, children }
    if (n.children?.length) return { ...n, children: setNodeChildren(n.children as any, key, children) }
    return n
  })
}

//
async function onExpandNode(e: any) {
  const key = String(e?.node?.key || '')
  if (!key) return
  try {
    const r = await fetch(`/api/bom_tree?parent=${encodeURIComponent(key)}&withThumb=1`)
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    const kids: TreeNode[] = await r.json()
    setBomNodes((prev) => setNodeChildren(prev, key, kids))
    setBomExpanded((prev) => ({ ...prev, [key]: true }))
  } catch (err) {
    console.error('bom_tree children (detail) failed', err)
  }
}


  // Fetch part details
  useEffect(() => {
    let canceled = false
    ;(async () => {
      setLoading(true)
      try {
        const r = await fetch(`/api/part_detail?pn=${encodeURIComponent(pn)}`)
        if (!r.ok) throw new Error(await r.text())
        const j = await r.json()
        if (canceled) return
        setPart(j.part)
        setFiles(j.files || [])
        setChildren(j.children || [])
        setWU(j.whereused || [])
      } catch (e) {
        console.error("part_detail failed", e)
        if (!canceled) {
          setPart(null); setFiles([]); setChildren([]); setWU([])
        }
      } finally {
        if (!canceled) setLoading(false)
      }
    })()
    return () => { canceled = true }
  }, [pn])

  const attrs = useMemo(() => {
    const a = part?.attrs || {}
    // Put some common keys first, the rest sorted
    const order = ["manufacturer", "oem_partnumber", "category", "uom", "weight", "material"]
    const picked: [string, any][] = []
    for (const k of order) if (k in a) picked.push([k, a[k]])
    const rest = Object.entries(a).filter(([k]) => !order.includes(k)).sort(([a],[b]) => a.localeCompare(b))
    return [...picked, ...rest]
  }, [part])

// Load BOM root with thumbnails
useEffect(() => {
   let cancelled = false
   ;(async () => {
     try {
       const r = await fetch(`/api/bom_tree?pn=${encodeURIComponent(pn)}&withThumb=1`)
       if (!r.ok) throw new Error(`HTTP ${r.status}`)
       const root: TreeNode[] = await r.json()
       if (!cancelled) setBomNodes(root)
     } catch (e) {
       console.error('bom_tree root (detail) failed', e)
       if (!cancelled) setBomNodes([])
     }
   })()
   return () => { cancelled = true }
 }, [pn])



  return (
    <div className="p-3">
      <div className="mb-3">
        <h4 className="mb-0">{pn}</h4>
        <div className="text-muted">
          {part?.description || "-"} · {part?.category || "-"} · Rev {part?.revision || "-"} · {part?.uom || "EA"}
        </div>
      </div>

      {/* Images */}
      <ImageStrip pn={pn} rev={part?.revision} />

      {/* Properties */}
      <div className="mb-4">
        <h6 className="mb-2">Properties</h6>
        {attrs.length === 0 ? <div className="text-muted">No attributes.</div> :
          <div style={{display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(260px,1fr))", gap: "8px"}}>
            {attrs.map(([k, v]) => (
              <div key={k} style={{border:"1px solid rgba(0,0,0,.08)", borderRadius:8, padding:"8px"}}>
                <div className="text-muted small">{k}</div>
                <div>{String(v)}</div>
              </div>
            ))}
          </div>}
      </div>

      {/* Files */}
      <div className="mb-4">
        <h6 className="mb-2">Files</h6>
        {files.length === 0 ? <div className="text-muted">No files found.</div> :
          <ul className="list-unstyled">
            {files.map((f, i) => (
              <li key={i} className="mb-1">
                <a href={f.url} target="_blank" rel="noreferrer">
                  {f.rel_path || f.url}
                </a>
                <span className="text-muted small"> · {f.ext_group.toUpperCase()} {f.ext}</span>
              </li>
            ))}
          </ul>}
      </div>

      {/* Children (contains) */}
<div className="mb-4">
  <h6 className="mb-2">BOM</h6>
  <TreeTable
    value={bomNodes}
    expandedKeys={bomExpanded}
    onToggle={(e) => setBomExpanded(e.value)}
    onExpand={onExpandNode}
    scrollable
    scrollHeight="55vh"
    resizableColumns
    size="small"
    showGridlines
  >
    <Column
      header=""
      body={(node) => <ThumbImg urls={node.node.data?.thumb_urls} maxH={32} maxW={48} />}
      style={{ width: 60 }}
    />
    <Column
      field="data.pn"
      header="Part Number"
      sortable
      body={(node) => <a href={`/ui/part/${encodeURIComponent(node.node.data?.pn || '')}`}>{node.node.data?.pn}</a>}
      style={{ width: 240 }}
    />
    <Column field="data.desc" header="Description" sortable />
    <Column field="data.qty" header="Qty" sortable style={{ width: 100 }} />
    <Column field="data.uom" header="UoM" sortable style={{ width: 100 }} />
    <Column field="data.alt_group" header="Alt Group" sortable style={{ width: 140 }} />
  </TreeTable>
</div>


      {/* Where used */}
      <div className="mb-4">
        <h6 className="mb-2">Where-used</h6>
        <DataTable value={wu} size="small" stripedRows responsiveLayout="scroll">
          <Column  header=""
          body={(row) => <ThumbImg urls={row.parent_thumb_urls} maxH={28} maxW={44} />}
          style={{ width: 56 }}/>

          <Column field="parent_pn" header="Parent PN"
                  body={(r: WURow) => <Link to={`/ui/part/${encodeURIComponent(r.parent_pn)}`}>{r.parent_pn}</Link>} sortable />
          <Column field="parent_desc" header="Description" sortable />
          <Column field="qty" header="Qty" sortable />
          <Column field="uom" header="UoM" sortable />
          <Column field="alt_group" header="Alt Group" sortable />
        </DataTable>
      </div>
    </div>
  )
}

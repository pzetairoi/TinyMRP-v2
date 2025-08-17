import { useEffect, useMemo, useState } from "react"
import { useParams, Link } from "react-router-dom"
import { DataTable } from "primereact/datatable"
import { Column } from "primereact/column"
import ImageStrip from "../components/ImageStrip"

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
        <h6 className="mb-2">Contains</h6>
        <DataTable value={children} size="small" stripedRows responsiveLayout="scroll">
          <Column field="child_pn" header="Child PN"
                  body={(r: ChildRow) => <Link to={`/ui/part/${encodeURIComponent(r.child_pn)}`}>{r.child_pn}</Link>} sortable />
          <Column field="child_desc" header="Description" sortable />
          <Column field="qty" header="Qty" sortable />
          <Column field="uom" header="UoM" sortable />
          <Column field="alt_group" header="Alt Group" sortable />
        </DataTable>
      </div>

      {/* Where used */}
      <div className="mb-4">
        <h6 className="mb-2">Where-used</h6>
        <DataTable value={wu} size="small" stripedRows responsiveLayout="scroll">
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

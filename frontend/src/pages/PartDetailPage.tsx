// frontend/src/pages/PartDetailPage.tsx
import { useEffect, useMemo, useState } from "react"
import { useParams, Link } from "react-router-dom"
import { DataTable } from "primereact/datatable"
import { Column } from "primereact/column"
import { TreeTable } from "primereact/treetable"
import type { TreeNode } from "primereact/treenode"
import { TabView, TabPanel } from "primereact/tabview"
import ImageStrip from "../components/ImageStrip"
import ThumbImg from "../components/ThumbImg"
import ProcessBadges from "../components/ProcessBadges"
import "./partdetail.css"

// ---------- Types ----------
type Part = {
  part_number: string
  description: string
  revision?: string
  category?: string
  uom?: string
  attrs: Record<string, any>
}

type FileRow = {
  ext_group: string // pdf|dxf|step|edr|3mf|png|datasheet|qr|thumbnail|others
  ext: string
  rel_path?: string
  size?: number
  mtime?: string
  url: string
  urls: string[]
}

type ChildRow = {
  child_pn: string
  child_desc: string
  qty: number
  uom: string
  alt_group: string
  thumb_urls?: string[]
  material?: string
  finish?: string
}

type WURow = {
  parent_pn: string
  parent_desc: string
  qty: number
  uom: string
  alt_group: string
  parent_thumb_urls?: string[]
}

// ---------- Helpers ----------
const asArr = <T,>(x: any): T[] => (Array.isArray(x) ? (x as T[]) : [])

function pickHero(drawingUrls: string[], images: string[]) {
  // Prefer drawing (_DWG.png), then any plain image
  return drawingUrls[0] || images[0] || ""
}

function groupFiles(files: FileRow[]) {
  const g: Record<string, FileRow[]> = {}
  for (const f of files) {
    const k = (f.ext_group || "others").toLowerCase()
    g[k] ??= []
    g[k].push(f)
  }
  return g
}

// ---------- Check if value has display value ----------
function hasDisplayValue(v: any): boolean {
  if (v === null || v === undefined) return false
  if (typeof v === 'string') return v.trim() !== ''
  if (Array.isArray(v)) return v.length > 0
  if (typeof v === 'object') return Object.keys(v).length > 0
  return true
}


// ---------- Component ----------
export default function PartDetailPage() {
  const route = useParams()
  const pn = route.pn || (window as any).__INITIAL__?.pn || ""

  const [part, setPart] = useState<Part | null>(null)
  const [files, setFiles] = useState<FileRow[]>([])
  const [children, setChildren] = useState<ChildRow[]>([])
  const [wu, setWU] = useState<WURow[]>([])
  const [loading, setLoading] = useState(true)

  // for the right-side Drawing tab + hero image
  const [drawingUrls, setDrawingUrls] = useState<string[]>([])
  const [images, setImages] = useState<string[]>([])

  // BOM Tree
  const [bomNodes, setBomNodes] = useState<TreeNode[]>([])
  const [bomExpanded, setBomExpanded] = useState<Record<string, boolean>>({})

  const pnBody = (n: any) => {
  const leaf = !!n?.leaf
  const pn = n?.data?.pn || ''
  return (
    <span className="tt-pncell">
      {leaf && <span className="tt-leaf-dot" aria-hidden="true" />}
      <a href={`/ui/part/${encodeURIComponent(pn)}`}>{pn}</a>
    </span>
  )
  }


  // ---------- Load Part Detail ----------
  useEffect(() => {
    let canceled = false
    ;(async () => {
      setLoading(true)
      try {
        const r = await fetch(`/api/part_detail?pn=${encodeURIComponent(pn)}`)
        if (!r.ok) throw new Error(await r.text())
        const j = await r.json()

        if (canceled) return

        // j.part, j.files (array), j.children (array), j.whereused (array)
        setPart(
          j.part
            ? {
                part_number: j.part.part_number,
                description: j.part.description,
                revision: j.part.revision || "",
                category: j.part.category || "",
                uom: j.part.uom || "EA",
                attrs: j.part.attributes || j.part.attrs || {}, // accept either key
              }
            : null
        )

        setFiles(asArr<FileRow>(j.files))
        setChildren(asArr<ChildRow>(j.children))
        setWU(asArr<WURow>(j.whereused))

        setDrawingUrls(asArr<string>(j.drawing_urls))
        setImages(asArr<string>(j.images))
      } catch (e) {
        console.error("part_detail failed", e)
        if (!canceled) {
          setPart(null)
          setFiles([])
          setChildren([])
          setWU([])
          setDrawingUrls([])
          setImages([])
        }
      } finally {
        if (!canceled) setLoading(false)
      }
    })()
    return () => {
      canceled = true
    }
  }, [pn])


  // ---------- Process metadata ----------
  type ProcMeta = { color: string; icon: string }
  const [procMeta, setProcMeta] = useState<Record<string, ProcMeta>>({})

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const r = await fetch('/api/process_meta')
        if (r.ok) {
          const m = await r.json()
          if (!cancelled) setProcMeta(m || {})
        }
      } catch {}
    })()
    return () => { cancelled = true }
  }, [])




  // ---------- Load BOM (root) ----------
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const r = await fetch(`/api/bom_tree?pn=${encodeURIComponent(pn)}&withThumb=1`)
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        const root: TreeNode[] = await r.json()
        if (!cancelled) setBomNodes(asArr<TreeNode>(root))
      } catch (e) {
        console.error("bom_tree root (detail) failed", e)
        if (!cancelled) setBomNodes([])
      }
    })()
    return () => {
      cancelled = true
    }
  }, [pn])

  // ---------- Load BOM (lazy children) ----------
  function setNodeChildren(tree: TreeNode[], key: string, kids: TreeNode[]): TreeNode[] {
    return tree.map((n) => {
      if (String(n.key) === String(key)) return { ...n, children: kids }
      if (n.children?.length) return { ...n, children: setNodeChildren(n.children as any, key, kids) }
      return n
    })
  }

  async function onExpandNode(e: any) {
    const key = String(e?.node?.key || "")
    if (!key) return
    try {
      const r = await fetch(`/api/bom_tree?parent=${encodeURIComponent(key)}&withThumb=1`)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const kids: TreeNode[] = asArr(await r.json())
      setBomNodes((prev) => setNodeChildren(prev, key, kids))
      setBomExpanded((prev) => ({ ...prev, [key]: true }))
    } catch (err) {
      console.error("bom_tree children (detail) failed", err)
    }
  }

  // ---------- Derived ----------
  const fileGroups = useMemo(() => groupFiles(files), [files])
  const heroUrl = useMemo(() => pickHero(drawingUrls, images), [drawingUrls, images])

  const attrs = useMemo(() => {
    const raw = (part?.attrs || {}) as Record<string, any>

    // only non-empty
    const allEntries = Object.entries(raw).filter(([, v]) => hasDisplayValue(v))

    // surface some common keys first (only if non-empty)
    const prio = [
      'processes', 'process', 'process2', 'process3',
      'material', 'finish', 'mass', 'category',
      'oem', 'oem_partnumber'
    ]
    const picked: [string, any][] = []
    for (const k of prio) {
      if (k in raw && hasDisplayValue(raw[k])) picked.push([k, raw[k]])
    }

    const rest = allEntries
      .filter(([k]) => !prio.includes(k))
      .sort(([a], [b]) => a.localeCompare(b))

    return [...picked, ...rest]
    }, [part])

    // Processes: normalize and deduplicate
    const processes: string[] = useMemo(() => {
      if (part?.processes && Array.isArray(part.processes)) return part.processes
      const a = part?.attrs || {}
      const tmp = ([] as string[]).concat(
        Array.isArray(a.processes) ? a.processes : [],
        a.process ? [a.process] : [],
        a.process2 ? [a.process2] : [],
        a.process3 ? [a.process3] : [],
      )
      return tmp
        .map(x => String(x || '').trim().toLowerCase())
        .filter((x, i, arr) => x && arr.indexOf(x) === i)
    }, [part])






  // ---------- Render ----------
  return (
    <div className="container-xxl py-3">
      {/* Title */}
      <div className="pb-2 border-bottom mb-3">
        <h4 className="mb-0">
          {pn} {part?.revision ? `· REV ${part.revision}` : ""} {part?.description ? ` – ${part.description}` : ""}
        </h4>
        <div className="text-muted small">{part?.category || ""}</div>
      </div>

      {/* Top zone: Left (hero + quick facts) / Right (tabs) */}
      <div className="row g-3">
        {/* LEFT */}
        <div className="col-lg-4">
          <div className="pd-card">
            <div className="pd-hero">
            <ImageStrip pn={pn} mode="preview" />
            </div>

            {/* quick info */}
            <table className="table table-sm table-borderless mb-2">
              <tbody>
                <tr>
                  <th className="pd-th">Processes:</th>
                  <td>
                                        {processes.length > 0 && (
                      <div className="pd-proc-chips">
                        {processes.map(p => {
                          const m = procMeta[p] || procMeta['others']
                          const bg = m?.color ? `rgb(${m.color})` : 'rgba(0,0,0,.15)'
                          const icon = m?.icon ? `/static/images/${m.icon}` : `/static/images/unknown.svg`
                          return (
                            <span key={p} className="pd-proc-chip" style={{ background: bg }}>
                              <img src={icon} onError={(e: any)=>{e.currentTarget.src='/static/images/unknown.svg'}} />
                              <span>{p}</span>
                            </span>
                          )
                        })}
                      </div>
                    )}

                  </td>
                </tr>
                <tr>
                  <th className="pd-th">Material:</th>
                  <td>{part?.attrs?.material || part?.attrs?.Material || part?.attrs?.MATERIAL || "-"}</td>
                </tr>
                <tr>
                  <th className="pd-th">Finish:</th>
                  <td>{part?.attrs?.finish || "-"}</td>
                </tr>
                <tr>
                  <th className="pd-th">Mass:</th>
                  <td>{part?.attrs?.mass || part?.attrs?.Weight || "-"}</td>
                </tr>
              </tbody>
            </table>

            {/* file buttons */}
            <div className="pd-files d-grid gap-1">
              {/* model-ish */}
              {!!fileGroups.edr?.length && (
                <a className="btn btn-info btn-sm w-100" href={fileGroups.edr[0].url} target="_blank" rel="noreferrer">
                  3D
                </a>
              )}
              {!!fileGroups.step?.length && (
                <a className="btn btn-info btn-sm w-100" href={fileGroups.step[0].url} target="_blank" rel="noreferrer">
                  STEP
                </a>
              )}

              {/* docs */}
              {!!fileGroups.pdf?.length && (
                <a className="btn btn-success btn-sm w-100" href={fileGroups.pdf[0].url} target="_blank" rel="noreferrer">
                  PDF
                </a>
              )}
              {!!fileGroups.dxf?.length && (
                <a className="btn btn-success btn-sm w-100" href={fileGroups.dxf[0].url} target="_blank" rel="noreferrer">
                  DXF
                </a>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT */}
        <div className="col-lg-8">
          <TabView>
            <TabPanel header="Drawing">
              <ImageStrip pn={pn} mode="drawing" />
            </TabPanel>

            <TabPanel header="All attributes">
              {attrs.length === 0 ? (
                <div className="text-muted small">No attributes.</div>
              ) : (
                <div className="pd-attrs-wrap">
                  <div className="pd-attrs-list">
                    {attrs.map(([k, v]) => (
                      <div key={k} className="pd-attr">
                        <div className="pd-attr-k">{k}</div>
                        <div className="pd-attr-v">{String(v)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </TabPanel>

            <TabPanel header="Doc Packs">
              <div className="text-muted small">
                (Hook up to your reporting/binder endpoints later – this is just a placeholder panel.)
              </div>
            </TabPanel>
          </TabView>
        </div>
      </div>

      {/* Used in */}
      <div className="mt-4">
        <h6 className="mb-2">Used in</h6>
        <DataTable value={wu} size="small" stripedRows responsiveLayout="scroll">
          <Column
            header=""
            body={(row) => <ThumbImg urls={row.parent_thumb_urls} maxH={28} maxW={44} />}
            style={{ width: 56 }}
          />
          <Column
            field="parent_pn"
            header="Parent PN"
            sortable
            body={(r: WURow) => <Link to={`/ui/part/${encodeURIComponent(r.parent_pn)}`}>{r.parent_pn}</Link>}
          />
          <Column field="parent_desc" header="Description" sortable />
          <Column field="qty" header="Qty" sortable />
          <Column field="uom" header="UoM" sortable />
          <Column field="alt_group" header="Alt Group" sortable />
        </DataTable>
      </div>

      {/* Components table (Tree) */}
      <div className="mt-4">
        <h6 className="mb-2">Components Table</h6>
        <TreeTable
          value={Array.isArray(bomNodes) ? bomNodes : []}
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
            body={(node: any) => {
              const urls = node?.data?.thumb_urls || []
              return urls.length ? (
                <img
                  src={urls[0]}
                  onError={(ev: any) => urls[1] && (ev.currentTarget.src = urls[1])}
                  style={{ maxHeight: 28, maxWidth: 44, objectFit: "contain" }}
                />
              ) : null
            }}
            style={{ width: 56 }}
          />

          <Column
            field="pn"
            header="Partnumber"
            expander
            sortable
            body={pnBody}
            style={{ width: 240 }}
          />

          <Column field="rev" header="Rev" sortable style={{ width: 90 }} />
          <Column field="desc" header="Description" sortable />
          <Column field="process" header="Process" sortable />
          <Column field="finish" header="Finish" sortable />
          <Column field="material" header="Material" sortable />
          <Column field="qty" header="Level QTY" sortable style={{ width: 110 }} />
        </TreeTable>
      </div>

      {/* Optional: small image strip under everything */}
      <div className="pd-proc-legend">
        {Object.entries(procMeta).map(([k, m]) => (
          <span key={k} className="pd-proc-chip" style={{ background: `rgb(${m.color})` }}>
            <img src={`/static/images/${m.icon}`} onError={(e:any)=>{e.currentTarget.src='/static/images/unknown.svg'}} />
            <span>{k}</span>
          </span>
        ))}
      </div>

    </div>




  )
}

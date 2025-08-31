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
import { FilterMatchMode } from 'primereact/api'

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

// --- TreeTable filters (controlled) ---
type TTFilters = Record<string, { value: any; matchMode: string }>

const makeInitFilters = (): TTFilters => ({
  pn:        { value: null, matchMode: FilterMatchMode.CUSTOM },
  desc:      { value: null, matchMode: FilterMatchMode.CUSTOM },
  rev:       { value: null, matchMode: FilterMatchMode.CUSTOM },
  process:   { value: null, matchMode: FilterMatchMode.CUSTOM },
  finish:    { value: null, matchMode: FilterMatchMode.CUSTOM },
  material:  { value: null, matchMode: FilterMatchMode.CUSTOM },
  qty:       { value: null, matchMode: FilterMatchMode.EQUALS },
});


const [ttFilters, setTtFilters] = useState<TTFilters>(makeInitFilters())

// Remove cleared filters ('' / null) so they don’t “stick”
function normalizeFilters(next: TTFilters): TTFilters {
  const out: TTFilters = { ...makeInitFilters() }
  for (const k of Object.keys(next || {})) {
    const v = next[k]?.value
    if (v !== '' && v !== null && v !== undefined) out[k] = next[k]
  }
  return out
}

function onTTFilter(e: any) {
  // PrimeReact sends e.filters
  setTtFilters(normalizeFilters(e.filters || {}))
}


const [ttKey, setTtKey] = useState(0); // to force remount
function clearTTFilters() {
  setTtFilters(makeInitFilters());
  setTtKey(k => k + 1);     // force remount so inputs clear
}

// Multi-term (space-separated) CONTAINS-ALL, case-insensitive
const containsAllTerms = (value: any, filter: any) => {
  if (filter == null || filter === '') return true;
  const hay = String(value ?? '').toLowerCase();
  const terms = String(filter).toLowerCase().trim().split(/\s+/).filter(Boolean);
  if (!terms.length) return true;
  return terms.every(t => hay.includes(t));
};






// Replace your pnBody with this (no dot here, just the link)
const pnBody = (n: any) => {
  const pn = n?.data?.pn || '';
  return (
    <span className="tt-pncell">
      <a className="tt-pnlink" href={`/ui/part/${encodeURIComponent(pn)}`}>{pn}</a>
    </span>
  );
};

// New: level + thumbnail cell
const levelThumbBody = (node: any) => {
  const depth = Math.max(0, Number(node?.data?._depth ?? 0));
  const levelGlyph = depth > 0 ? '—'.repeat(depth) : ''; // en-dash chain
  const urls: string[] = Array.isArray(node?.data?.thumb_urls) ? node.data.thumb_urls : [];
  const isLeaf = !!node?.leaf || !node?.children?.length;

  return (
    <div className="tt-thumbcell">
      <span className="tt-level">{levelGlyph}</span>
      {isLeaf && !urls.length ? (
        <span className="tt-leaf-dot" aria-hidden="true" />
      ) : null}
      {urls.length ? (
        <img
          src={urls[0]}
          onError={(ev: any) => urls[1] && (ev.currentTarget.src = urls[1])}
          className="tt-thumb"
          alt=""
        />
      ) : null}
    </div>
  );
};


  // ---------- Load Part Detail ----------
  // frontend/src/pages/PartDetailPage.tsx

// ---- Load Part Detail (RESTORE THIS) ----
useEffect(() => {
  let canceled = false
  ;(async () => {
    setLoading(true)
    try {
      const r = await fetch(`/api/part_detail?pn=${encodeURIComponent(pn)}`)
      if (!r.ok) throw new Error(await r.text())
      const j = await r.json()
      if (canceled) return

      setPart(
        j.part
          ? {
              part_number: j.part.part_number,
              description: j.part.description,
              revision: j.part.revision || "",
              category: j.part.category || "",
              uom: j.part.uom || "EA",
              attrs: j.part.attributes || j.part.attrs || {},
            }
          : null
      )
      setFiles(asArr<FileRow>(j.files))
      setChildren(asArr<ChildRow>(j.children))
      setWU(asArr<WURow>(j.whereused))               // <-- this feeds “Used in”
      setDrawingUrls(asArr<string>(j.drawing_urls))
      setImages(asArr<string>(j.images))
    } catch (e) {
      console.error("part_detail failed", e)
      if (!canceled) {
        setPart(null); setFiles([]); setChildren([]); setWU([])
        setDrawingUrls([]); setImages([])
      }
    } finally {
      if (!canceled) setLoading(false)
    }
  })()
  return () => { canceled = true }
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


// ---- BOM: show first-level children as table roots (KEEP this one) ----
useEffect(() => {
  let cancelled = false
  ;(async () => {
    try {
      const r = await fetch(`/api/bom_tree?pn=${encodeURIComponent(pn)}&withThumb=1`)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const root: TreeNode[] = asArr(await r.json())
      if (cancelled) return

      if (!root.length) { setBomNodes([]); setBomExpanded({}); return }

      const rootKey = String(root[0].key ?? root[0].data?.pn ?? pn)
      const r2 = await fetch(`/api/bom_tree?parent=${encodeURIComponent(rootKey)}&withThumb=1`)
      if (!r2.ok) throw new Error(`HTTP ${r2.status}`)
      let kids: TreeNode[] = asArr(await r2.json())

      kids = annotateDepth(kids, 0) // first visible level = depth 0
      if (!cancelled) { setBomNodes(kids); setBomExpanded({}) }
    } catch (e) {
      console.error("bom_tree root (detail) failed", e)
      if (!cancelled) { setBomNodes([]); setBomExpanded({}) }
    }
  })()
  return () => { cancelled = true }
}, [pn])



  // ---------- Load BOM (lazy children) ----------
  function setNodeChildren(tree: TreeNode[], key: string, kids: TreeNode[]): TreeNode[] {
    return tree.map((n) => {
      if (String(n.key) === String(key)) return { ...n, children: kids }
      if (n.children?.length) return { ...n, children: setNodeChildren(n.children as any, key, kids) }
      return n
    })
  }

// find a node by key in current tree (shallow + deep)
  function findNode(tree: TreeNode[], key: string): TreeNode | undefined {
    for (const n of tree) {
      if (String(n.key) === String(key)) return n
      if (n.children?.length) {
        const hit = findNode(n.children as TreeNode[], key)
        if (hit) return hit
      }
    }
    return undefined
  }


async function onExpandNode(e: any) {
  const key = String(e?.node?.key || '')
  if (!key) return
  try {
    const r = await fetch(`/api/bom_tree?parent=${encodeURIComponent(key)}&withThumb=1`)
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    const kids: TreeNode[] = asArr(await r.json())

    // depth tagging for new children
    setBomNodes((prev) => {
      const parentDepth = findNodeDepth(prev, key) ?? 0
      const tagged = annotateDepth(kids, parentDepth + 1)
      return setNodeChildren(prev, key, tagged)
    })
    setBomExpanded((prev) => ({ ...prev, [key]: true }))
  } catch (err) {
    console.error('bom_tree children (detail) failed', err)
  }
}



 // Expand the entire tree (recursively loads all children and expands them)
  async function expandAll() {
    if (!bomNodes.length) return
    const seen = new Set<string>()
    const queue: string[] = bomNodes.map(n => String(n.key))
    let nextTree = bomNodes
    const expanded: Record<string, boolean> = { ...bomExpanded }

    while (queue.length) {
      const key = queue.shift()!
      if (seen.has(key)) continue
      seen.add(key)

      let node = findNode(nextTree, key)
      if (!node) continue

      // If we don't have children yet, try to fetch them
      if (!node.children || (node.children as TreeNode[]).length === 0) {
        try {
          const r = await fetch(`/api/bom_tree?parent=${encodeURIComponent(key)}&withThumb=1`)
          if (r.ok) {
          let kids: TreeNode[] = asArr(await r.json());
          const parentDepth = findNodeDepth(nextTree, key) ?? 0;
          kids = annotateDepth(kids, parentDepth + 1);   // <-- add depth
          if (kids.length) {
            nextTree = setNodeChildren(nextTree, key, kids);
            expanded[key] = true;
            for (const k of kids) queue.push(String(k.key));
          }
          }
        } catch (e) {
          console.warn('expandAll fetch failed for', key, e)
        }
      } else {
        // already have children
        const kids = (node.children as TreeNode[]) || []
        if (kids.length) {
          expanded[key] = true
          for (const k of kids) queue.push(String(k.key))
        }
      }
    }
    setBomNodes(nextTree)
    setBomExpanded(expanded)
  }
  // Expand all once we have the root nodes

// ADD near other helpers
function annotateDepth(nodes: TreeNode[], depth = 0): TreeNode[] {
  return (nodes || []).map((n) => {
    const data = { ...(n.data || {}), _depth: depth };
    const kids = Array.isArray(n.children) ? annotateDepth(n.children as TreeNode[], depth + 1) : n.children;
    return { ...n, data, children: kids };
  });
}

function findNodeDepth(tree: TreeNode[], key: string, current = 0): number | null {
  for (const n of tree || []) {
    if (String(n.key) === String(key)) return (n as any)?.data?._depth ?? current;
    if (n.children && n.children.length) {
      const d = findNodeDepth(n.children as TreeNode[], key, (n as any)?.data?._depth ?? current);
      if (d !== null) return d;
    }
  }
  return null;
}

const rowClassName = (node: any) => {
  const d = Number(node?.data?._depth ?? 0) % 5; // 5-color loop
  return { [`tt-depth-${d}`]: true };
};




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
        
        
        
        
        </div>
      </div>



      {/* Components table (Tree) */}
      <div className="mt-4">
        <div className="d-flex align-items-center justify-content-between mb-2">
          <h6 className="mb-0">BOM</h6>
          <button type="button" className="btn btn-sm btn-outline-secondary" onClick={expandAll}>
            Expand all
          </button>
          <button className="btn btn-sm btn-outline-secondary ms-2" onClick={() => setBomExpanded({})}>
          Collapse all
          </button>
                <button
  type="button"
  className="btn btn-sm btn-outline-secondary"
  onClick={(e) => { e.preventDefault(); clearTTFilters(); }}
>
  Clear filters
</button>

        </div>

// ---- TreeTable ----
<TreeTable
  key={ttKey}                      // <-- ensure inputs reset on “Clear filters”
  className="pd-tt"
  value={bomNodes || []}
  expandedKeys={bomExpanded}
  onToggle={(e) => setBomExpanded(e.value)}
  onExpand={onExpandNode}
  filters={ttFilters}
  onFilter={onTTFilter}
  filterDisplay="row"
  rowClassName={rowClassName}
  showGridlines
  scrollable
  scrollHeight="55vh"
  resizableColumns
  size="small"
>
  <Column expander style={{ width: 38 }} />
  <Column header="" body={levelThumbBody} style={{ width: 120 }} />

  <Column
    field="pn" filterField="pn" header="Partnumber"
    sortable filter filterMatchMode="custom"
    filterFunction={(value, flt) => containsAllTerms(value, flt)}
    showFilterMenu={false} filterPlaceholder="Filter PN"
    body={pnBody} style={{ width: 240, textAlign: 'left' }}
  />
  <Column
    field="rev" filterField="rev" header="Rev"
    sortable filter filterMatchMode="custom"
    filterFunction={(value, flt) => containsAllTerms(value, flt)}
    showFilterMenu={false} filterPlaceholder="Rev"
    style={{ width: 90 }}
  />
  <Column
    field="desc" filterField="desc" header="Description"
    sortable filter filterMatchMode="custom"
    filterFunction={(value, flt) => containsAllTerms(value, flt)}
    showFilterMenu={false} filterPlaceholder="Filter description"
  />
  <Column
    field="process" filterField="process" header="Process"
    sortable filter filterMatchMode="custom"
    filterFunction={(value, flt) => containsAllTerms(value, flt)}
    showFilterMenu={false} filterPlaceholder="Filter process"
  />
  <Column
    field="finish" filterField="finish" header="Finish"
    sortable filter filterMatchMode="custom"
    filterFunction={(value, flt) => containsAllTerms(value, flt)}
    showFilterMenu={false} filterPlaceholder="Filter finish"
  />
  <Column
    field="material" filterField="material" header="Material"
    sortable filter filterMatchMode="custom"
    filterFunction={(value, flt) => containsAllTerms(value, flt)}
    showFilterMenu={false} filterPlaceholder="Filter material"
  />
  <Column
    field="qty" filterField="qty" header="Level QTY"
    sortable filter showFilterMenu={false}
    filterPlaceholder="= Qty" style={{ width: 110 }}
  />
</TreeTable>



      </div>




      {/* Optional: small image strip under everything */}
      <br></br>
      <br></br>
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

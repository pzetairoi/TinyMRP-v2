// frontend/src/pages/PartDetailPage.tsx
import React, { useEffect, useMemo, useState, Suspense } from "react";
import { useParams, Link } from "react-router-dom";
import { DataTable } from "primereact/datatable";
import { Column } from "primereact/column";
import { TreeTable } from "primereact/treetable";
import type { TreeNode } from "primereact/treenode";
import { TabView, TabPanel } from "primereact/tabview";
import ImageStrip from "../components/ImageStrip";
import ThumbImg from "../components/ThumbImg";
import "./partdetail.css";
import { FilterMatchMode } from "primereact/api";

// ---------- Types ----------
type Part = {
  part_number: string;
  description: string;
  revision?: string;
  category?: string;
  uom?: string;
  attrs: Record<string, any>;
};

type FileRow = {
  ext_group?: string;
  group?: string;
  ext?: string;
  rel_path?: string;
  size?: number;
  mtime?: string;
  url?: string;
  http_url?: string;
  urls?: string[];
};

type ChildRow = {
  child_pn: string;
  child_desc: string;
  qty: number;
  uom: string;
  alt_group: string;
  thumb_urls?: string[];
  material?: string;
  finish?: string;
};

type WURow = {
  parent_pn: string;
  parent_desc: string;
  qty: number;
  uom: string;
  alt_group: string;
  parent_thumb_urls?: string[];
  parent_rev?: string;
};

// threeMF viewer (lazy load)
const ThreeMFViewer = React.lazy(() => import("../components/ThreeMFViewer"));

// ---------- Helpers ----------
const asArr = <T,>(x: any): T[] => (Array.isArray(x) ? (x as T[]) : []);

function groupKeyOf(f: FileRow): string {
  const raw = (f.ext_group || f.group || f.ext || "others").toLowerCase();
  if (raw === "eprt" || raw === "edr") return "edr";
  if (raw === "stp" || raw === "step") return "step";
  if (raw === "jpg" || raw === "jpeg" || raw === "png") return "png";
  return raw;
}

// ---------- Check if value has display value ----------
function hasDisplayValue(v: any): boolean {
  if (v === null || v === undefined) return false;
  if (typeof v === "string") return v.trim() !== "";
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === "object") return Object.keys(v).length > 0;
  return true;
}

function groupFiles(files: FileRow[]) {
  const g: Record<string, FileRow[]> = {};
  for (const f of files || []) {
    const k = groupKeyOf(f);
    (g[k] ||= []).push(f);
  }
  return g;
}

// ---------- Component ----------
export default function PartDetailPage() {
  const route = useParams();
  const pn = route.pn || (window as any).__INITIAL__?.pn || "";
  const sp = new URLSearchParams(window.location.search);
  const rev = sp.get("rev") || ((window as any).__INITIAL__?.rev ?? "");

  const [part, setPart] = useState<Part | null>(null);
  const [files, setFiles] = useState<FileRow[]>([]);
  const [children, setChildren] = useState<ChildRow[]>([]);
  const [wu, setWU] = useState<WURow[]>([]);
  const [loading, setLoading] = useState(true);

  // for the right-side Drawing tab + hero image
  const [drawingUrls, setDrawingUrls] = useState<string[]>([]);
  const [images, setImages] = useState<string[]>([]);

  // BOM Tree
  const [bomNodes, setBomNodes] = useState<TreeNode[]>([]);
  const [bomExpanded, setBomExpanded] = useState<Record<string, boolean>>({});
  const [rootKey, setRootKey] = useState<string | null>(null); // <- moved up so helpers can reference it

  // --- TreeTable filters (controlled) ---
  type TTFilters = Record<string, { value: any; matchMode: string }>;

  const makeInitFilters = (): TTFilters => ({
    pn: { value: null, matchMode: FilterMatchMode.CUSTOM },
    desc: { value: null, matchMode: FilterMatchMode.CUSTOM },
    rev: { value: null, matchMode: FilterMatchMode.CUSTOM },
    process: { value: null, matchMode: FilterMatchMode.CUSTOM },
    finish: { value: null, matchMode: FilterMatchMode.CUSTOM },
    material: { value: null, matchMode: FilterMatchMode.CUSTOM },
    qty: { value: null, matchMode: FilterMatchMode.EQUALS },
  });

  const [ttFilters, setTtFilters] = useState<TTFilters>(makeInitFilters());

  // Remove cleared filters ('' / null) so they don’t “stick”
  function normalizeFilters(next: TTFilters): TTFilters {
    const out: TTFilters = { ...makeInitFilters() };
    for (const k of Object.keys(next || {})) {
      const v = next[k]?.value;
      if (v !== "" && v !== null && v !== undefined) out[k] = next[k];
    }
    return out;
  }

  function onTTFilter(e: any) {
    setTtFilters(normalizeFilters(e.filters || {}));
  }

  const [ttKey, setTtKey] = useState(0); // to force remount
  function clearTTFilters() {
    setTtFilters(makeInitFilters());
    setTtKey((k) => k + 1);
  }

  // Multi-term (space-separated) CONTAINS-ALL, case-insensitive
  const containsAllTerms = (value: any, filter: any) => {
    if (filter == null || filter === "") return true;
    const hay = String(value ?? "").toLowerCase();
    const terms = String(filter)
      .toLowerCase()
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    if (!terms.length) return true;
    return terms.every((t) => hay.includes(t));
  };

  // --- helpers that rely on component state (must be inside component) ---
// Prefer rel_path + BASE; avoid absolute http_url to dodge CORS

// in PartDetailPage.tsx (replace your bestUrl)
function bestUrl(f: FileRow): string {
  const base = (import.meta as any).env?.VITE_FILES_BASE_URL || "/extfiles/deliverables";

  // 1) Preferred: rel_path -> same-origin {base}/rel_path
  if (f.rel_path) {
    const rp = String(f.rel_path).replace(/^\/+/, "");
    return `${base}/${rp}`.replace(/([^:]\/)\/+/g, "$1");
  }

  // 2) Rewrite absolute URLs that contain /deliverables/ -> same-origin
  const direct = f.url || f.http_url || (Array.isArray(f.urls) ? f.urls[0] : "");
  if (direct) {
    try {
      const u = new URL(direct, window.location.origin);
      const m = u.pathname.match(/\/deliverables\/(.+)$/);
      if (m) return `${base}/${m[1]}`.replace(/([^:]\/)\/+/g, "$1");
      // allow same-origin direct urls
      if (u.origin === window.location.origin) return u.toString();
    } catch { /* ignore */ }
  }

  // 3) Nothing else
  return "";
}



  function normalizeFileRow(raw: any): FileRow {
    const rel = raw?.rel_path ?? raw?.rel ?? "";

    const urlCandidate =
      raw?.url || raw?.http_url || (Array.isArray(raw?.urls) ? raw.urls[0] : "");

    return {
      ext_group: raw?.ext_group ?? raw?.group,
      group: raw?.group,
      ext: (raw?.ext || "").toLowerCase(),
      rel_path: rel,
      size: raw?.size,
      mtime: raw?.mtime,
      url: raw?.url,
      http_url: raw?.http_url,
      urls: Array.isArray(raw?.urls) ? raw.urls : urlCandidate ? [urlCandidate] : [],
    };
  }

  function getNodeByKey(tree: TreeNode[], key: string): TreeNode | undefined {
    for (const n of tree) {
      if (String(n.key) === String(key)) return n;
      if (n.children?.length) {
        const hit = getNodeByKey(n.children as TreeNode[], key);
        if (hit) return hit;
      }
    }
    return undefined;
  }

  function getChildrenOf(parentKey: string | null): TreeNode[] {
    if (!parentKey || parentKey === rootKey) return bomNodes;
    const p = getNodeByKey(bomNodes, parentKey);
    return (p?.children as TreeNode[]) || [];
  }

  function isLastSibling(nodeKey: string, parentKey: string | null): boolean {
    const sibs = getChildrenOf(parentKey);
    const idx = sibs.findIndex((s) => String(s.key) === String(nodeKey));
    return idx >= 0 && idx === sibs.length - 1;
  }

  function getAncestorChain(node: any): string[] {
    const chain: string[] = [];
    let p: string | null = node?.data?._parent ?? null;
    while (p) {
      chain.unshift(p);
      if (p === rootKey) break;
      const pn = getNodeByKey(bomNodes, p);
      p = (pn?.data?._parent ?? rootKey) as string | null;
    }
    return chain;
  }

  const levelCellBody = (node: any) => {
    const depth = Math.max(0, Number(node?.data?._depth ?? 0));
    const parentKey = node?.data?._parent ?? null;
    const ancestors = getAncestorChain(node);

    // draw vertical lines for ancestors that have a next sibling
    const keepMask = ancestors.map(
      (ak) =>
        !isLastSibling(ak, getNodeByKey(bomNodes, ak)?.data?._parent ?? rootKey)
    );

    const lastHere = isLastSibling(String(node?.key ?? node?.data?.pn ?? ""), parentKey);
    const indent = 16; // px per level
    const totalSlots = Math.max(1, depth + 1);

    return (
      <div className="tt-levelcell" style={{ width: totalSlots * indent }}>
        {Array.from({ length: depth }).map((_, i) => (
          <span key={`v-${i}`} className={`tt-lvl ${keepMask[i] ? "keep" : ""}`} />
        ))}
        <span className={`tt-lvl cap ${lastHere ? "last" : "mid"}`} />
      </div>
    );
  };

  const thumbOnlyBody = (node: any) => {
    const urls: string[] = Array.isArray(node?.data?.thumb_urls)
      ? node.data.thumb_urls
      : [];
    return urls.length ? (
      <img
        src={urls[0]}
        onError={(ev: any) => urls[1] && (ev.currentTarget.src = urls[1])}
        className="tt-thumb"
        alt=""
      />
    ) : null;
  };

  const pnBody = (n: any) => {
    const pn = n?.data?.pn || "";
    return (
      <span className="tt-pncell">
        <a className="tt-pnlink" href={`/ui/part/${encodeURIComponent(pn)}?rev=${encodeURIComponent(n?.data?.rev || "")}`}>
          {pn}
        </a>
      </span>
    );
  };

  // ---- Load Part Detail ----
  useEffect(() => {
    let canceled = false;
    (async () => {
      setLoading(true);
      try {
        const r = await fetch(`/api/part_detail?pn=${encodeURIComponent(pn)}&rev=${encodeURIComponent(rev || "")}`);
        if (!r.ok) throw new Error(await r.text());
        const j = await r.json();
        if (canceled) return;

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
        );

        // --- files: handle both array and grouped object ---
        const arrFiles: FileRow[] = [];
        const src = j.files || j.part_files || j.artifacts || j.file_rows || [];

        // case A: already an array
        if (Array.isArray(src)) {
          arrFiles.push(...src.map(normalizeFileRow));
        }
        // case B: grouped object { pdf: [...], dxf: [...], ... }
        else if (src && typeof src === "object") {
          for (const [grp, list] of Object.entries(src)) {
            const items = Array.isArray(list) ? list : [];
            for (const item of items) {
              arrFiles.push(
                normalizeFileRow({
                  ...item,
                  ext_group: grp,
                  group: grp,
                  // backend uses "rel", unify to rel_path for our fallback
                  rel_path: (item as any)?.rel ?? (item as any)?.rel_path,
                })
              );
            }
          }
        }

        setFiles(arrFiles);

        setChildren(asArr<ChildRow>(j.children));
        setWU(asArr<WURow>(j.whereused));
        setDrawingUrls(asArr<string>(j.drawing_urls));
        setImages(asArr<string>(j.images));
      } catch (e) {
        console.error("part_detail failed", e);
        if (!canceled) {
          setPart(null);
          setFiles([]);
          setChildren([]);
          setWU([]);
          setDrawingUrls([]);
          setImages([]);
        }
      } finally {
        if (!canceled) setLoading(false);
      }
    })();
    return () => {
      canceled = true;
    };
  }, [pn, rev]);

  // ---------- Process metadata ----------
  type ProcMeta = { color: string; icon: string };
  const [procMeta, setProcMeta] = useState<Record<string, ProcMeta>>({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch("/api/process_meta");
        if (r.ok) {
          const m = await r.json();
          if (!cancelled) setProcMeta(m || {});
        }
      } catch {}
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // ---- BOM: show first-level children as table roots ----
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(
          `/api/bom_tree?pn=${encodeURIComponent(pn)}&rev=${encodeURIComponent(rev || "")}&withThumb=1`
        );
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const root: TreeNode[] = asArr(await r.json());
        if (cancelled) return;
        if (!root.length) {
          setBomNodes([]);
          setBomExpanded({});
          setRootKey(null);
          return;
        }

        const rk = String(root[0].key ?? root[0].data?.pn ?? pn);
        const rootRev = (root[0] as any)?.data?.rev || "";
        setRootKey(rk);

        const r2 = await fetch(
          `/api/bom_tree?parent=${encodeURIComponent(rk)}&parent_rev=${encodeURIComponent(rootRev)}&withThumb=1`
        );
        if (!r2.ok) throw new Error(`HTTP ${r2.status}`);
        let kids: TreeNode[] = asArr(await r2.json());

        kids = annotateDepth(kids, 0, rk); // depth 0 for first visible level, parent=rootKey
        if (!cancelled) {
          setBomNodes(kids);
          setBomExpanded({});
        }
      } catch (e) {
        console.error("bom_tree root (detail) failed", e);
        if (!cancelled) {
          setBomNodes([]);
          setBomExpanded({});
          setRootKey(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pn, rev]);

  // ---------- Load BOM (lazy children) ----------
  function setNodeChildren(
    tree: TreeNode[],
    key: string,
    kids: TreeNode[]
  ): TreeNode[] {
    return tree.map((n) => {
      if (String(n.key) === String(key)) return { ...n, children: kids };
      if (n.children?.length)
        return {
          ...n,
          children: setNodeChildren(n.children as any, key, kids),
        };
      return n;
    });
  }

  function findNode(tree: TreeNode[], key: string): TreeNode | undefined {
    for (const n of tree) {
      if (String(n.key) === String(key)) return n;
      if (n.children?.length) {
        const hit = findNode(n.children as TreeNode[], key);
        if (hit) return hit;
      }
    }
    return undefined;
  }

  async function onExpandNode(e: any) {
    const key = String(e?.node?.key || "");
    if (!key) return;
    try {
      const parentNode = findNode(bomNodes, key);
      const parentRev = (parentNode as any)?.data?.rev || "";
      const r = await fetch(
        `/api/bom_tree?parent=${encodeURIComponent(key)}&parent_rev=${encodeURIComponent(parentRev)}&withThumb=1`
      );
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      let kids: TreeNode[] = asArr(await r.json());

      setBomNodes((prev) => {
        const parentDepth = findNodeDepth(prev, key) ?? 0;
        const tagged = annotateDepth(kids, parentDepth + 1, key);
        return setNodeChildren(prev, key, tagged);
      });
      setBomExpanded((prev) => ({ ...prev, [key]: true }));
    } catch (err) {
      console.error("bom_tree children (detail) failed", err);
    }
  }

  // Expand the entire tree (recursively loads all children and expands them)
  async function expandAll() {
    if (!bomNodes.length) return;
    const seen = new Set<string>();
    const queue: string[] = bomNodes.map((n) => String(n.key));
    let nextTree = bomNodes;
    const expanded: Record<string, boolean> = { ...bomExpanded };

    while (queue.length) {
      const key = queue.shift()!;
      if (seen.has(key)) continue;
      seen.add(key);

      let node = findNode(nextTree, key);
      if (!node) continue;

      // If we don't have children yet, try to fetch them
      if (!node.children || (node.children as TreeNode[]).length === 0) {
        try {
          const parentNode2 = findNode(nextTree, key);
          const parentRev2 = (parentNode2 as any)?.data?.rev || "";
          const r = await fetch(
            `/api/bom_tree?parent=${encodeURIComponent(key)}&parent_rev=${encodeURIComponent(parentRev2)}&withThumb=1`
          );
          if (r.ok) {
            let kids: TreeNode[] = asArr(await r.json());
            const parentDepth = findNodeDepth(nextTree, key) ?? 0;
            kids = annotateDepth(kids, parentDepth + 1, key);
            if (kids.length) {
              nextTree = setNodeChildren(nextTree, key, kids);
              expanded[key] = true;
              for (const k of kids) queue.push(String(k.key));
            }
          }
        } catch (e) {
          console.warn("expandAll fetch failed for", key, e);
        }
      } else {
        // already have children
        const kids = (node.children as TreeNode[]) || [];
        if (kids.length) {
          expanded[key] = true;
          for (const k of kids) queue.push(String(k.key));
        }
      }
    }
    setBomNodes(nextTree);
    setBomExpanded(expanded);
  }

  // annotate depth + parent
  function annotateDepth(
    nodes: TreeNode[],
    depth = 0,
    parentKey: string | null = null
  ): TreeNode[] {
    return (nodes || []).map((n) => {
      const data = { ...(n.data || {}), _depth: depth, _parent: parentKey };
      const kids = Array.isArray(n.children)
        ? annotateDepth(
            n.children as TreeNode[],
            depth + 1,
            String(n.key ?? (data as any)?.pn ?? "")
          )
        : n.children;
      return { ...n, data, children: kids };
    });
  }

  function findNodeDepth(
    tree: TreeNode[],
    key: string,
    current = 0
  ): number | null {
    for (const n of tree || []) {
      if (String(n.key) === String(key))
        return (n as any)?.data?._depth ?? current;
      if (n.children && n.children.length) {
        const d = findNodeDepth(
          n.children as TreeNode[],
          key,
          (n as any)?.data?._depth ?? current
        );
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
  const fileGroups = useMemo(() => groupFiles(files), [files]);

  const firstLinks = useMemo(() => {
    const pick = (k: string) => {
      const arr = fileGroups[k] || [];
      const href = arr.length ? bestUrl(arr[0]) : "";
      return href ? { href, count: arr.length } : null;
    };
    return {
      edr: pick("edr"),
      step: pick("step"),
      pdf: pick("pdf"),
      dxf: pick("dxf"),
      datasheet: pick("datasheet"),
      threeMF: pick("3mf"),
    };
  }, [fileGroups]);

  const pdfHref = firstLinks.pdf?.href || "";

  // 3D: find first 3MF
  const threeMfUrl: string | null = useMemo(() => {
    const arr = fileGroups["3mf"] || [];
    if (!arr.length) return null;
    const href = bestUrl(arr[0]);
    return href || null;
  }, [fileGroups]);

  const attrs = useMemo(() => {
    const raw = (part?.attrs || {}) as Record<string, any>;

    // only non-empty
    const allEntries = Object.entries(raw).filter(([, v]) => hasDisplayValue(v));

    // surface some common keys first (only if non-empty)
    const prio = [
      "processes",
      "process",
      "process2",
      "process3",
      "material",
      "finish",
      "mass",
      "category",
      "oem",
      "oem_partnumber",
    ];
    const picked: [string, any][] = [];
    for (const k of prio) {
      if (k in raw && hasDisplayValue(raw[k])) picked.push([k, raw[k]]);
    }

    const rest = allEntries
      .filter(([k]) => !prio.includes(k))
      .sort(([a], [b]) => a.localeCompare(b));

    return [...picked, ...rest];
  }, [part]);

  // Processes: normalize and deduplicate
  const processes: string[] = useMemo(() => {
    if (part?.processes && Array.isArray(part.processes)) return part.processes;
    const a = part?.attrs || {};
    const tmp = ([] as string[]).concat(
      Array.isArray(a.processes) ? a.processes : [],
      a.process ? [a.process] : [],
      a.process2 ? [a.process2] : [],
      a.process3 ? [a.process3] : []
    );
    return tmp
      .map((x) => String(x || "").trim().toLowerCase())
      .filter((x, i, arr) => x && arr.indexOf(x) === i);
  }, [part]);

  const isPurchased = useMemo(() => {
    const a = part?.attrs || {}
    return processes.includes('purchase') || Boolean(a.oem || a.oem_partnumber)
  }, [processes, part])

  // ---------- Render ----------
  const [tabIndex, setTabIndex] = useState(0)
  // If there is no drawing preview image but there is a PDF, we still
  // consider that we have a drawing. Otherwise, hide the Drawing tab and
  // default to All attributes.
  const hasDrawing = Boolean(pdfHref) || (drawingUrls?.length || 0) > 0

  return (
    <div className="container-xxl py-3">
      {/* Title */}
      <div className="pb-2 border-bottom mb-3">
        <h4 className="mb-0">
          {pn} {part?.revision ? `· REV ${part.revision}` : ""}{" "}
          {part?.description ? ` – ${part.description}` : ""}
        </h4>
        <div className="text-muted small">{part?.category || ""}</div>
      </div>

      {/* Top zone: Left (hero + quick facts) / Right (tabs) */}
      <div className="row g-3">
        {/* LEFT */}
        <div className="col-lg-4">
            <div className="pd-card">
            <div className="pd-hero">
              <ImageStrip pn={pn} rev={rev || ""} mode="preview" limit={1} fit />
            </div>

            {/* quick info */}
            <table className="table table-sm table-borderless mb-2">
              <tbody>
                <tr>
                  <th className="pd-th">Processes:</th>
                  <td>
                    {processes.length > 0 && (
                      <div className="pd-proc-chips">
                        {processes.map((p) => {
                          const m = procMeta[p] || procMeta["others"];
                          const bg = m?.color ? `rgb(${m.color})` : "rgba(0,0,0,.15)";
                          const icon = m?.icon
                            ? `/static/images/${m.icon}`
                            : `/static/images/unknown.svg`;
                          return (
                            <span key={p} className="pd-proc-chip" style={{ background: bg }}>
                              <img
                                src={icon}
                                onError={(e: any) => {
                                  e.currentTarget.src = "/static/images/unknown.svg";
                                }}
                              />
                              <span>{p}</span>
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </td>
                </tr>
                {isPurchased && (
                  <tr>
                    <th className="pd-th">OEM:</th>
                    <td>
                      {(part?.attrs?.oem || '-')}
                      {part?.attrs?.oem_partnumber ? ` · ${part?.attrs?.oem_partnumber}` : ''}
                    </td>
                  </tr>
                )}
                <tr>
                  <th className="pd-th">Material:</th>
                  <td>
                    {part?.attrs?.material ||
                      part?.attrs?.Material ||
                      part?.attrs?.MATERIAL ||
                      "-"}
                  </td>
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

            {/* file buttons + external link */}
            <div className="pd-files mt-2">
              {(() => {
                const href = (part?.attrs?.link || part?.attrs?.oem_internet || '').toString().trim()
                return href ? (
                  <a className="btn btn-outline-primary btn-sm pd-file-btn" href={href} target="_blank" rel="noreferrer">
                    Link
                  </a>
                ) : null
              })()}
              {firstLinks.edr && (
                <a
                  className="btn btn-info btn-sm pd-file-btn"
                  href={firstLinks.edr.href}
                  target="_blank"
                  rel="noreferrer"
                >
                  3D{firstLinks.edr.count > 1 ? ` (${firstLinks.edr.count})` : ""}
                </a>
              )}
              {firstLinks.step && (
                <a
                  className="btn btn-info btn-sm pd-file-btn"
                  href={firstLinks.step.href}
                  target="_blank"
                  rel="noreferrer"
                >
                  STEP{firstLinks.step.count > 1 ? ` (${firstLinks.step.count})` : ""}
                </a>
              )}
              {firstLinks.pdf && (
                <a
                  className="btn btn-success btn-sm pd-file-btn"
                  href={firstLinks.pdf.href}
                  target="_blank"
                  rel="noreferrer"
                >
                  PDF{firstLinks.pdf.count > 1 ? ` (${firstLinks.pdf.count})` : ""}
                </a>
              )}
              {firstLinks.dxf && (
                <a
                  className="btn btn-success btn-sm pd-file-btn"
                  href={firstLinks.dxf.href}
                  target="_blank"
                  rel="noreferrer"
                >
                  DXF{firstLinks.dxf.count > 1 ? ` (${firstLinks.dxf.count})` : ""}
                </a>
              )}
              {firstLinks.datasheet && (
                <a
                  className="btn btn-outline-secondary btn-sm pd-file-btn"
                  href={firstLinks.datasheet.href}
                  target="_blank"
                  rel="noreferrer"
                >
                  Datasheet
                  {firstLinks.datasheet.count > 1
                    ? ` (${firstLinks.datasheet.count})`
                    : ""}
                </a>
              )}
              {firstLinks.threeMF && (
                <a
                  className="btn btn-outline-secondary btn-sm pd-file-btn"
                  href={firstLinks.threeMF.href}
                  target="_blank"
                  rel="noreferrer"
                >
                  3MF
                  {firstLinks.threeMF.count > 1 ? ` (${firstLinks.threeMF.count})` : ""}
                </a>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT */}
        <div className="col-lg-8 pd-right-wrap">
          <div className="pd-right-top">
          <TabView activeIndex={tabIndex} onTabChange={(e: any) => setTabIndex(e.index)}>
            

            {hasDrawing && (
            <TabPanel header="Drawing">
              {pdfHref ? (
                <>
                  <a
                    href={pdfHref}
                    target="_blank"
                    rel="noreferrer"
                    className="pd-drawing-link"
                    title="Open PDF drawing"
                  >
                    <ImageStrip pn={pn} rev={rev || ""} mode="drawing" limit={1} fit />
                  </a>
                </>
              ) : (
                <div className="pd-drawing-link">
                  <ImageStrip pn={pn} rev={rev || ""} mode="drawing" limit={1} fit />
                </div>
              )}
            </TabPanel>
            )}
            

            

            {/* NEW: 3D Preview tab using 3MF */}
            {/* 3D moved to end */} {false && (<TabPanel header="3D Preview">
              {threeMfUrl ? (
                <Suspense fallback={<div className="p-3">Loading 3D viewer…</div>}>
                  <ThreeMFViewer url={threeMfUrl} height={520} />
                </Suspense>
              ) : (
                <div className="p-3 text-muted">No 3D file found for this part (3MF).</div>
              )}
            </TabPanel>)}

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

            {/* 3D Preview tab at the end */}
            <TabPanel header="3D Preview">
              {threeMfUrl ? (
                <Suspense fallback={<div className="p-3">Loading 3D viewer...</div>}>
                  <ThreeMFViewer url={threeMfUrl} height={520} />
                </Suspense>
              ) : (
                <div className="p-3 text-muted">No 3D file found for this part (3MF).</div>
              )}
            </TabPanel>

            
            <TabPanel header="Doc Packs">
              <div className="text-muted small">
                (Hook up to your reporting/binder endpoints later – this is just a placeholder panel.)
              </div>
            </TabPanel>
          </TabView>
          </div>

          {/* Used in (always visible under tabs) */}
          <div className="pd-usedin pd-card">
            <h6 className="mb-2">Used in</h6>
            <DataTable value={wu} size="small" stripedRows responsiveLayout="scroll">
              <Column
                header=""
                body={(row: WURow) => <ThumbImg urls={row.parent_thumb_urls} maxH={28} maxW={44} />}
                style={{ width: 56 }}
              />
              <Column
                field="parent_pn"
                header="Parent PN"
                sortable
                body={(r: WURow) => (
                  <Link to={`/ui/part/${encodeURIComponent(r.parent_pn)}?rev=${encodeURIComponent(r.parent_rev || "")}`}>{r.parent_pn}</Link>
                )}
              />
              <Column field="parent_rev" header="Rev" sortable style={{ width: 100 }} />
              <Column field="parent_desc" header="Description" sortable />
              <Column field="qty" header="Qty" sortable style={{ width: 100 }} />
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
          <button
            className="btn btn-sm btn-outline-secondary ms-2"
            onClick={() => setBomExpanded({})}
          >
            Collapse all
          </button>
          <button
            type="button"
            className="btn btn-sm btn-outline-secondary"
            onClick={(e) => {
              e.preventDefault();
              clearTTFilters();
            }}
          >
            Clear filters
          </button>
        </div>

        {/*  ---- TreeTable ----  */}
        <TreeTable
          key={ttKey}
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
          {/* 1) Level guides (dynamic width) */}
          <Column header="" body={levelCellBody} style={{ width: "auto", padding: 0 }} />

          {/* 2) Expander (arrow only on expandable rows) */}
          <Column
            expander
            className="tt-expander"
            bodyClassName="tt-expander"
            headerClassName="tt-expander"
            style={{ width: 24, minWidth: 24, maxWidth: 24 }}
          />

          {/* 3) Image preview ONLY */}
          <Column header="" body={thumbOnlyBody} style={{ width: 64 }} />

          {/* 4) PN (left aligned) */}
          <Column
            field="pn"
            filterField="pn"
            header="Partnumber"
            sortable
            filter
            filterMatchMode="custom"
            filterFunction={(value, flt) => containsAllTerms(value, flt)}
            showFilterMenu={false}
            filterPlaceholder="Filter PN"
            body={pnBody}
            style={{ width: 240, textAlign: "left" }}
          />

          <Column
            field="rev"
            filterField="rev"
            header="Rev"
            sortable
            filter
            filterMatchMode="custom"
            filterFunction={(value, flt) => containsAllTerms(value, flt)}
            showFilterMenu={false}
            filterPlaceholder="Rev"
            style={{ width: 90 }}
          />
          <Column
            field="desc"
            filterField="desc"
            header="Description"
            sortable
            filter
            filterMatchMode="custom"
            filterFunction={(value, flt) => containsAllTerms(value, flt)}
            showFilterMenu={false}
            filterPlaceholder="Filter description"
          />
          <Column
            field="process"
            filterField="process"
            header="Process"
            sortable
            filter
            filterMatchMode="custom"
            filterFunction={(value, flt) => containsAllTerms(value, flt)}
            showFilterMenu={false}
            filterPlaceholder="Filter process"
          />
          <Column
            field="finish"
            filterField="finish"
            header="Finish"
            sortable
            filter
            filterMatchMode="custom"
            filterFunction={(value, flt) => containsAllTerms(value, flt)}
            showFilterMenu={false}
            filterPlaceholder="Filter finish"
          />
          <Column
            field="material"
            filterField="material"
            header="Material"
            sortable
            filter
            filterMatchMode="custom"
            filterFunction={(value, flt) => containsAllTerms(value, flt)}
            showFilterMenu={false}
            filterPlaceholder="Filter material"
          />
          <Column
            field="qty"
            filterField="qty"
            header="Level QTY"
            sortable
            filter
            showFilterMenu={false}
            filterPlaceholder="= Qty"
            style={{ width: 110 }}
          />
        </TreeTable>
      </div>

      {/* Optional: small image strip under everything */}
      <br />
      <br />
      <div className="pd-proc-legend">
        {Object.entries(procMeta).map(([k, m]) => (
          <span key={k} className="pd-proc-chip" style={{ background: `rgb(${m.color})` }}>
            <img
              src={`/static/images/${m.icon}`}
              onError={(e: any) => {
                e.currentTarget.src = "/static/images/unknown.svg";
              }}
            />
            <span>{k}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

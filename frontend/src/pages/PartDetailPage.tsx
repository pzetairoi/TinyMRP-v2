// frontend/src/pages/PartDetailPage.tsx
import React, { useEffect, useMemo, useState, Suspense, useRef } from "react";
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
  processes?: string[];
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
  name?: string;
};

type PreviewFormat = "3mf" | "ply" | "stl";

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

type VersionRow = {
  id?: string;
  part_number: string;
  revision: string;
  description: string;
  thumb_urls?: string[];
};

type JobsOrdersRow = {
  row_key?: string;
  source: "job" | "order";
  job_id?: string;
  job_number?: string;
  order_id?: string;
  order_number?: string;
  order_kind?: string;
  order_status?: string;
  immediate_pn: string;
  immediate_rev?: string;
  immediate_desc?: string;
  top_pn: string;
  top_rev?: string;
  top_desc?: string;
};

type CommentRow = {
  ts: string;
  author: string;
  text: string;
};

type ExtraFileRow = {
  id?: string;
  pn?: string;
  rev?: string;
  original_name?: string;
  label?: string;
  size?: number;
  mime?: string;
  uploaded_by?: string;
  uploaded_at?: string;
  url?: string;
  rel_path?: string;
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

function formatBytes(value?: number): string {
  const num = Number(value || 0);
  if (!num) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let n = num;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i += 1;
  }
  return `${n.toFixed(n >= 10 ? 0 : 1)} ${units[i]}`;
}

// ---------- Component ----------
export default function PartDetailPage() {
  const route = useParams();
  const pn = route.pn || (window as any).__INITIAL__?.pn || "";
  const sp = new URLSearchParams(window.location.search);
  const rev = sp.get("rev") || ((window as any).__INITIAL__?.rev ?? "");

  const [part, setPart] = useState<Part | null>(null);
  const [files, setFiles] = useState<FileRow[]>([]);
  const [extraFiles, setExtraFiles] = useState<ExtraFileRow[]>([]);
  const [extraLoading, setExtraLoading] = useState(false);
  const [extraError, setExtraError] = useState<string | null>(null);
  const [extraUploadBusy, setExtraUploadBusy] = useState(false);
  const [extraUploadError, setExtraUploadError] = useState<string | null>(null);
  const [extraDeleteBusy, setExtraDeleteBusy] = useState<string | null>(null);
  const [children, setChildren] = useState<ChildRow[]>([]);
  const [wu, setWU] = useState<WURow[]>([]);
  const [versions, setVersions] = useState<VersionRow[]>([]);
  const [jobsOrders, setJobsOrders] = useState<JobsOrdersRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [canJobsManage, setCanJobsManage] = useState(false);
  const [canOrdersManage, setCanOrdersManage] = useState(false);
  const [canPartsDelete, setCanPartsDelete] = useState(false);
  const [canPartsNote, setCanPartsNote] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [refreshBusy, setRefreshBusy] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [refreshMsg, setRefreshMsg] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const [canPartsEdit, setCanPartsEdit] = useState(false);
  const insightsLoading = false;
  const [notes, setNotes] = useState("");
  const [comments, setComments] = useState<CommentRow[]>([]);
  const [notesSaving, setNotesSaving] = useState(false);
  const [notesError, setNotesError] = useState<string | null>(null);
  const [commentText, setCommentText] = useState("");
  const [commentSaving, setCommentSaving] = useState(false);
  const [commentError, setCommentError] = useState<string | null>(null);

  // for the right-side Drawing tab + hero image
  const [drawingUrls, setDrawingUrls] = useState<string[]>([]);
  const [images, setImages] = useState<string[]>([]);
  const [selectedPreviewKey, setSelectedPreviewKey] = useState<string>("");

  // Doc Packs state
  type DocOpts = { file_types: string[]; processes: string[] };
  const [docOpts, setDocOpts] = useState<DocOpts>({ file_types: [], processes: [] });
  const [docLoading, setDocLoading] = useState(false);
  const [docProgress, setDocProgress] = useState(0);
  const progressTimer = useRef<number | null>(null);
  const extraFileInputRef = useRef<HTMLInputElement | null>(null);
  const [depth, setDepth] = useState<'top'|'full'>('full');
  const [classified, setClassified] = useState<'hide'|'show'|'only'>('show');
  const [processMode, setProcessMode] = useState<'all'|'selected'>('all');
  const [selProcesses, setSelProcesses] = useState<Set<string>>(new Set());
  const [selTypes, setSelTypes] = useState<Set<string>>(new Set());
  const [wantSelectedFiles, setWantSelectedFiles] = useState(false);
  const [wantExcel, setWantExcel] = useState(false);
  const [excelAllFields, setExcelAllFields] = useState(false);
  const [wantBinder, setWantBinder] = useState(false);
  const [wantIndex, setWantIndex] = useState(false);
  const [wantVisual, setWantVisual] = useState(false);
  const [wantCoverPage, setWantCoverPage] = useState(false);
  const [wantWhereusedReport, setWantWhereusedReport] = useState(false);
  const [wantHardwareSummary, setWantHardwareSummary] = useState(false);
  const [binderAddCover, setBinderAddCover] = useState(true);
  const [binderAddVisualList, setBinderAddVisualList] = useState(true);
  const [binderAddWhereused, setBinderAddWhereused] = useState(false);
  const [binderAddIndex, setBinderAddIndex] = useState(true);
  const [binderAddDatasheets, setBinderAddDatasheets] = useState(false);
  const [binderAddHardwareSummary, setBinderAddHardwareSummary] = useState(true);
  const [binderPageNumbers, setBinderPageNumbers] = useState(true);
  const [binderIncludeFlatPatterns, setBinderIncludeFlatPatterns] = useState(false);
  const [stampQuote, setStampQuote] = useState(false);
  const [stampConfidential, setStampConfidential] = useState(false);
  const [stampApproved, setStampApproved] = useState(false);
  const [stampWip, setStampWip] = useState(false);
  const [stampInprog, setStampInprog] = useState(false);
  const [outputName, setOutputName] = useState("");
  const [includeConsumed, setIncludeConsumed] = useState(false); // Hide consumed by default
  const [fabricationPack, setFabricationPack] = useState(false);

  // BOM Tree
  const [bomNodes, setBomNodes] = useState<TreeNode[]>([]);
  const [bomExpanded, setBomExpanded] = useState<Record<string, boolean>>({});
  const [rootKey, setRootKey] = useState<string | null>(null); // <- moved up so helpers can reference it

  const effectiveRev = (part?.revision ?? rev ?? "").trim();
  const revToken = effectiveRev ? effectiveRev : "__no_rev__";

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
  const runtimeBase = (window as any).__FILES_BASE_URL as string | undefined;
  const base = runtimeBase || (import.meta as any).env?.VITE_FILES_BASE_URL || "";

  // 1) Prefer explicit URLs returned by the API (tokenized or same-origin)
  const direct = f.url || f.http_url || (Array.isArray(f.urls) ? f.urls[0] : "");
  if (direct) {
    try {
      const u = new URL(direct, window.location.origin);
      if (u.origin === window.location.origin) return u.toString();
    } catch {
      if (direct.startsWith("/")) return direct;
    }
  }

  // 2) Fallback: rel_path -> same-origin {base}/rel_path (only if base is provided)
  if (base && f.rel_path) {
    const rp = String(f.rel_path).replace(/^\/+/, "");
    return `${base}/${rp}`.replace(/([^:]\/)\/+/g, "$1");
  }

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
      name: raw?.name ?? "",
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
    return <ThumbImg urls={urls} maxH={32} maxW={48} />;
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
      setRefreshMsg(null);
      setRefreshError(null);
      try {
        const r = await fetch(`/api/part_detail?pn=${encodeURIComponent(pn)}&rev=${encodeURIComponent(rev || "")}`);
        if (r.status === 403) { if (!canceled) { setForbidden(true); } return; }
        if (!r.ok) throw new Error(await r.text());
        const j = await r.json();
        if (canceled) return;

        const partAttrs = j.part?.attributes || j.part?.attrs || {};
        setPart(
          j.part
            ? {
                part_number: j.part.part_number,
                description: j.part.description,
                revision: j.part.revision || "",
                category: j.part.category || "",
                uom: j.part.uom || "EA",
                processes: Array.isArray(j.part.processes) ? j.part.processes : [],
                attrs: partAttrs,
              }
            : null
        );
        setNotes(String(partAttrs?.notes || ""));
        setComments(Array.isArray(partAttrs?.comments) ? partAttrs.comments : []);

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
        setVersions(asArr<VersionRow>(j.other_versions));
        setJobsOrders(asArr<JobsOrdersRow>(j.jobs_orders));
        setCanJobsManage(!!j.can_jobs_manage);
        setCanOrdersManage(!!j.can_orders_manage);
        setCanPartsDelete(!!j.can_parts_delete);
        setCanPartsEdit(!!j.can_parts_edit);
        setCanPartsNote(j.can_parts_note !== undefined ? !!j.can_parts_note : !!j.can_parts_edit);
      } catch (e) {
        console.error("part_detail failed", e);
          if (!canceled) {
            setPart(null);
            setFiles([]);
            setChildren([]);
            setWU([]);
            setDrawingUrls([]);
            setImages([]);
            setJobsOrders([]);
            setNotes("");
            setComments([]);
            setCanPartsEdit(false);
            setCanPartsNote(false);
          }
      } finally {
        if (!canceled) setLoading(false);
      }
    })();
    return () => {
      canceled = true;
    };
  }, [pn, rev, refreshTick]);

  async function loadExtraFiles() {
    if (!pn) return;
    setExtraLoading(true);
    setExtraError(null);
    try {
      const resp = await fetch(
        `/api/parts/${encodeURIComponent(pn)}/${encodeURIComponent(revToken)}/extra`
      );
      if (resp.status === 403) {
        setExtraFiles([]);
        setExtraError("Forbidden");
        return;
      }
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();
      const rows = Array.isArray(data) ? data : data?.files || [];
      setExtraFiles(rows);
    } catch (err: any) {
      setExtraFiles([]);
      setExtraError(err?.message || "Failed to load associated files.");
    } finally {
      setExtraLoading(false);
    }
  }

  useEffect(() => {
    loadExtraFiles();
  }, [pn, revToken, refreshTick]);

  // Load DocPack options when pn/rev/depth changes
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`/api/docpacks/options?pn=${encodeURIComponent(pn)}&rev=${encodeURIComponent(rev || "")}&depth=${depth}`);
        if (r.status === 403) { if (!cancelled) setForbidden(true); return; }
        if (!r.ok) return;
        const j = await r.json();
        if (cancelled) return;
        const file_types = Array.isArray(j.file_types) ? j.file_types : [];
        const processes = Array.isArray(j.processes) ? j.processes : [];
        setDocOpts({ file_types, processes });
        if (selTypes.size === 0 && file_types.length) setSelTypes(new Set(file_types));
        if (selProcesses.size === 0 && processes.length) setSelProcesses(new Set(processes));
      } catch {}
    })();
    return () => { cancelled = true };
  }, [pn, rev, depth]);

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
        if (r.status === 403) { if (!cancelled) setForbidden(true); return; }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const root: TreeNode[] = asArr(await r.json());
        if (cancelled) return;
        if (!root.length) {
          setBomNodes([]);
          setBomExpanded({});
          setRootKey(null);
          return;
        }

        const rootNode = root[0] as any;
        const rootPn = (rootNode?.data?.pn || pn) as string;
        const rk = String(rootNode?.key ?? rootPn);
        const rootRev = (rootNode?.data?.rev || "") as string;
        setRootKey(rk);

        const r2 = await fetch(
          `/api/bom_tree?parent=${encodeURIComponent(rootPn)}&parent_rev=${encodeURIComponent(rootRev)}&withThumb=1`
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
      const parentPn = (parentNode as any)?.data?.pn || key;
      const parentRev = (parentNode as any)?.data?.rev || "";
      const r = await fetch(
        `/api/bom_tree?parent=${encodeURIComponent(parentPn)}&parent_rev=${encodeURIComponent(parentRev)}&withThumb=1`
      );
      if (r.status === 403) { setForbidden(true); return; }
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
          const parentPn2 = (parentNode2 as any)?.data?.pn || key;
          const parentRev2 = (parentNode2 as any)?.data?.rev || "";
          const r = await fetch(
            `/api/bom_tree?parent=${encodeURIComponent(parentPn2)}&parent_rev=${encodeURIComponent(parentRev2)}&withThumb=1`
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
  const threeDOptions = useMemo(() => {
    const options: Array<{ key: string; url: string; format: PreviewFormat; label: string }> = [];
    const labelFor = (f: FileRow, fmt: PreviewFormat, idx: number) => {
      const name = f.name || (f.rel_path ? f.rel_path.split("/").pop() : "") || f.ext || `file ${idx + 1}`;
      return `${fmt.toUpperCase()} - ${name}`;
    };
    const addGroup = (fmt: PreviewFormat) => {
      const arr = fileGroups[fmt] || [];
      arr.forEach((file, idx) => {
        const url = bestUrl(file);
        if (!url) return;
        options.push({ key: `${fmt}:${idx}`, url, format: fmt, label: labelFor(file, fmt, idx) });
      });
    };
    addGroup("3mf");
    addGroup("ply");
    addGroup("stl");
    return options;
  }, [fileGroups]);

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
      ply: pick("ply"),
      stl: pick("stl"),
    };
  }, [fileGroups]);

  const pdfHref = firstLinks.pdf?.href || "";

  useEffect(() => {
    if (threeDOptions.length <= 1) {
      setSelectedPreviewKey(threeDOptions[0]?.key || "");
    } else {
      setSelectedPreviewKey("");
    }
  }, [threeDOptions]);

  const activePreview = useMemo(() => {
    if (threeDOptions.length === 0) return null;
    if (threeDOptions.length === 1) return threeDOptions[0];
    return threeDOptions.find((opt) => opt.key === selectedPreviewKey) || null;
  }, [threeDOptions, selectedPreviewKey]);

  const previewUrl = activePreview?.url ?? null;
  const previewFormat = activePreview?.format ?? null;

  const attrs = useMemo(() => {
    const raw = (part?.attrs || {}) as Record<string, any>;

    // only non-empty
    const skipKeys = new Set(["notes", "comments"]);
    const allEntries = Object.entries(raw).filter(([k, v]) => {
      if (skipKeys.has(String(k || "").toLowerCase())) return false;
      return hasDisplayValue(v);
    });

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
    const a = part?.attrs || {};
    const raw = (Array.isArray(part?.processes) && part.processes.length)
      ? part.processes
      : ([] as string[]).concat(
          Array.isArray(a.processes) ? a.processes : [],
          a.process ? [a.process] : [],
          a.process2 ? [a.process2] : [],
          a.process3 ? [a.process3] : []
        );
    return raw
      .map((x) => String(x || "").trim().toLowerCase())
      .filter((x, i, arr) => x && arr.indexOf(x) === i);
  }, [part]);

  const isBlankish = (value: any, allowNa = false) => {
    if (value === null || value === undefined) return true
    const text = String(value).trim().toLowerCase()
    if (allowNa && (text === "n/a" || text === "na")) return false
    return text === "" || text === "none" || text === "null"
  }

  const materialValue = (part?.attrs?.material || part?.attrs?.Material || part?.attrs?.MATERIAL || "") as string
  const finishValue = (part?.attrs?.finish || part?.attrs?.Finish || "") as string
  const massValue = (part?.attrs?.mass || part?.attrs?.Weight || "") as string

  const approvedInfo = useMemo(() => {
    const raw = part?.attrs?.approvedby ?? part?.attrs?.approved ?? part?.attrs?.approved_by
    if (raw === undefined || raw === null) return { approved: false, label: "" }
    if (typeof raw === "boolean") return { approved: raw, label: "" }
    const text = String(raw).trim()
    if (!text) return { approved: false, label: "" }
    const lowered = text.toLowerCase()
    if (["n/a", "na", "none", "null", "0", "false"].includes(lowered)) return { approved: false, label: "" }
    return { approved: true, label: text }
  }, [part])

  const uploaderName = useMemo(() => {
    const a = part?.attrs || {}
    return (
      a.uploader ||
      a.uploaded_by ||
      a.uploadedby ||
      a.author ||
      a.drawnby ||
      ""
    )
  }, [part])

  const approverName = useMemo(() => {
    const a = part?.attrs || {}
    return a.approvedby || a.approved || a.approved_by || a.checkedby || ""
  }, [part])

  const missingCritical = useMemo(() => {
    const missing: string[] = []
    const pnValue = (part?.part_number || pn || "").toString().trim()
    if (!pnValue) missing.push("partnumber")
    const desc = (part?.description || part?.attrs?.description || "").toString().trim()
    if (!desc) missing.push("description")
    const rev = (part?.revision || part?.attrs?.revision || "").toString().trim()
    if (!rev) missing.push("revision")
    if (isBlankish(materialValue, true)) missing.push("material")
    if (isBlankish(finishValue, true)) missing.push("finish")
    if (!processes.length) missing.push("process")
    return missing
  }, [part, pn, processes, materialValue, finishValue])

  const hasAnyFiles = useMemo(() => {
    return Object.values(firstLinks).some((v) => !!v)
  }, [firstLinks])

  const legendKeys = useMemo(() => {
    const keys = new Set<string>()
    const addProcess = (val: any) => {
      if (!val) return
      if (Array.isArray(val)) {
        val.forEach(addProcess)
        return
      }
      const text = String(val)
      const parts = text
        .split(/[,;/|&+\n\r]+/)
        .map((p) => p.trim().toLowerCase())
        .filter(Boolean)
      parts.forEach((p) => keys.add(p))
    }
    processes.forEach((p) => keys.add(String(p).toLowerCase()))
    const walk = (nodes: TreeNode[]) => {
      for (const n of nodes || []) {
        addProcess((n as any)?.data?.process)
        if (Array.isArray(n.children) && n.children.length) {
          walk(n.children as TreeNode[])
        }
      }
    }
    walk(bomNodes)
    return keys
  }, [processes, bomNodes])

  const legendEntries = useMemo(() => {
    return Object.entries(procMeta || {}).filter(([k, v]) => {
      if (!k || k.startsWith("_")) return false
      if (!v || !(v as any).icon) return false
      return legendKeys.has(String(k).toLowerCase())
    })
  }, [procMeta, legendKeys])

  // ---------- Render ----------
  const [tabIndex, setTabIndex] = useState(0)
  // If there is no drawing preview image but there is a PDF, we still
  // consider that we have a drawing. Otherwise, hide the Drawing tab and
  // default to All attributes.
  const hasDrawing = Boolean(pdfHref) || (drawingUrls?.length || 0) > 0

  async function saveNotes() {
    if (!canPartsNote || !part) return
    setNotesSaving(true)
    setNotesError(null)
    try {
      const resp = await fetch(`/api/parts/${encodeURIComponent(part.part_number)}/notes?rev=${encodeURIComponent(part.revision || "")}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes, rev: part.revision || "" }),
      })
      if (!resp.ok) {
        throw new Error(await resp.text())
      }
      const j = await resp.json()
      setNotes(String(j.notes || ""))
    } catch (e: any) {
      setNotesError(e?.message || "Failed to save notes")
    } finally {
      setNotesSaving(false)
    }
  }

  async function addComment() {
    if (!canPartsNote || !part) return
    const text = commentText.trim()
    if (!text) return
    setCommentSaving(true)
    setCommentError(null)
    try {
      const resp = await fetch(`/api/parts/${encodeURIComponent(part.part_number)}/comments?rev=${encodeURIComponent(part.revision || "")}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, rev: part.revision || "" }),
      })
      if (!resp.ok) {
        throw new Error(await resp.text())
      }
      const j = await resp.json()
      if (j.comment) {
        setComments((prev) => [...prev, j.comment as CommentRow])
      }
      setCommentText("")
    } catch (e: any) {
      setCommentError(e?.message || "Failed to add comment")
    } finally {
      setCommentSaving(false)
    }
  }

  async function handleRefreshFiles() {
    if (!canPartsEdit || !part) return
    setRefreshBusy(true)
    setRefreshError(null)
    setRefreshMsg(null)
    try {
      const resp = await fetch(`/api/parts/${encodeURIComponent(part.part_number)}/refresh_files?rev=${encodeURIComponent(part.revision || "")}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rev: part.revision || "" }),
      })
      const j = await resp.json().catch(() => ({}))
      if (!resp.ok) {
        const msg = j?.error || `HTTP ${resp.status}`
        throw new Error(msg)
      }
      const found = j?.files_found ?? 0
      const upserts = j?.artifacts_upserted ?? 0
      const thumbs = j?.thumbnails_generated ?? 0
      if (found <= 0) {
        setRefreshMsg("No matching files found for this part.")
      } else if (upserts <= 0) {
        setRefreshMsg(`No new files found. ${found} file(s) already registered.`)
      } else {
        setRefreshMsg(`Found ${found} file(s). Updated ${upserts}. Thumbs ${thumbs}.`)
      }
      setRefreshTick((t) => t + 1)
    } catch (err: any) {
      setRefreshError(err?.message || "Refresh failed")
    } finally {
      setRefreshBusy(false)
    }
  }

  async function handleDeletePart() {
    if (!canPartsDelete || !part) return;
    const label = `${part.part_number}${part.revision ? "-" + part.revision : ""}`;
    const ok = window.confirm(`Delete part ${label}? This cannot be undone.`);
    if (!ok) return;
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      const resp = await fetch("/api/part_delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pn: part.part_number, rev: part.revision || "" }),
      });
      if (!resp.ok) {
        const msg = await resp.text();
        throw new Error(msg || "Delete failed");
      }
      window.location.href = "/ui/parts";
    } catch (err: any) {
      setDeleteError(err?.message || "Delete failed");
    } finally {
      setDeleteBusy(false);
    }
  }

  async function handleExtraUpload(files: FileList | null) {
    if (!files || !files.length || !pn) return;
    setExtraUploadBusy(true);
    setExtraUploadError(null);
    try {
      const form = new FormData();
      Array.from(files).forEach((f) => form.append("file", f));
      const resp = await fetch(
        `/api/parts/${encodeURIComponent(pn)}/${encodeURIComponent(revToken)}/extra`,
        { method: "POST", body: form }
      );
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        const msg = data?.error || `HTTP ${resp.status}`;
        throw new Error(msg);
      }
      if (Array.isArray(data?.errors) && data.errors.length) {
        setExtraUploadError(data.errors.join("; "));
      }
      await loadExtraFiles();
    } catch (err: any) {
      setExtraUploadError(err?.message || "Upload failed.");
    } finally {
      setExtraUploadBusy(false);
      if (extraFileInputRef.current) extraFileInputRef.current.value = "";
    }
  }

  async function handleExtraDelete(fileId?: string) {
    if (!fileId || !pn) return;
    const ok = window.confirm("Delete this associated file?");
    if (!ok) return;
    setExtraDeleteBusy(fileId);
    try {
      const resp = await fetch(
        `/api/parts/${encodeURIComponent(pn)}/${encodeURIComponent(revToken)}/extra/${encodeURIComponent(fileId)}`,
        { method: "DELETE" }
      );
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        const msg = data?.error || `HTTP ${resp.status}`;
        throw new Error(msg);
      }
      await loadExtraFiles();
    } catch (err) {
      console.error(err);
    } finally {
      setExtraDeleteBusy(null);
    }
  }

  return (
    <div className="container-xxl py-3">
      {/* Title */}
      <div className="pb-2 border-bottom mb-3">
        <div className="d-flex align-items-start justify-content-between gap-3">
          <div>
            <h4 className="mb-0">
              {pn}
              {part?.revision ? ` REV ${part.revision}` : ""}
              {part?.description ? ` - ${part.description}` : ""}
            </h4>
            <div className="text-muted small">{part?.category || ""}</div>
          </div>
        </div>
      </div>

      {/* Top zone: Left (hero + quick facts) / Right (tabs) */}
      <div className="row g-3">
        {/* LEFT */}
        <div className="col-lg-4">
            <div className="pd-card">
            <div className="pd-hero">
              <ImageStrip pn={pn} rev={rev || ""} mode="preview" limit={1} fit />
            </div>

            <div className="pd-info-rows">
              <div className="pd-info-row pd-icon-row">
                <img
                  src={approvedInfo.approved ? "/static/images/approved.svg" : "/static/images/notapproved.svg"}
                  alt={approvedInfo.approved ? "Approved" : "Not approved"}
                  className="pd-status-icon"
                />
                {processes.map((p) => {
                  const m = procMeta[p] || procMeta["others"]
                  const icon = m?.icon ? `/static/images/${m.icon}` : `/static/images/unknown.svg`
                  return (
                    <img
                      key={p}
                      src={icon}
                      title={p}
                      className="pd-proc-icon"
                      onError={(e: any) => {
                        e.currentTarget.src = "/static/images/unknown.svg"
                      }}
                    />
                  )
                })}
              </div>

              <div className="pd-info-row pd-meta-row">
                <span><strong>Material:</strong> {materialValue || "-"}</span>
                <span><strong>Finish:</strong> {finishValue || "-"}</span>
                <span><strong>Mass:</strong> {massValue || "-"}</span>
              </div>

              <div className="pd-info-row pd-file-row">
                {(() => {
                  const href = (part?.attrs?.link || part?.attrs?.oem_internet || "").toString().trim()
                  return href ? (
                    <a className="btn btn-outline-primary btn-sm pd-file-btn" href={href} target="_blank" rel="noreferrer">
                      Link
                    </a>
                  ) : null
                })()}
                {firstLinks.edr && (
                  <a className="btn btn-info btn-sm pd-file-btn" href={firstLinks.edr.href} target="_blank" rel="noreferrer">
                    3D{firstLinks.edr.count > 1 ? ` (${firstLinks.edr.count})` : ""}
                  </a>
                )}
                {firstLinks.step && (
                  <a className="btn btn-info btn-sm pd-file-btn" href={firstLinks.step.href} target="_blank" rel="noreferrer">
                    STEP{firstLinks.step.count > 1 ? ` (${firstLinks.step.count})` : ""}
                  </a>
                )}
                {firstLinks.pdf && (
                  <a className="btn btn-success btn-sm pd-file-btn" href={firstLinks.pdf.href} target="_blank" rel="noreferrer">
                    PDF{firstLinks.pdf.count > 1 ? ` (${firstLinks.pdf.count})` : ""}
                  </a>
                )}
                {firstLinks.dxf && (
                  <a className="btn btn-success btn-sm pd-file-btn" href={firstLinks.dxf.href} target="_blank" rel="noreferrer">
                    DXF{firstLinks.dxf.count > 1 ? ` (${firstLinks.dxf.count})` : ""}
                  </a>
                )}
                {firstLinks.datasheet && (
                  <a className="btn btn-outline-secondary btn-sm pd-file-btn" href={firstLinks.datasheet.href} target="_blank" rel="noreferrer">
                    Datasheet{firstLinks.datasheet.count > 1 ? ` (${firstLinks.datasheet.count})` : ""}
                  </a>
                )}
                {firstLinks.threeMF && (
                  <a className="btn btn-outline-secondary btn-sm pd-file-btn" href={firstLinks.threeMF.href} target="_blank" rel="noreferrer">
                    3MF{firstLinks.threeMF.count > 1 ? ` (${firstLinks.threeMF.count})` : ""}
                  </a>
                )}
                {firstLinks.ply && (
                  <a className="btn btn-outline-secondary btn-sm pd-file-btn" href={firstLinks.ply.href} target="_blank" rel="noreferrer">
                    PLY{firstLinks.ply.count > 1 ? ` (${firstLinks.ply.count})` : ""}
                  </a>
                )}
                {firstLinks.stl && (
                  <a className="btn btn-outline-secondary btn-sm pd-file-btn" href={firstLinks.stl.href} target="_blank" rel="noreferrer">
                    STL{firstLinks.stl.count > 1 ? ` (${firstLinks.stl.count})` : ""}
                  </a>
                )}
                {!hasAnyFiles && (
                  <span className="text-muted small">No files found.</span>
                )}
              </div>

              {extraFiles.length > 0 && (
                <div className="pd-info-row">
                  <div className="small text-muted fw-semibold">
                    Associated files ({extraFiles.length})
                  </div>
                  <div className="small">
                    {extraFiles.slice(0, 3).map((f, idx) => (
                      <div key={f.id || f.rel_path || f.original_name || `extra-${idx}`}>
                        {f.original_name || f.rel_path || "file"}
                      </div>
                    ))}
                    {extraFiles.length > 3 && (
                      <div className="text-muted">+{extraFiles.length - 3} more</div>
                    )}
                  </div>
                </div>
              )}

              <div className="pd-info-row pd-user-row">
                <span className="pd-user-pill">
                  <img src="/static/images/file.svg" alt="Uploader" />
                  <span>{uploaderName ? `Uploaded by ${uploaderName}` : "Uploader unknown"}</span>
                </span>
                <span className="pd-user-pill">
                  <img src={approvedInfo.approved ? "/static/images/approved.svg" : "/static/images/notapproved.svg"} alt="Approval" />
                  <span>
                    {approverName
                      ? `Approved by ${approverName}`
                      : approvedInfo.approved
                      ? "Approved"
                      : "Not approved"}
                  </span>
                </span>
              </div>
            </div>

            {(insightsLoading || missingCritical.length > 0) && (
              <div className="pd-missing mt-2 pt-2 border-top">
                <div className="fw-semibold small">Missing properties</div>
                {insightsLoading && <div className="text-muted small mt-1">Checking...</div>}
                {!insightsLoading && missingCritical.length > 0 && (
                  <div className="text-danger small mt-1">Missing: {missingCritical.join(", ")}</div>
                )}
              </div>
            )}
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
            

            

            {/* NEW: 3D Preview tab using available 3D formats */}
            {/* 3D moved to end */} {false && (<TabPanel header="3D Preview">
              {previewUrl ? (
                <Suspense fallback={<div className="p-3">Loading 3D viewer...</div>}>
                  <ThreeMFViewer
                    url={previewUrl}
                    format={previewFormat || "3mf"}
                    height={520}
                  />
                </Suspense>
              ) : (
                <div className="p-3 text-muted">No 3D preview available.</div>
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
              {threeDOptions.length > 1 && (
                <div className="p-3 pb-0">
                  <label className="form-label small" htmlFor="previewSelect">
                    3D file
                  </label>
                  <select
                    id="previewSelect"
                    className="form-select form-select-sm"
                    value={selectedPreviewKey}
                    onChange={(e) => setSelectedPreviewKey(e.target.value)}
                  >
                    <option value="">Select a 3D file...</option>
                    {threeDOptions.map((opt) => (
                      <option key={opt.key} value={opt.key}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {previewUrl ? (
                <Suspense fallback={<div className="p-3">Loading 3D viewer...</div>}>
                  <ThreeMFViewer
                    url={previewUrl}
                    format={previewFormat || "3mf"}
                    height={520}
                  />
                </Suspense>
              ) : threeDOptions.length ? (
                <div className="p-3 text-muted">Select a 3D file to preview.</div>
              ) : (
                <div className="p-3 text-muted">No 3D preview available.</div>
              )}
            </TabPanel>

            <TabPanel header="Associated files">
              <div className="pd-card p-3 mt-3">
                <div className="d-flex align-items-center justify-content-between mb-2">
                  <h6 className="mb-0">Associated files</h6>
                  {canPartsEdit && (
                    <button
                      type="button"
                      className="btn btn-sm btn-outline-primary"
                      onClick={() => extraFileInputRef.current?.click()}
                      disabled={extraUploadBusy}
                    >
                      {extraUploadBusy ? "Uploading..." : "Upload files..."}
                    </button>
                  )}
                </div>
                <input
                  ref={extraFileInputRef}
                  type="file"
                  multiple
                  className="d-none"
                  onChange={(e) => handleExtraUpload(e.target.files)}
                />
                {extraUploadError && <div className="text-danger small mb-2">{extraUploadError}</div>}
                {extraError && <div className="text-danger small mb-2">{extraError}</div>}
                {extraLoading ? (
                  <div className="text-muted small">Loading...</div>
                ) : extraFiles.length ? (
                  <div className="table-responsive">
                    <table className="table table-sm">
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>Size</th>
                          <th>Type</th>
                          <th>Uploaded</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {extraFiles.map((f) => (
                          <tr key={f.id || f.rel_path || f.original_name}>
                            <td>{f.original_name || f.rel_path || "file"}</td>
                            <td>{formatBytes(f.size)}</td>
                            <td>{f.mime || "-"}</td>
                            <td>
                              {f.uploaded_at ? new Date(f.uploaded_at).toLocaleString() : "-"}
                            </td>
                            <td>
                              {f.url ? (
                                <a className="btn btn-sm btn-outline-secondary" href={f.url} target="_blank" rel="noreferrer">
                                  Download
                                </a>
                              ) : (
                                <span className="text-muted small">-</span>
                              )}
                              {canPartsEdit && (
                                <button
                                  type="button"
                                  className="btn btn-sm btn-outline-danger ms-2"
                                  disabled={extraDeleteBusy === f.id}
                                  onClick={() => handleExtraDelete(f.id)}
                                >
                                  {extraDeleteBusy === f.id ? "Deleting..." : "Delete"}
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-muted small">No associated files.</div>
                )}
              </div>
            </TabPanel>

            
            <TabPanel header="Doc Packs">

              <div className="pd-card p-3 mt-3">
                <h6 className="mb-3">BOM and output options</h6>

                <div className="row g-3">
                  <div className="col-md-6">
                    <div className="mb-3">
                      <div className="fw-semibold small">Depth of compilation</div>
                      <div className="form-check">
                        <input className="form-check-input" type="radio" name="depth" id="depthTop" checked={depth==='top'} onChange={()=>setDepth('top')} />
                        <label className="form-check-label" htmlFor="depthTop">Top Level only</label>
                      </div>
                      <div className="form-check">
                        <input className="form-check-input" type="radio" name="depth" id="depthFull" checked={depth==='full'} onChange={()=>setDepth('full')} />
                        <label className="form-check-label" htmlFor="depthFull">Full BOM</label>
                      </div>
                    </div>

                    <div className="mb-3">
                      <div className="fw-semibold small">Consumed components</div>
                      <div className="form-check">
                        <input className="form-check-input" type="radio" name="consumed" id="cHide" checked={!includeConsumed} onChange={() => setIncludeConsumed(false)} />
                        <label className="form-check-label" htmlFor="cHide">Hide consumed</label>
                      </div>
                      <div className="form-check">
                        <input className="form-check-input" type="radio" name="consumed" id="cShow" checked={includeConsumed} onChange={() => setIncludeConsumed(true)} />
                        <label className="form-check-label" htmlFor="cShow">Show consumed</label>
                      </div>
                    </div>

                    <div className="mb-3">
                      <div className="fw-semibold small">Classified components</div>
                      <div className="form-check">
                        <input className="form-check-input" type="radio" name="classified" id="clsHide" checked={classified==='hide'} onChange={()=>setClassified('hide')} />
                        <label className="form-check-label" htmlFor="clsHide">Hide classified</label>
                      </div>
                      <div className="form-check">
                        <input className="form-check-input" type="radio" name="classified" id="clsShow" checked={classified==='show'} onChange={()=>setClassified('show')} />
                        <label className="form-check-label" htmlFor="clsShow">Show classified</label>
                      </div>
                      <div className="form-check">
                        <input className="form-check-input" type="radio" name="classified" id="clsOnly" checked={classified==='only'} onChange={()=>setClassified('only')} />
                        <label className="form-check-label" htmlFor="clsOnly">Only Classified</label>
                      </div>
                    </div>
                  </div>

                  <div className="col-md-6">
                    <div className="mb-3">
                      <div className="fw-semibold small">Filter Process</div>
                      <div className="form-check">
                        <input className="form-check-input" type="radio" name="procMode" id="procSel" checked={processMode==='selected'} onChange={()=>setProcessMode('selected')} />
                        <label className="form-check-label" htmlFor="procSel">Only selected</label>
                      </div>
                      <div className="form-check">
                        <input className="form-check-input" type="radio" name="procMode" id="procAll" checked={processMode==='all'} onChange={()=>setProcessMode('all')} />
                        <label className="form-check-label" htmlFor="procAll">All</label>
                      </div>
                    </div>

                    <div className="mb-3">
                      <label className="fw-semibold small form-label" htmlFor="docOutName">Output name (optional)</label>
                      <input
                        id="docOutName"
                        className="form-control form-control-sm"
                        value={outputName}
                        onChange={(e)=>setOutputName(e.target.value)}
                        placeholder={`${pn}${rev ? `_${rev}` : ''}_docpack`}
                      />
                    </div>

                    <div className="mb-3">
                      <div className="fw-semibold small">Doc Packs</div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="docSel" checked={wantSelectedFiles} onChange={(e)=>setWantSelectedFiles(e.target.checked)} /><label className="form-check-label" htmlFor="docSel">Selected files</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="docExcel" checked={wantExcel} onChange={(e)=>setWantExcel(e.target.checked)} /><label className="form-check-label" htmlFor="docExcel">Excel BOM</label></div>
                      {wantExcel && (
                        <div className="form-check ms-3">
                          <input className="form-check-input" type="checkbox" id="docExcelAll" checked={excelAllFields} onChange={(e)=>setExcelAllFields(e.target.checked)} />
                          <label className="form-check-label" htmlFor="docExcelAll">Include all fields</label>
                        </div>
                      )}
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="docBinder" checked={wantBinder} onChange={(e)=>setWantBinder(e.target.checked)} /><label className="form-check-label" htmlFor="docBinder">PDF binder</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="docIndex" checked={wantIndex} onChange={(e)=>setWantIndex(e.target.checked)} /><label className="form-check-label" htmlFor="docIndex">Index (PDF)</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="docVisual" checked={wantVisual} onChange={(e)=>setWantVisual(e.target.checked)} /><label className="form-check-label" htmlFor="docVisual">Visual summary (PDF)</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="docHardware" checked={wantHardwareSummary} onChange={(e)=>setWantHardwareSummary(e.target.checked)} /><label className="form-check-label" htmlFor="docHardware">Hardware summary (standalone)</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="docCover" checked={wantCoverPage} onChange={(e)=>setWantCoverPage(e.target.checked)} /><label className="form-check-label" htmlFor="docCover">Cover page (standalone)</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="docWhere" checked={wantWhereusedReport} onChange={(e)=>setWantWhereusedReport(e.target.checked)} /><label className="form-check-label" htmlFor="docWhere">Where-used report (standalone)</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="docFab" checked={fabricationPack} onChange={(e)=>{
                        const on=e.target.checked; setFabricationPack(on);
                        if(on){
                          setProcessMode('selected');
                          setSelProcesses(new Set(['welding','lasercut','profile cut','folding','rolling','cutting','machine','3d laser','casting']));
                          setSelTypes(new Set(['dxf','step','pdf']));
                          setWantSelectedFiles(true);
                          setWantExcel(true);
                          setWantBinder(true);
                          setIncludeConsumed(false);
                        }
                      }} /><label className="form-check-label" htmlFor="docFab">Fabrication Pack</label></div>
                    </div>

                    {wantBinder && (
                      <div className="mb-3">
                        <div className="fw-semibold small">PDF binder options</div>
                        <div className="form-check"><input className="form-check-input" type="checkbox" id="bCover" checked={binderAddCover} onChange={(e)=>setBinderAddCover(e.target.checked)} /><label className="form-check-label" htmlFor="bCover">Add cover page</label></div>
                        <div className="form-check"><input className="form-check-input" type="checkbox" id="bIdx" checked={binderAddIndex} onChange={(e)=>setBinderAddIndex(e.target.checked)} /><label className="form-check-label" htmlFor="bIdx">Add index</label></div>
                        <div className="form-check"><input className="form-check-input" type="checkbox" id="bVis" checked={binderAddVisualList} onChange={(e)=>setBinderAddVisualList(e.target.checked)} /><label className="form-check-label" htmlFor="bVis">Visual index section</label></div>
                        <div className="form-check"><input className="form-check-input" type="checkbox" id="bWhere" checked={binderAddWhereused} onChange={(e)=>setBinderAddWhereused(e.target.checked)} /><label className="form-check-label" htmlFor="bWhere">Where-used report section</label></div>
                        <div className="form-check"><input className="form-check-input" type="checkbox" id="bHard" checked={binderAddHardwareSummary} onChange={(e)=>setBinderAddHardwareSummary(e.target.checked)} /><label className="form-check-label" htmlFor="bHard">Hardware summary</label></div>
                        <div className="form-check"><input className="form-check-input" type="checkbox" id="bData" checked={binderAddDatasheets} onChange={(e)=>setBinderAddDatasheets(e.target.checked)} /><label className="form-check-label" htmlFor="bData">Add datasheets</label></div>
                        <div className="form-check"><input className="form-check-input" type="checkbox" id="bFlat" checked={binderIncludeFlatPatterns} onChange={(e)=>setBinderIncludeFlatPatterns(e.target.checked)} /><label className="form-check-label" htmlFor="bFlat">Include flat pattern PDFs</label></div>
                        <div className="form-check"><input className="form-check-input" type="checkbox" id="bNums" checked={binderPageNumbers} onChange={(e)=>setBinderPageNumbers(e.target.checked)} /><label className="form-check-label" htmlFor="bNums">Add page numbers</label></div>
                        <div className="form-check mt-2"><input className="form-check-input" type="checkbox" id="sQuote" checked={stampQuote} onChange={(e)=>setStampQuote(e.target.checked)} /><label className="form-check-label" htmlFor="sQuote">For quotation stamp</label></div>
                        <div className="form-check"><input className="form-check-input" type="checkbox" id="sConf" checked={stampConfidential} onChange={(e)=>setStampConfidential(e.target.checked)} /><label className="form-check-label" htmlFor="sConf">Confidential stamp</label></div>
                        <div className="form-check"><input className="form-check-input" type="checkbox" id="sAppr" checked={stampApproved} onChange={(e)=>setStampApproved(e.target.checked)} /><label className="form-check-label" htmlFor="sAppr">Approval stamp</label></div>
                        <div className="form-check"><input className="form-check-input" type="checkbox" id="sWip" checked={stampWip} onChange={(e)=>setStampWip(e.target.checked)} /><label className="form-check-label" htmlFor="sWip">In WIP stamp</label></div>
                        <div className="form-check"><input className="form-check-input" type="checkbox" id="sProg" checked={stampInprog} onChange={(e)=>setStampInprog(e.target.checked)} /><label className="form-check-label" htmlFor="sProg">In progress/Not approved</label></div>
                      </div>
                    )}
                  </div>
                </div>

                <div className="accordion my-3" id="docpacksAcc">
                  <div className="accordion-item">
                    <h2 className="accordion-header" id="headingFiles">
                      <button className="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseFiles">File filter</button>
                    </h2>
                    <div id="collapseFiles" className="accordion-collapse collapse">
                      <div className="accordion-body">
                        <div className="row g-2">
                          {docOpts.file_types.map((t) => (
                            <div key={t} className="col-6 col-md-3">
                              <div className="form-check">
                                <input className="form-check-input" type="checkbox" id={`ft_${t}`} checked={selTypes.has(t)} onChange={(e)=>{
                                  const next = new Set(selTypes); if(e.target.checked) next.add(t); else next.delete(t); setSelTypes(next);
                                }} />
                                <label className="form-check-label" htmlFor={`ft_${t}`}>{t}</label>
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="mt-2">
                          <button className="btn btn-sm btn-outline-secondary me-2" onClick={()=>setSelTypes(new Set(docOpts.file_types))}>Select all</button>
                          <button className="btn btn-sm btn-outline-secondary" onClick={()=>setSelTypes(new Set())}>Select none</button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="accordion-item mt-2">
                    <h2 className="accordion-header" id="headingProc">
                      <button className="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseProc">Process filter (only selected will be output)</button>
                    </h2>
                    <div id="collapseProc" className="accordion-collapse collapse">
                      <div className="accordion-body">
                        <div className="row g-2">
                          {docOpts.processes.map((p) => (
                            <div key={p} className="col-6 col-md-3">
                              <div className="form-check">
                                <input className="form-check-input" type="checkbox" id={`pr_${p}`} checked={selProcesses.has(p)} onChange={(e)=>{
                                  const next = new Set(selProcesses); if(e.target.checked) next.add(p); else next.delete(p); setSelProcesses(next);
                                }} />
                                <label className="form-check-label" htmlFor={`pr_${p}`}>{p}</label>
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="mt-2">
                          <button className="btn btn-sm btn-outline-secondary me-2" onClick={()=>setSelProcesses(new Set(docOpts.processes))}>Select all</button>
                          <button className="btn btn-sm btn-outline-secondary" onClick={()=>setSelProcesses(new Set())}>Select none</button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div>
                  <button className="btn btn-primary" disabled={docLoading} onClick={async ()=>{
                    setDocLoading(true);
                    // kick off a friendly progress indicator (indeterminate → up to 85%)
                    setDocProgress(10);
                    if (progressTimer.current) { window.clearInterval(progressTimer.current); }
                    progressTimer.current = window.setInterval(() => {
                      setDocProgress((p) => {
                        if (p >= 85) return p;
                        const step = Math.max(1, Math.round((85 - p) * 0.08));
                        return Math.min(85, p + step);
                      });
                    }, 700);
                    try{
                      const body:any = {
                        pn, rev,
                        depth,
                        include_consumed: includeConsumed,
                        classified,
                        process_mode: processMode,
                        processes: processMode==='selected' ? Array.from(selProcesses) : [],
                        file_types: Array.from(selTypes),
                        selected_files: wantSelectedFiles,
                        excel_bom: wantExcel,
                        excel_all_fields: excelAllFields,
                        pdf_binder: wantBinder,
                        index_pdf: wantIndex,
                        visual_list: wantVisual,
                        hardware_summary: wantHardwareSummary,
                        cover_page: wantCoverPage,
                        whereused_report: wantWhereusedReport,
                        fabrication_pack: fabricationPack,
                        binder_add_cover: binderAddCover,
                        binder_add_visual_list: binderAddVisualList,
                        binder_add_whereused: binderAddWhereused,
                        binder_add_index: binderAddIndex,
                        binder_add_datasheets: binderAddDatasheets,
                        binder_add_hardware_summary: binderAddHardwareSummary,
                        binder_page_numbers: binderPageNumbers,
                        binder_include_flat_patterns: binderIncludeFlatPatterns,
                        stamp_quote: stampQuote,
                        stamp_confidential: stampConfidential,
                        stamp_approved: stampApproved,
                        stamp_wip: stampWip,
                        stamp_inprogress: stampInprog,
                      };
                      if (outputName.trim()) body.output_name = outputName.trim();
                      const resp = await fetch('/api/docpacks/build', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
                      if(!resp.ok) throw new Error(`HTTP ${resp.status}`);
                      const blob = await resp.blob();
                      const disp = resp.headers.get('Content-Disposition') || '';
                      const m = disp.match(/filename=\"?([^\";]+)\"?/i);
                      const filename = (m? m[1] : `${pn}_docpack.zip`).replace(/\s+/g,'_');
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a'); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
                      // finish progress
                      setDocProgress(100);
                      setTimeout(() => setDocProgress(0), 800);
                    }catch(err){
                      console.error(err);
                      setDocProgress(0);
                    }
                    finally{
                      setDocLoading(false);
                      if (progressTimer.current) { window.clearInterval(progressTimer.current); progressTimer.current = null; }
                    }
                  }}>{docLoading? `Building... ${docProgress}%` : 'Submit'}</button>
                  {docLoading && (
                    <div className="mt-2" aria-live="polite">
                      <div className="progress" style={{height: 8}}>
                        <div className="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={docProgress} style={{width: `${Math.max(5, docProgress)}%`}} />
                      </div>
                      <div className="small text-muted mt-1">
                        {(() => {
                          const items: string[] = [];
                          if (wantSelectedFiles) items.push("selected files");
                          if (wantExcel) items.push("Excel BOM");
                          if (wantIndex) items.push("Index");
                          if (wantVisual) items.push("Visual summary");
                          if (wantHardwareSummary) items.push("Hardware summary");
                          if (wantCoverPage) items.push("Cover page");
                          if (wantWhereusedReport) items.push("Where-used report");
                          if (wantBinder) items.push("Binder");
                          return `Preparing ${items.join(", ") || "outputs"}...`;
                        })()}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </TabPanel>

          {versions.length > 1 && (
            <TabPanel header="Other versions">
              <DataTable value={versions} dataKey="id" responsiveLayout="scroll" stripedRows>
                <Column header="" body={(r: VersionRow) => <ThumbImg urls={r.thumb_urls || []} maxH={32} maxW={48} />} style={{width:60}} />
                <Column field="part_number" header="Part Number" body={(r: VersionRow) => <a href={`/ui/part/${encodeURIComponent(r.part_number)}?rev=${encodeURIComponent(r.revision||"")}`}>{r.part_number}</a>} sortable />
                <Column field="revision" header="Rev" sortable />
                <Column field="description" header="Description" sortable />
              </DataTable>
            </TabPanel>
          )}

          <TabPanel header="Jobs & Orders">
            {jobsOrders.length ? (
              <DataTable value={jobsOrders} dataKey="row_key" responsiveLayout="scroll" stripedRows>
                <Column
                  header="Source"
                  body={(r: JobsOrdersRow) => (r.source === "job" ? "Job" : "Order")}
                  style={{ width: 90 }}
                />
                <Column
                  header="Job"
                  body={(r: JobsOrdersRow) =>
                    r.job_number ? (
                      canJobsManage ? (
                        <a href={`/admin/jobs/${encodeURIComponent(r.job_id || "")}/edit`}>{r.job_number}</a>
                      ) : (
                        r.job_number
                      )
                    ) : (
                      "-"
                    )
                  }
                  style={{ width: 140 }}
                />
                <Column
                  header="Order"
                  body={(r: JobsOrdersRow) =>
                    r.order_number ? (
                      canOrdersManage ? (
                        <a href={`/admin/orders/${encodeURIComponent(r.order_id || "")}/edit`}>{r.order_number}</a>
                      ) : (
                        r.order_number
                      )
                    ) : (
                      "-"
                    )
                  }
                  style={{ width: 140 }}
                />
                <Column
                  header="Immediate Parent"
                  body={(r: JobsOrdersRow) => (
                    <div>
                      <a href={`/ui/part/${encodeURIComponent(r.immediate_pn)}?rev=${encodeURIComponent(r.immediate_rev || "")}`}>
                        {r.immediate_pn}
                      </a>
                      {r.immediate_desc ? <div className="text-muted small">{r.immediate_desc}</div> : null}
                    </div>
                  )}
                />
                <Column
                  header="Top-Level Parent"
                  body={(r: JobsOrdersRow) => (
                    <div>
                      <a href={`/ui/part/${encodeURIComponent(r.top_pn)}?rev=${encodeURIComponent(r.top_rev || "")}`}>
                        {r.top_pn}
                      </a>
                      {r.top_desc ? <div className="text-muted small">{r.top_desc}</div> : null}
                    </div>
                  )}
                />
                <Column
                  header="Order Status"
                  body={(r: JobsOrdersRow) => (r.order_status ? r.order_status : "-")}
                  style={{ width: 140 }}
                />
              </DataTable>
            ) : (
              <div className="text-muted small">No jobs or orders found for this part.</div>
            )}
          </TabPanel>


            
          <TabPanel header="Notes & Comments">
            <div className="pd-card p-3 mt-3">
              <div className="d-flex align-items-center justify-content-between">
                <h6 className="mb-0">Notes</h6>
                {canPartsNote ? (
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-primary"
                    onClick={saveNotes}
                    disabled={notesSaving}
                  >
                    {notesSaving ? "Saving..." : "Save"}
                  </button>
                ) : null}
              </div>
              <textarea
                className="form-control form-control-sm mt-2"
                rows={4}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add notes for this part..."
                disabled={!canPartsNote}
              />
              {notesError ? <div className="text-danger small mt-1">{notesError}</div> : null}
              {!canPartsNote && <div className="text-muted small mt-1">Read-only</div>}

              <div className="mt-3">
                <h6 className="mb-2">Comments</h6>
                {comments.length ? (
                  <div className="d-flex flex-column gap-2">
                    {comments.map((c, idx) => (
                      <div key={`${c.ts}-${idx}`} className="border rounded p-2">
                        <div className="small text-muted">
                          {c.author || "User"} {c.ts ? `- ${new Date(c.ts).toLocaleString()}` : ""}
                        </div>
                        <div className="small">{c.text}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-muted small">No comments yet.</div>
                )}
                {canPartsNote && (
                  <div className="input-group input-group-sm mt-2">
                    <input
                      type="text"
                      className="form-control"
                      value={commentText}
                      onChange={(e) => setCommentText(e.target.value)}
                      placeholder="Add a comment..."
                      disabled={commentSaving}
                    />
                    <button
                      className="btn btn-outline-primary"
                      type="button"
                      onClick={addComment}
                      disabled={commentSaving || !commentText.trim()}
                    >
                      {commentSaving ? "Adding..." : "Add"}
                    </button>
                  </div>
                )}
                {commentError ? <div className="text-danger small mt-1">{commentError}</div> : null}
              </div>
            </div>
          </TabPanel>


          <TabPanel header="Actions">
            <div className="pd-card p-3">
              {(canPartsEdit || canPartsDelete) ? (
                <div className="d-flex flex-column gap-3">
                  {canPartsEdit && (
                    <div>
                      <button
                        type="button"
                        className="btn btn-outline-secondary btn-sm"
                        onClick={handleRefreshFiles}
                        disabled={refreshBusy}
                      >
                        {refreshBusy ? "Refreshing..." : "Update files"}
                      </button>
                      {refreshMsg ? <div className="text-muted small mt-1">{refreshMsg}</div> : null}
                      {refreshError ? <div className="text-danger small mt-1">{refreshError}</div> : null}
                      <div className="text-muted small mt-1">Scans storage for files matching this PN and revision.</div>
                    </div>
                  )}
                  {canPartsDelete && (
                    <div>
                      <button
                        type="button"
                        className="btn btn-outline-danger btn-sm"
                        onClick={handleDeletePart}
                        disabled={deleteBusy}
                      >
                        {deleteBusy ? "Deleting..." : "Delete part"}
                      </button>
                      {deleteError ? <div className="text-danger small mt-1">{deleteError}</div> : null}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-muted small">No actions available.</div>
              )}
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
      {bomNodes.length > 0 ? (
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
      ) : null}

      {/* Optional: small image strip under everything */}
      <br />
      <br />
      {legendEntries.length ? (
        <div className="pd-proc-legend">
          {legendEntries.map(([k, m]) => (
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
      ) : null}
    </div>
  );
}


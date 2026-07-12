// frontend/src/pages/PartDetailPage.tsx
import React, { useEffect, useMemo, useState, Suspense, useRef } from "react";
import { useLocation, useParams, Link } from "react-router-dom";
import { DataTable } from "primereact/datatable";
import { Column } from "primereact/column";
import { TreeTable } from "primereact/treetable";
import type { TreeNode } from "primereact/treenode";
import { TabView, TabPanel } from "primereact/tabview";
import ImageStrip from "../components/ImageStrip";
import ThumbImg from "../components/ThumbImg";
import "./partdetail.css";
import FieldSelector from "../components/FieldSelector";
import DrawingMarkupWorkspace from "../components/markups/DrawingMarkupWorkspace";
import { withBomOccurrenceKeys } from "../lib/bomTree";
import type {
  DrawingImageRow,
  MarkupDraft,
  MarkupLayer,
  MarkupThread,
} from "../components/markups/types";
import {
  contextFields,
  defaultFieldIds,
  fieldFilterPlaceholder,
  formatFieldValue,
  loadFieldConfig,
  matchesFieldFilter,
  requiredFieldIds,
  saveFieldPreferences,
  selectedFieldIds,
  updateContextSelection,
  updateContextMode,
  type FieldConfigPayload,
  type FieldDefinition,
  type FieldPreferences,
} from "../lib/fieldConfig";

// ---------- Types ----------
type Part = {
  part_number: string;
  description: string;
  revision?: string;
  notes?: string;
  category?: string;
  uom?: string;
  processes?: string[];
  process?: string;
  field_values?: Record<string, any>;
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
const PREVIEW_FORMAT_PRIORITY: PreviewFormat[] = ["ply", "3mf", "stl"];

type DatasheetOption = {
  key: string;
  url: string;
  ext: string;
  label: string;
  file: FileRow;
  isExternal: boolean;
  canPreview: boolean;
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
  part_number?: string;
  revision?: string;
  description?: string;
  [key: string]: any;
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

type IdentityProfile = {
  email?: string;
  display_name?: string;
  label?: string;
  initials?: string;
  avatar_color?: string;
  avatar_shape?: string;
  roles?: string[];
  permissions?: string[];
};

type CommentReplyRow = {
  id: string;
  ts: string | null;
  ts_display?: string | null;
  ts_local?: string | null;
  author: string;
  author_display?: string;
  author_profile?: IdentityProfile | null;
  text: string;
};

type CommentRow = {
  id?: string;
  ts: string;
  ts_display?: string | null;
  ts_local?: string | null;
  author: string;
  author_display?: string;
  author_profile?: IdentityProfile | null;
  text: string;
  priority?: "low" | "normal" | "high" | "";
  status?: "open" | "resolved";
  replies?: CommentReplyRow[];
  reply_count?: number;
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
  uploaded_at_display?: string;
  uploaded_at_local?: string;
  url?: string;
  rel_path?: string;
};

type FileOverviewRow = {
  id?: string;
  db_id?: string;
  collection?: string;
  kind?: string;
  part_number?: string;
  revision?: string;
  display_revision?: string;
  name?: string;
  label?: string;
  ext_group?: string;
  ext?: string;
  mime?: string;
  rel_path?: string;
  size?: number;
  source?: string;
  recorded_by?: string;
  recorded_at?: string;
  recorded_at_display?: string;
  recorded_at_local?: string;
  url?: string;
};

type FileOverviewSection = {
  revision?: string;
  display_revision?: string;
  counts?: {
    total?: number;
    part_files?: number;
    part_extra_files?: number;
  };
  files?: FileOverviewRow[];
};

type PublicShareInfo = {
  share_id?: string;
  created_at?: string;
  created_at_display?: string | null;
  created_at_local?: string | null;
  expires_at?: string;
  expires_at_display?: string | null;
  expires_at_local?: string | null;
  access_count?: number;
  allow_children?: boolean;
  allow_docpacks?: boolean;
  allow_attributes?: boolean;
};

type PartShareRow = {
  id: string;
  part_number: string;
  revision: string;
  token_prefix?: string;
  allow_children?: boolean;
  allow_docpacks?: boolean;
  allow_attributes?: boolean;
  status?: string;
  created_at?: string | null;
  created_at_display?: string | null;
  created_at_local?: string | null;
  created_by_email?: string;
  expires_at?: string | null;
  expires_at_display?: string | null;
  expires_at_local?: string | null;
  revoked_at?: string | null;
  revoked_at_display?: string | null;
  revoked_at_local?: string | null;
  revoked_by_email?: string;
  last_accessed_at?: string | null;
  last_accessed_at_display?: string | null;
  last_accessed_at_local?: string | null;
  access_count?: number;
};

type FlatBomRow = {
  row_key?: string;
  part_number?: string;
  revision?: string;
  description?: string;
  qty?: number;
  uom?: string;
  alt_group?: string;
  thumb_urls?: string[];
  pending_review_count?: number;
  pending_review_severity?: "low" | "normal" | "high" | "";
  has_pending_reviews?: boolean;
  [key: string]: any;
};

const FALLBACK_SUMMARY_FIELDS: FieldDefinition[] = [
  { id: "material", label: "Material", kind: "builtin", filterable: true, sortable: true },
  { id: "finish", label: "Finish", kind: "builtin", filterable: true, sortable: true },
  { id: "mass", label: "Mass", kind: "builtin", filterable: true, sortable: true },
  { id: "process", label: "Process", kind: "builtin", filterable: true, sortable: true },
];

const FALLBACK_BOM_FIELDS: FieldDefinition[] = [
  { id: "thumbnail", label: "Thumbnail", kind: "special", filterable: false, sortable: false },
  { id: "part_number", label: "Part Number", kind: "builtin", filterable: true, sortable: true },
  { id: "revision", label: "Revision", kind: "builtin", filterable: true, sortable: true },
  { id: "description", label: "Description", kind: "builtin", filterable: true, sortable: true },
  { id: "process", label: "Process", kind: "builtin", filterable: true, sortable: true },
  { id: "finish", label: "Finish", kind: "builtin", filterable: true, sortable: true },
  { id: "material", label: "Material", kind: "builtin", filterable: true, sortable: true },
  { id: "qty", label: "Qty", kind: "special", filterable: true, sortable: true },
];

const FALLBACK_WHERE_USED_FIELDS: FieldDefinition[] = [
  { id: "thumbnail", label: "Thumbnail", kind: "special", filterable: false, sortable: false },
  { id: "part_number", label: "Part Number", kind: "builtin", filterable: true, sortable: true },
  { id: "revision", label: "Revision", kind: "builtin", filterable: true, sortable: true },
  { id: "description", label: "Description", kind: "builtin", filterable: true, sortable: true },
  { id: "qty", label: "Qty", kind: "special", filterable: true, sortable: true },
];

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

function initialsForLabel(value: string): string {
  const tokens = String(value || "")
    .trim()
    .split(/[\s._-]+/)
    .filter(Boolean)
  if (!tokens.length) return "U"
  if (tokens.length === 1) return tokens[0].slice(0, 2).toUpperCase()
  return `${tokens[0][0]}${tokens[1][0]}`.toUpperCase()
}

function identityLabel(profile?: IdentityProfile | null, fallback = ""): string {
  return String(profile?.label || profile?.display_name || profile?.email || fallback || "").trim()
}

function identityAvatar(profile?: IdentityProfile | null, fallback = "", size: "sm" | "md" = "sm") {
  const label = identityLabel(profile, fallback) || "User"
  const shape = String(profile?.avatar_shape || "circle").toLowerCase()
  const avatarClass = shape === "square" ? "square" : shape === "rounded" ? "rounded" : "circle"
  return (
    <span
      className={`pd-identity-avatar pd-identity-avatar--${size} pd-identity-avatar--${avatarClass}`}
      style={{ backgroundColor: String(profile?.avatar_color || "#1d4ed8") }}
      title={label}
      aria-hidden="true"
    >
      {String(profile?.initials || initialsForLabel(label)).slice(0, 2)}
    </span>
  )
}

const APPROVAL_TRUE_VALUES = new Set(["1", "true", "yes", "y", "on", "approved"])
const APPROVAL_FALSE_VALUES = new Set([
  "0",
  "false",
  "no",
  "n",
  "off",
  "missing",
  "none",
  "absent",
  "n/a",
  "na",
  "null",
  "not approved",
  "not_approved",
  "not-approved",
  "notapproved",
  "unapproved",
  "rejected",
  "wip",
  "work in progress",
  "in progress",
])
const PART_DETAIL_FIELD_FALLBACK_ALIASES: Record<string, string[]> = {
  description: ["description", "desc", "desc1", "summary_text"],
  revision: ["revision", "rev"],
  category: ["category"],
  material: ["material"],
  finish: ["finish", "treatment", "colour", "color"],
  mass: ["mass", "weight"],
  uom: ["uom", "unit", "unit_of_measure"],
  link: ["link", "oem_internet", "oem_link"],
  oem: ["oem", "manufacturer", "oem_supplier"],
  oem_partnumber: ["oem_partnumber", "oem_part_number", "supplier_partnumber", "supplier_part_number", "mfr_part", "manufacturer_part"],
  datasheet: ["datasheet", "oem_data_sheet", "oem_datasheet", "data_sheet", "datasheet_url"],
  approved: ["approved"],
  approved_by: ["approvedby", "approved_by", "approved"],
  process: [
    "process",
    "processes",
    "process2",
    "process3",
    "secondprocess",
    "thirdprocess",
    "second_process",
    "third_process",
    "second process",
    "third process",
  ],
}

function normalizeAliasName(value: unknown): string {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
}

function readRecordValue(record: Record<string, unknown> | null | undefined, key: string) {
  if (!record) return undefined
  if (Object.prototype.hasOwnProperty.call(record, key)) return record[key]
  const target = normalizeAliasName(key)
  if (!target) return undefined
  for (const [recordKey, value] of Object.entries(record)) {
    if (normalizeAliasName(recordKey) === target) return value
  }
  return undefined
}

function canonicalFieldAliases(
  config: FieldConfigPayload | null | undefined,
  fieldId: string,
  fallbackAliases: string[],
): string[] {
  const aliases = new Set<string>()
  const add = (value: unknown) => {
    const text = String(value ?? "").trim()
    if (text) aliases.add(text)
  }

  add(fieldId)
  const entry = (config?.canonical_aliases || []).find(
    (item) => normalizeAliasName(item?.field_id) === normalizeAliasName(fieldId),
  )
  for (const alias of entry?.aliases || []) add(alias)
  for (const alias of fallbackAliases) add(alias)

  return Array.from(aliases)
}

function collectRecordValues(record: Record<string, unknown> | null | undefined, aliases: string[]): unknown[] {
  const values: unknown[] = []
  for (const alias of aliases) {
    const value = readRecordValue(record, alias)
    if (value !== undefined) values.push(value)
  }
  return values
}

function approvalTextVariants(value: string): string[] {
  const text = String(value || "").trim().toLowerCase()
  if (!text) return []

  const variants = new Set<string>()
  const add = (item: string) => {
    const normalized = item.trim().toLowerCase().replace(/\s+/g, " ")
    if (normalized) variants.add(normalized)
  }

  add(text)
  add(text.replace(/[_-]+/g, " "))

  const alnumSpaced = text.replace(/[^a-z0-9]+/g, " ").trim().replace(/\s+/g, " ")
  if (alnumSpaced) {
    add(alnumSpaced)
    add(alnumSpaced.replace(/\s+/g, ""))
    add(alnumSpaced.replace(/\s+/g, "_"))
    add(alnumSpaced.replace(/\s+/g, "-"))
  }

  return Array.from(variants)
}

function explicitApprovalStatus(value: unknown): boolean | null {
  if (value === undefined || value === null) return null
  if (typeof value === "boolean") return value
  if (typeof value === "number") return value !== 0
  if (typeof value !== "string") return null

  const text = value.trim()
  if (!text) return null

  const variants = approvalTextVariants(text)
  if (variants.some((item) => APPROVAL_FALSE_VALUES.has(item))) return false
  if (variants.some((item) => APPROVAL_TRUE_VALUES.has(item))) return true
  return null
}

function approvalStatus(value: unknown): boolean | null {
  if (value === undefined || value === null) return null
  if (Array.isArray(value)) {
    let sawNonEmpty = false
    for (const item of value) {
      const status = approvalStatus(item)
      if (status === false) return false
      if (status === true) return true
      if (hasDisplayValue(item)) sawNonEmpty = true
    }
    return sawNonEmpty ? true : null
  }

  const explicit = explicitApprovalStatus(value)
  if (explicit !== null) return explicit
  if (typeof value === "string") return value.trim() ? true : null
  if (typeof value === "number") return value !== 0
  return null
}

function approvalIdentityText(value: unknown): string {
  if (value === undefined || value === null) return ""
  if (Array.isArray(value)) {
    return value
      .map((item) => approvalIdentityText(item))
      .filter(Boolean)
      .join(", ")
      .trim()
  }
  if (explicitApprovalStatus(value) !== null) return ""
  if (typeof value !== "string") return ""
  return value.trim()
}

function partDetailFieldFallbackAliases(fieldId: string): string[] {
  return PART_DETAIL_FIELD_FALLBACK_ALIASES[fieldId] || [fieldId]
}

function processTokens(value: unknown): string[] {
  if (value === undefined || value === null) return []
  if (Array.isArray(value)) {
    return value.flatMap((item) => processTokens(item))
  }
  return String(value)
    .split(/\s*(?:,|;|\/|\||&|\+|\r|\n)\s*/)
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean)
}

// ---------- Component ----------
export default function PartDetailPage() {
  const route = useParams();
  const location = useLocation();
  const sp = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const shareId = route.shareId || (window as any).__INITIAL__?.share_id || "";
  const shareToken = route.token || (window as any).__INITIAL__?.share_token || "";
  const isSharedView = !!shareId && !!shareToken;
  const pn = (isSharedView ? sp.get("pn") : route.pn) || (window as any).__INITIAL__?.pn || "";
  const rev = sp.get("rev") || ((window as any).__INITIAL__?.rev ?? "");
  const shareApiBase = isSharedView
    ? `/api/share/part/${encodeURIComponent(shareId)}/${encodeURIComponent(shareToken)}`
    : "";
  const shareViewBase = isSharedView
    ? `/share/part/${encodeURIComponent(shareId)}/${encodeURIComponent(shareToken)}`
    : "";
  const partImagesEndpoint = isSharedView ? `${shareApiBase}/part_images` : "/api/part_images";

  const [part, setPart] = useState<Part | null>(null);
  const [files, setFiles] = useState<FileRow[]>([]);
  const [extraFiles, setExtraFiles] = useState<ExtraFileRow[]>([]);
  const [extraLoading, setExtraLoading] = useState(false);
  const [extraError, setExtraError] = useState<string | null>(null);
  const [extraUploadBusy, setExtraUploadBusy] = useState(false);
  const [extraUploadError, setExtraUploadError] = useState<string | null>(null);
  const [extraDeleteBusy, setExtraDeleteBusy] = useState<string | null>(null);
  const [filesOverviewCurrent, setFilesOverviewCurrent] = useState<FileOverviewSection | null>(null);
  const [filesOverviewOther, setFilesOverviewOther] = useState<FileOverviewSection[]>([]);
  const [filesOverviewLoading, setFilesOverviewLoading] = useState(false);
  const [filesOverviewError, setFilesOverviewError] = useState<string | null>(null);
  const [children, setChildren] = useState<ChildRow[]>([]);
  const [wu, setWU] = useState<WURow[]>([]);
  const [versions, setVersions] = useState<VersionRow[]>([]);
  const [jobsOrders, setJobsOrders] = useState<JobsOrdersRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [canJobsManage, setCanJobsManage] = useState(false);
  const [canOrdersManage, setCanOrdersManage] = useState(false);
  const [canAdmin, setCanAdmin] = useState(false);
  const [canPartsDelete, setCanPartsDelete] = useState(false);
  const [canPartsNote, setCanPartsNote] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteChildren, setDeleteChildren] = useState(false);
  const [deleteFilesToo, setDeleteFilesToo] = useState(false);
  const [refreshBusy, setRefreshBusy] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [refreshMsg, setRefreshMsg] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const [refreshIncludeChildren, setRefreshIncludeChildren] = useState(false);
  const [canPartsEdit, setCanPartsEdit] = useState(false);
  const [publicShareInfo, setPublicShareInfo] = useState<PublicShareInfo | null>(null);
  const [fieldConfig, setFieldConfig] = useState<FieldConfigPayload | null>(null);
  const [fieldPreferences, setFieldPreferences] = useState<FieldPreferences | null>(null);
  const insightsLoading = false;
  const [notes, setNotes] = useState("");
  const [savedNotes, setSavedNotes] = useState("");
  const [notesSavedOnce, setNotesSavedOnce] = useState(false);
  const [comments, setComments] = useState<CommentRow[]>([]);
  const [uploaderProfile, setUploaderProfile] = useState<IdentityProfile | null>(null);
  const [approverProfile, setApproverProfile] = useState<IdentityProfile | null>(null);
  const [notesSaving, setNotesSaving] = useState(false);
  const [notesError, setNotesError] = useState<string | null>(null);
  const [commentSaving, setCommentSaving] = useState(false);
  const [commentError, setCommentError] = useState<string | null>(null);
  const [notesSearch, setNotesSearch] = useState("");
  const [attributeSearch, setAttributeSearch] = useState("");
  const [shareLinks, setShareLinks] = useState<PartShareRow[]>([]);
  const [shareLoading, setShareLoading] = useState(false);
  const [shareError, setShareError] = useState<string | null>(null);
  const [shareCreateBusy, setShareCreateBusy] = useState(false);
  const [shareCreateError, setShareCreateError] = useState<string | null>(null);
  const [shareCreateUrl, setShareCreateUrl] = useState("");
  const [shareCopied, setShareCopied] = useState(false);
  const [shareExpiresDays, setShareExpiresDays] = useState("30");
  const [shareAllowChildren, setShareAllowChildren] = useState(false);
  const [shareAllowExtended, setShareAllowExtended] = useState(false);
  const [shareRevokingId, setShareRevokingId] = useState<string | null>(null);
  const [arenaBaseUrl, setArenaBaseUrl] = useState("");
  const [arenaBusy, setArenaBusy] = useState<null | "bom" | "links">(null);
  const [arenaError, setArenaError] = useState<string | null>(null);

  // for the right-side Drawing tab + hero image
  const [drawingUrls, setDrawingUrls] = useState<string[]>([]);
  const [images, setImages] = useState<string[]>([]);

  // Drawing markup layer (vector overlay + review threads)
  const [drawingSource, setDrawingSource] = useState<DrawingImageRow | null>(null);
  const [markupLayer, setMarkupLayer] = useState<MarkupLayer | null>(null);
  const [markupLoading, setMarkupLoading] = useState(false);
  const [markupError, setMarkupError] = useState<string | null>(null);
  const markupDraftRef = useRef<MarkupDraft | null>(null);
  const [selectedPreviewKey, setSelectedPreviewKey] = useState<string>("");
  const [selectedDatasheetKey, setSelectedDatasheetKey] = useState<string>("");

  // Doc Packs state
  type DocOpts = { file_types: string[]; processes: string[]; markup_document_count: number };
  const [docOpts, setDocOpts] = useState<DocOpts>({ file_types: [], processes: [], markup_document_count: 0 });
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
  const [wantMarkupFiles, setWantMarkupFiles] = useState(false);
  const [wantMarkupReport, setWantMarkupReport] = useState(false);
  const [binderAddCover, setBinderAddCover] = useState(true);
  const [binderAddVisualList, setBinderAddVisualList] = useState(true);
  const [binderAddWhereused, setBinderAddWhereused] = useState(false);
  const [binderAddIndex, setBinderAddIndex] = useState(true);
  const [binderAddDatasheets, setBinderAddDatasheets] = useState(false);
  const [binderAddHardwareSummary, setBinderAddHardwareSummary] = useState(true);
  const [binderPageNumbers, setBinderPageNumbers] = useState(true);
  const [binderIncludeFlatPatterns, setBinderIncludeFlatPatterns] = useState(false);
  const [binderAddMarkups, setBinderAddMarkups] = useState(false);
  const [stampQuote, setStampQuote] = useState(false);
  const [stampConfidential, setStampConfidential] = useState(false);
  const [stampApproved, setStampApproved] = useState(false);
  const [stampWip, setStampWip] = useState(false);
  const [stampInprog, setStampInprog] = useState(false);
  const [outputName, setOutputName] = useState("");
  const [includeConsumed, setIncludeConsumed] = useState(false); // Hide consumed by default
  const [fabricationPack, setFabricationPack] = useState(false);

  // BOM Tree
  const [bomMode, setBomMode] = useState<"tree" | "flat">("tree");
  const [bomNodes, setBomNodes] = useState<TreeNode[]>([]);
  const [flatBomRows, setFlatBomRows] = useState<FlatBomRow[]>([]);
  const [flatBomLoading, setFlatBomLoading] = useState(false);
  const [bomExpanded, setBomExpanded] = useState<Record<string, boolean>>({});

  const effectiveRev = (part?.revision ?? rev ?? "").trim();
  const revToken = effectiveRev ? effectiveRev : "__no_rev__";
  const sharedAllowsChildren = !!publicShareInfo?.allow_children;
  const sharedAllowsDocpacks = !!publicShareInfo?.allow_docpacks;
  const sharedAllowsAttributes = !!publicShareInfo?.allow_attributes;

  // --- TreeTable filters (controlled) ---
  type TTFilters = Record<string, { value: any; matchMode: string }>;

  const [ttFilters, setTtFilters] = useState<TTFilters>({});

  // Remove cleared filters ('' / null) so they do not stick.
  function normalizeFilters(next: TTFilters): TTFilters {
    const out: TTFilters = {};
    for (const k of Object.keys(next || {})) {
      if (hasActiveFilterValue(filterMetaValue(next[k]))) out[k] = next[k];
    }
    return out;
  }

  function onTTFilter(e: any) {
    setTtFilters(normalizeFilters(e.filters || {}));
  }

  const [ttKey, setTtKey] = useState(0); // to force remount
  function clearTTFilters() {
    setTtFilters({});
    setTtKey((k) => k + 1);
  }

  function setTTFilterValue(key: string, value: any, matchMode = "custom") {
    setTtFilters((prev) =>
      normalizeFilters({
        ...prev,
        [key]: { ...(prev[key] || { matchMode }), value, matchMode },
      }),
    )
  }

  function setBooleanTTFilter(key: string, value: string) {
    let nextValue: boolean | null = null
    if (value === "true") nextValue = true
    if (value === "false") nextValue = false
    setTTFilterValue(key, nextValue, "custom")
  }

  function renderBomColumnFilter(field: FieldDefinition) {
    if (field.data_type !== "boolean") return undefined
    const rawValue = filterMetaValue(ttFilters?.[field.id])
    const value = rawValue === true ? "true" : rawValue === false ? "false" : ""
    return (
      <select
        className="form-select form-select-sm"
        value={value}
        onChange={(e) => setBooleanTTFilter(field.id, e.target.value)}
      >
        <option value="">Any</option>
        <option value="true">Yes</option>
        <option value="false">No</option>
      </select>
    )
  }

  function renderFlatBomColumnFilter(field: FieldDefinition) {
    if (field.data_type === "boolean") return renderBomColumnFilter(field)
    const rawValue = filterMetaValue(ttFilters?.[field.id])
    const value = hasActiveFilterValue(rawValue) ? String(rawValue) : ""

    return (
      <input
        className="form-control form-control-sm"
        type="text"
        value={value}
        onChange={(e) => setTTFilterValue(field.id, e.target.value, "custom")}
        placeholder={fieldFilterPlaceholder(field)}
      />
    )
  }

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

function fileNameFromUrl(url: string): string {
  const text = String(url || "").trim();
  if (!text) return "";
  try {
    const parsed = new URL(text, window.location.origin);
    const parts = parsed.pathname.split("/").filter(Boolean);
    return decodeURIComponent(parts[parts.length - 1] || "");
  } catch {
    const clean = text.split("#", 1)[0].split("?", 1)[0];
    const parts = clean.split("/").filter(Boolean);
    return decodeURIComponent(parts[parts.length - 1] || "");
  }
}

function extensionFromFileRowOrUrl(file: FileRow, url: string): string {
  const explicit = String(file.ext || "").trim().toLowerCase();
  if (explicit) return explicit;
  const relName = String(file.name || file.rel_path || "").trim();
  const urlName = fileNameFromUrl(url);
  const source = relName || urlName;
  const idx = source.lastIndexOf(".");
  return idx >= 0 ? source.slice(idx + 1).toLowerCase() : "";
}

function isPdfLike(ext: string, url: string): boolean {
  const extNorm = String(ext || "").trim().toLowerCase();
  if (extNorm === "pdf") return true;
  return fileNameFromUrl(url).toLowerCase().endsWith(".pdf");
}

function isImageLike(ext: string, url: string): boolean {
  const extNorm = String(ext || "").trim().toLowerCase();
  if (["jpg", "jpeg", "png", "gif", "webp", "bmp", "svg"].includes(extNorm)) return true;
  const lowerName = fileNameFromUrl(url).toLowerCase();
  return [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"].some((suffix) => lowerName.endsWith(suffix));
}

function bestDatasheetUrl(f: FileRow): string {
  const direct = f.url || f.http_url || (Array.isArray(f.urls) ? f.urls[0] : "");
  if (direct) {
    const text = String(direct).trim();
    if (/^https?:\/\//i.test(text)) return text;
    try {
      const u = new URL(text, window.location.origin);
      if (u.origin === window.location.origin) return u.toString();
    } catch {
      if (text.startsWith("/")) return text;
    }
  }

  return bestUrl(f);
}

function isExternalDatasheetUrl(url: string): boolean {
  const text = String(url || "").trim();
  if (!text || !/^https?:\/\//i.test(text)) return false;
  try {
    return new URL(text).origin !== window.location.origin;
  } catch {
    return true;
  }
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

  function bomData(row: any): Record<string, any> {
    return row?.data ?? row ?? {};
  }

  function bomCellValue(row: any, fieldId: string): any {
    const data = bomData(row);
    return data?.[fieldId];
  }

  function filterMetaValue(filterMeta: any): any {
    if (!filterMeta || typeof filterMeta !== "object") return filterMeta;
    if ("value" in filterMeta) return filterMeta.value;

    const constraints = filterMeta.constraints;
    if (Array.isArray(constraints)) {
      const active = constraints.find((item) => {
        const value = item?.value;
        return value !== "" && value !== null && value !== undefined;
      });
      return active?.value;
    }

    return undefined;
  }

  function hasActiveFilterValue(value: any): boolean {
    return value !== "" && value !== null && value !== undefined;
  }

  function sharedPartHref(targetPn: string, targetRev: string) {
    if (!shareViewBase) return "#";
    const qs = new URLSearchParams();
    qs.set("pn", targetPn || "");
    qs.set("rev", targetRev || "");
    return `${shareViewBase}?${qs.toString()}`;
  }

  const thumbOnlyBody = (row: any) => {
    const data = bomData(row);
    const urls: string[] = Array.isArray(data?.thumb_urls) ? data.thumb_urls : [];
    return <ThumbImg urls={urls} maxH={32} maxW={48} />;
  };

  const pnBody = (row: any) => {
    const data = bomData(row);
    const bomPn = data?.part_number || data?.pn || "";
    const bomRev = data?.revision || data?.rev || "";
    const depth = Math.max(0, Number(data?._depth ?? 0));
    return (
      <span className="tt-pncell" style={depth ? { paddingLeft: `${depth * 0.8}rem` } : undefined}>
        {isSharedView ? (
          sharedAllowsChildren ? (
            <Link className="tt-pnlink" to={sharedPartHref(bomPn, bomRev)}>
              {bomPn}
            </Link>
          ) : (
            <span className="tt-pnlink">{bomPn}</span>
          )
        ) : (
          <a className="tt-pnlink" href={`/ui/part/${encodeURIComponent(bomPn)}?rev=${encodeURIComponent(bomRev)}`}>
            {bomPn}
          </a>
        )}
      </span>
    );
  };

  function renderSummaryField(field: FieldDefinition) {
    const value = summaryValue(field.id);
    if (field.data_type === "link") {
      const href = String(value || "").trim();
      return href ? (
        <a className="btn btn-outline-secondary btn-sm pd-file-btn" href={href} target="_blank" rel="noreferrer">
          {field.label}
        </a>
      ) : <span><strong>{field.label}:</strong> -</span>;
    }
    return <span><strong>{field.label}:</strong> {formatFieldValue(value)}</span>;
  }

  function renderBomCell(field: FieldDefinition, row: any) {
    const value = bomCellValue(row, field.id);
    if (field.id === "thumbnail") return thumbOnlyBody(row);
    if (field.id === "part_number") return pnBody(row);
    if (field.data_type === "link") {
      const href = String(value || "").trim();
      return href ? <a href={href} target="_blank" rel="noreferrer">Open</a> : "-";
    }
    return formatFieldValue(value);
  }

  function renderWhereUsedCell(field: FieldDefinition, row: WURow & Record<string, any>) {
    const value = row?.[field.id];
    if (field.id === "thumbnail") {
      return <ThumbImg urls={row.parent_thumb_urls} maxH={28} maxW={44} />;
    }
    if (field.id === "part_number") {
      return isSharedView
        ? row.part_number
        : <Link to={`/ui/part/${encodeURIComponent(row.part_number)}?rev=${encodeURIComponent(row.revision || "")}`}>{row.part_number}</Link>;
    }
    if (field.data_type === "link") {
      const href = String(value || "").trim();
      return href ? <a href={href} target="_blank" rel="noreferrer">Open</a> : "-";
    }
    return formatFieldValue(value);
  }

  useEffect(() => {
    (async () => {
      try {
        if (isSharedView) {
          const resp = await fetch(`${shareApiBase}/field-config`);
          if (!resp.ok) throw new Error(await resp.text());
          const payload = await resp.json();
          setFieldConfig(payload.config || null);
          setFieldPreferences(payload.user_preferences || { contexts: {} });
          setCanAdmin(false);
          return;
        }
        const resp = await loadFieldConfig();
        setFieldConfig(resp.config);
        setFieldPreferences(resp.user_preferences || { contexts: {} });
        setCanAdmin(!!resp.permissions?.can_admin);
      } catch {}
    })();
  }, [isSharedView, shareApiBase]);

  useEffect(() => {
    document.body.classList.add('wide-page');
    return () => {
      document.body.classList.remove('wide-page');
    };
  }, []);

  // ---- Load Part Detail ----
  useEffect(() => {
    let canceled = false;
    (async () => {
      setLoading(true);
      setRefreshMsg(null);
      setRefreshError(null);
      try {
        const detailUrl = isSharedView
          ? `${shareApiBase}/part_detail?pn=${encodeURIComponent(pn)}&rev=${encodeURIComponent(rev || "")}`
          : `/api/part_detail?pn=${encodeURIComponent(pn)}&rev=${encodeURIComponent(rev || "")}`;
        const r = await fetch(detailUrl);
        if (r.status === 403) { if (!canceled) { setForbidden(true); } return; }
        if (!r.ok) throw new Error(await r.text());
        const j = await r.json();
        if (canceled) return;

        const partAttrs = j.part?.attributes || j.part?.attrs || {};
        const partNotes = typeof j.part?.notes === "string" ? j.part.notes : "";
        setPart(
          j.part
            ? {
                part_number: j.part.part_number,
                description: j.part.description,
                revision: j.part.revision || "",
                notes: partNotes,
                category: j.part.category || "",
                uom: j.part.uom || "EA",
                process: j.part.process || "",
                processes: Array.isArray(j.part.processes) ? j.part.processes : [],
                field_values: j.part.field_values || {},
                attrs: partAttrs,
              }
            : null
        );
        setNotes(partNotes);
        setSavedNotes(partNotes);
        setNotesSavedOnce(false);
        setComments(Array.isArray(j.comments) ? j.comments : []);
        setUploaderProfile(j.uploader_profile || null);
        setApproverProfile(j.approver_profile || null);
        setPublicShareInfo(j.public_share || null);

        if (!isSharedView) {
        setArenaBaseUrl(String(j.arena_file_link_base_url || ""));}

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
            setSavedNotes("");
            setNotesSavedOnce(false);
            setComments([]);
            setUploaderProfile(null);
            setApproverProfile(null);
            setPublicShareInfo(null);
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
  }, [isSharedView, pn, rev, refreshTick, shareApiBase]);

  async function loadExtraFiles() {
    if (!pn) return;
    if (isSharedView) {
      setExtraFiles([]);
      setExtraError(null);
      setExtraLoading(false);
      return;
    }
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

  async function loadFilesOverview() {
    if (!pn) return;
    setFilesOverviewLoading(true);
    setFilesOverviewError(null);
    try {
      const qs = new URLSearchParams({ pn, rev: rev || "" });
      const url = isSharedView
        ? `${shareApiBase}/files_overview?${qs.toString()}`
        : `/api/parts/${encodeURIComponent(pn)}/files_overview?${qs.toString()}`;
      const resp = await fetch(url);
      if (resp.status === 403) {
        setFilesOverviewCurrent(null);
        setFilesOverviewOther([]);
        setFilesOverviewError("Forbidden");
        return;
      }
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();
      setFilesOverviewCurrent(data?.current_revision || null);
      setFilesOverviewOther(Array.isArray(data?.other_revisions) ? data.other_revisions : []);
    } catch (err: any) {
      setFilesOverviewCurrent(null);
      setFilesOverviewOther([]);
      setFilesOverviewError(err?.message || "Failed to load file visibility.");
    } finally {
      setFilesOverviewLoading(false);
    }
  }

  useEffect(() => {
    loadExtraFiles();
  }, [isSharedView, pn, revToken, refreshTick]);

  useEffect(() => {
    loadFilesOverview();
  }, [isSharedView, pn, rev, refreshTick, shareApiBase]);

  // ---- Load drawing source metadata + markup layer (never on public shares) ----
  useEffect(() => {
    if (isSharedView || !pn) {
      setDrawingSource(null);
      setMarkupLayer(null);
      setMarkupError(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setMarkupLoading(true);
      setMarkupError(null);
      try {
        const fetchRows = async (mode: "drawing" | "preview"): Promise<DrawingImageRow[]> => {
          const qs = new URLSearchParams({ pn, mode, rev: effectiveRev || "" });
          const r = await fetch(`/api/part_images?${qs.toString()}`);
          const rows = (r.ok ? await r.json() : []) as DrawingImageRow[];
          return Array.isArray(rows) ? rows : [];
        };
        // Exported drawing PNG preferred; otherwise the part's full-size
        // preview PNG (never the thumbnail) still allows markups.
        let source = (await fetchRows("drawing")).find((row) => row.source_file_id) || null;
        if (!source) {
          source = (await fetchRows("preview")).find((row) => row.source_file_id && row.image_urls?.length) || null;
        }
        if (cancelled) return;
        setDrawingSource(source);
        if (!source?.source_file_id) {
          setMarkupLayer(null);
          return;
        }
        const mq = new URLSearchParams({ rev: effectiveRev || "", source_file_id: source.source_file_id });
        const mr = await fetch(`/api/parts/${encodeURIComponent(pn)}/drawing-markups?${mq.toString()}`);
        const mj = await mr.json().catch(() => null);
        if (cancelled) return;
        if (!mr.ok || !mj?.ok) {
          setMarkupLayer(null);
          setMarkupError(
            mj?.message ||
              (mr.status === 403 ? "Not authorized to view drawing markups." : `Failed to load drawing markups (HTTP ${mr.status})`),
          );
          return;
        }
        setMarkupLayer(mj as MarkupLayer);
      } catch (e: any) {
        if (!cancelled) {
          setMarkupLayer(null);
          setMarkupError(e?.message || "Failed to load drawing markups");
        }
      } finally {
        if (!cancelled) setMarkupLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isSharedView, pn, effectiveRev, refreshTick]);

  const markupThreads = useMemo<MarkupThread[]>(() => markupLayer?.threads || [], [markupLayer]);

  // Load DocPack options when pn/rev/depth changes
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        if (isSharedView && !sharedAllowsDocpacks) {
          if (!cancelled) setDocOpts({ file_types: [], processes: [], markup_document_count: 0 });
          return;
        }
        const optionsUrl = isSharedView
          ? `${shareApiBase}/docpacks/options?pn=${encodeURIComponent(pn)}&rev=${encodeURIComponent(rev || "")}&depth=${depth}`
          : `/api/docpacks/options?pn=${encodeURIComponent(pn)}&rev=${encodeURIComponent(rev || "")}&depth=${depth}`;
        const r = await fetch(optionsUrl);
        if (r.status === 403) { if (!cancelled) setForbidden(true); return; }
        if (!r.ok) return;
        const j = await r.json();
        if (cancelled) return;
        const file_types = Array.isArray(j.file_types) ? j.file_types : [];
        const processes = Array.isArray(j.processes) ? j.processes : [];
        setDocOpts({ file_types, processes, markup_document_count: Number(j.markup_document_count || 0) });
        if (selTypes.size === 0 && file_types.length) setSelTypes(new Set(file_types));
        if (selProcesses.size === 0 && processes.length) setSelProcesses(new Set(processes));
      } catch {}
    })();
    return () => { cancelled = true };
  }, [depth, isSharedView, pn, rev, shareApiBase, sharedAllowsDocpacks]);

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
        const rootUrl = isSharedView
          ? `${shareApiBase}/bom_tree?pn=${encodeURIComponent(pn)}&rev=${encodeURIComponent(rev || "")}&withThumb=1`
          : `/api/bom_tree?pn=${encodeURIComponent(pn)}&rev=${encodeURIComponent(rev || "")}&withThumb=1`;
        const r = await fetch(rootUrl);
        if (r.status === 403) { if (!cancelled) setForbidden(true); return; }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const root: TreeNode[] = asArr(await r.json());
        if (cancelled) return;
        if (!root.length) {
          setBomNodes([]);
          setBomExpanded({});
          return;
        }

        const rootNode = withBomOccurrenceKeys(root)[0] as any;
        const rootPn = (rootNode?.data?.pn || pn) as string;
        const rootRev = (rootNode?.data?.rev || "") as string;

        const childUrl = isSharedView
          ? `${shareApiBase}/bom_tree?parent=${encodeURIComponent(rootPn)}&parent_rev=${encodeURIComponent(rootRev)}&withThumb=1`
          : `/api/bom_tree?parent=${encodeURIComponent(rootPn)}&parent_rev=${encodeURIComponent(rootRev)}&withThumb=1`;
        const r2 = await fetch(childUrl);
        if (!r2.ok) throw new Error(`HTTP ${r2.status}`);
        let kids: TreeNode[] = withBomOccurrenceKeys(asArr(await r2.json()), String(rootNode?.key || "bom"));

        kids = annotateDepth(kids, 0, String(rootNode?.key ?? rootPn));
        if (!cancelled) {
          setBomNodes(kids);
          setBomExpanded({});
        }
      } catch (e) {
        console.error("bom_tree root (detail) failed", e);
        if (!cancelled) {
          setBomNodes([]);
          setBomExpanded({});
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isSharedView, pn, rev, refreshTick, shareApiBase]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setFlatBomLoading(true);
      try {
        const flatUrl = isSharedView
          ? `${shareApiBase}/bom_flat?pn=${encodeURIComponent(pn)}&rev=${encodeURIComponent(rev || "")}`
          : `/api/bom_flat?pn=${encodeURIComponent(pn)}&rev=${encodeURIComponent(rev || "")}`;
        const r = await fetch(flatUrl);
        if (r.status === 403) {
          if (!cancelled) setForbidden(true);
          return;
        }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const rows = asArr<FlatBomRow>(await r.json());
        if (!cancelled) setFlatBomRows(rows);
      } catch (err) {
        console.error("bom_flat failed", err);
        if (!cancelled) setFlatBomRows([]);
      } finally {
        if (!cancelled) setFlatBomLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isSharedView, pn, rev, refreshTick, shareApiBase]);

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
      const url = isSharedView
        ? `${shareApiBase}/bom_tree?parent=${encodeURIComponent(parentPn)}&parent_rev=${encodeURIComponent(parentRev)}&withThumb=1`
        : `/api/bom_tree?parent=${encodeURIComponent(parentPn)}&parent_rev=${encodeURIComponent(parentRev)}&withThumb=1`;
      const r = await fetch(url);
      if (r.status === 403) { setForbidden(true); return; }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const kids: TreeNode[] = withBomOccurrenceKeys(asArr(await r.json()), key);

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

      const node = findNode(nextTree, key);
      if (!node) continue;

      // If we don't have children yet, try to fetch them
      if (!node.children || (node.children as TreeNode[]).length === 0) {
        try {
          const parentNode2 = findNode(nextTree, key);
          const parentPn2 = (parentNode2 as any)?.data?.pn || key;
          const parentRev2 = (parentNode2 as any)?.data?.rev || "";
          const url = isSharedView
            ? `${shareApiBase}/bom_tree?parent=${encodeURIComponent(parentPn2)}&parent_rev=${encodeURIComponent(parentRev2)}&withThumb=1`
            : `/api/bom_tree?parent=${encodeURIComponent(parentPn2)}&parent_rev=${encodeURIComponent(parentRev2)}&withThumb=1`;
          const r = await fetch(url);
          if (r.ok) {
            let kids: TreeNode[] = withBomOccurrenceKeys(asArr(await r.json()), key);
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
    const severity = String(node?.data?.pending_review_severity || "");
    return {
      [`tt-depth-${d}`]: true,
      [`parts-review-row parts-review-row--${severity}`]: Boolean(severity),
    };
  };

  const flatReviewRowClassName = (row: FlatBomRow) =>
    row.has_pending_reviews ? `parts-review-row parts-review-row--${row.pending_review_severity || "low"}` : "";

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
    PREVIEW_FORMAT_PRIORITY.forEach(addGroup);
    return options;
  }, [fileGroups]);

  const datasheetOptions = useMemo(() => {
    const items = fileGroups["datasheet"] || [];
    return items.reduce<DatasheetOption[]>((options, file, idx) => {
      const url = bestDatasheetUrl(file);
      if (!url) return options;
      const ext = extensionFromFileRowOrUrl(file, url);
      const isExternal = isExternalDatasheetUrl(url);
      const label =
        file.name ||
        (file.rel_path ? file.rel_path.split("/").pop() : "") ||
        fileNameFromUrl(url) ||
        `datasheet ${idx + 1}`;
      const keySource = file.rel_path || file.name || url || `datasheet ${idx + 1}`;
      options.push({
        key: `datasheet:${keySource}`,
        url,
        ext,
        label,
        file,
        isExternal,
        canPreview: !isExternal,
      });
      return options;
    }, []);
  }, [fileGroups]);

  const firstLinks = useMemo(() => {
    const pick = (k: string, urlResolver: (file: FileRow) => string = bestUrl) => {
      const arr = fileGroups[k] || [];
      const href = arr.length ? urlResolver(arr[0]) : "";
      return href ? { href, count: arr.length } : null;
    };
    return {
      edr: pick("edr"),
      step: pick("step"),
      pdf: pick("pdf"),
      dxf: pick("dxf"),
      datasheet: pick("datasheet", bestDatasheetUrl),
      threeMF: pick("3mf"),
      ply: pick("ply"),
      stl: pick("stl"),
    };
  }, [fileGroups]);

  const pdfHref = firstLinks.pdf?.href || "";
  const currentFileRows = useMemo(() => asArr<FileOverviewRow>(filesOverviewCurrent?.files), [filesOverviewCurrent]);
  const otherRevisionFileCount = useMemo(
    () => filesOverviewOther.reduce((sum, section) => sum + asArr<FileOverviewRow>(section?.files).length, 0),
    [filesOverviewOther]
  );

  useEffect(() => {
    if (threeDOptions.length === 0) {
      setSelectedPreviewKey("");
      return;
    }
    if (threeDOptions.some((opt) => opt.key === selectedPreviewKey)) {
      return;
    }
    const preferred =
      threeDOptions.find((opt) => opt.format === "ply") || threeDOptions[0];
    setSelectedPreviewKey(preferred?.key || "");
  }, [threeDOptions, selectedPreviewKey]);

  const activePreview = useMemo(() => {
    if (threeDOptions.length === 0) return null;
    return threeDOptions.find((opt) => opt.key === selectedPreviewKey) || threeDOptions[0] || null;
  }, [threeDOptions, selectedPreviewKey]);

  useEffect(() => {
    if (datasheetOptions.length === 0) {
      setSelectedDatasheetKey("");
      return;
    }
    if (datasheetOptions.some((opt) => opt.key === selectedDatasheetKey)) {
      return;
    }
    const preferred = datasheetOptions.find((opt) => opt.canPreview) || datasheetOptions[0];
    setSelectedDatasheetKey(preferred?.key || "");
  }, [datasheetOptions, selectedDatasheetKey]);

  const activeDatasheet = useMemo(() => {
    if (datasheetOptions.length === 0) return null;
    return datasheetOptions.find((opt) => opt.key === selectedDatasheetKey) || datasheetOptions[0] || null;
  }, [datasheetOptions, selectedDatasheetKey]);

  const hasDatasheetPreview = datasheetOptions.length > 0;

  const previewUrl = activePreview?.url ?? null;
  const previewFormat = activePreview?.format ?? null;

  const attrs = useMemo(() => {
    const raw = (part?.attrs || {}) as Record<string, any>;

    // only non-empty
    const skipKeys = new Set(["comments_search"]);
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

  const filteredAttrs = useMemo(() => {
    const query = attributeSearch.trim().toLowerCase();
    if (!query) return attrs;
    return attrs.filter(([key, value]) =>
      `${key} ${String(value)}`.toLowerCase().includes(query)
    );
  }, [attributeSearch, attrs]);

  // Processes: normalize and deduplicate
  const processes: string[] = useMemo(() => {
    const direct = Array.isArray(part?.processes) ? part.processes : []
    const source = direct.length ? direct : rawSummaryValue("process")
    return processTokens(source)
      .filter((x, i, arr) => x && arr.indexOf(x) === i);
  }, [part, rawSummaryValue]);

  const isBlankish = (value: any, allowNa = false) => {
    if (value === null || value === undefined) return true
    const text = String(value).trim().toLowerCase()
    if (allowNa && (text === "n/a" || text === "na")) return false
    return text === "" || text === "none" || text === "null"
  }

  const materialValue = rawSummaryValue("material")
  const finishValue = rawSummaryValue("finish")
  const descriptionValue = rawSummaryValue("description")
  const revisionValue = rawSummaryValue("revision")
  const categoryValue = rawSummaryValue("category")
  const linkValue = rawSummaryValue("link")
  const summaryFields = fieldConfig ? contextFields(fieldConfig, "part_detail_summary") : FALLBACK_SUMMARY_FIELDS
  const bomFields = fieldConfig ? contextFields(fieldConfig, "bom_tree") : FALLBACK_BOM_FIELDS
  const whereUsedFields = fieldConfig ? contextFields(fieldConfig, "where_used") : FALLBACK_WHERE_USED_FIELDS
  const excelFields = fieldConfig ? contextFields(fieldConfig, "excel_bom") : []
  const arenaFields = fieldConfig ? contextFields(fieldConfig, "arena_bom") : []
  const defaultSummaryIds = fieldConfig ? defaultFieldIds(fieldConfig, "part_detail_summary") : ["material", "finish", "mass", "process"]
  const defaultBomIds = fieldConfig ? defaultFieldIds(fieldConfig, "bom_tree") : ["thumbnail", "part_number", "revision", "description", "process", "finish", "material", "qty"]
  const defaultWhereUsedIds = fieldConfig ? defaultFieldIds(fieldConfig, "where_used") : ["thumbnail", "part_number", "revision", "description", "qty"]
  const defaultExcelIds = fieldConfig ? defaultFieldIds(fieldConfig, "excel_bom") : []
  const defaultArenaIds = fieldConfig ? defaultFieldIds(fieldConfig, "arena_bom") : []
  const requiredSummaryIds = fieldConfig ? requiredFieldIds(fieldConfig, "part_detail_summary") : []
  const requiredBomIds = fieldConfig ? requiredFieldIds(fieldConfig, "bom_tree") : ["part_number"]
  const requiredWhereUsedIds = fieldConfig ? requiredFieldIds(fieldConfig, "where_used") : ["part_number"]
  const requiredExcelIds = fieldConfig ? requiredFieldIds(fieldConfig, "excel_bom") : ["part_number", "revision", "description", "total_qty"]
  const requiredArenaIds = fieldConfig ? requiredFieldIds(fieldConfig, "arena_bom") : []
  const selectedSummaryIds = fieldConfig ? selectedFieldIds(fieldConfig, fieldPreferences, "part_detail_summary") : defaultSummaryIds
  const selectedBomIds = fieldConfig ? selectedFieldIds(fieldConfig, fieldPreferences, "bom_tree") : defaultBomIds
  const selectedWhereUsedIds = fieldConfig ? selectedFieldIds(fieldConfig, fieldPreferences, "where_used") : defaultWhereUsedIds
  const selectedExcelIds = fieldConfig ? selectedFieldIds(fieldConfig, fieldPreferences, "excel_bom") : defaultExcelIds
  const selectedArenaIds = fieldConfig ? selectedFieldIds(fieldConfig, fieldPreferences, "arena_bom") : defaultArenaIds
  const whereUsedSelectorFieldId = selectedWhereUsedIds.includes("thumbnail") ? "thumbnail" : selectedWhereUsedIds[0]
  const bomSelectorFieldId = selectedBomIds.includes("thumbnail") ? "thumbnail" : selectedBomIds[0]

  function renderBomColumnsSelector() {
    if (isSharedView || !bomFields.length) return null
    return (
      <FieldSelector
        title="BOM fields"
        buttonLabel="Columns"
        buttonIcon="pi pi-table"
        buttonClassName="btn btn-sm d-inline-flex align-items-center gap-1 parts-columns-trigger"
        menuAlign="start"
        availableFields={bomFields}
        selectedIds={selectedBomIds}
        requiredIds={requiredBomIds}
        onChange={(fieldIds) => persistFieldSelection("bom_tree", fieldIds)}
        onReset={() => persistFieldSelection("bom_tree", defaultBomIds)}
      />
    )
  }
  const excelUseDefault = fieldPreferences?.contexts?.excel_bom?.use_default ?? true
  const arenaUseDefault = fieldPreferences?.contexts?.arena_bom?.use_default ?? true
  const arenaAvailableFields = useMemo(
    () => arenaFields.filter((field) => !["thumbnail", "part_number", "description", "qty", "level"].includes(field.id)),
    [arenaFields],
  )
  const arenaVisibleFieldIds = useMemo(() => new Set(arenaAvailableFields.map((field) => field.id)), [arenaAvailableFields])
  const defaultVisibleArenaIds = useMemo(() => {
    return defaultArenaIds.filter((fieldId) => arenaVisibleFieldIds.has(fieldId))
  }, [arenaVisibleFieldIds, defaultArenaIds])
  const visibleRequiredArenaIds = useMemo(() => {
    return requiredArenaIds.filter((fieldId) => arenaVisibleFieldIds.has(fieldId))
  }, [arenaVisibleFieldIds, requiredArenaIds])
  const visibleSelectedArenaIds = useMemo(() => {
    return selectedArenaIds.filter((fieldId) => arenaVisibleFieldIds.has(fieldId))
  }, [arenaVisibleFieldIds, selectedArenaIds])
  const arenaSuggestedFieldIds = useMemo(() => {
    const allowed = new Set(arenaAvailableFields.map((field) => field.id))
    const source = defaultVisibleArenaIds.length ? defaultVisibleArenaIds : selectedExcelIds.length ? selectedExcelIds : defaultExcelIds
    return source.filter((fieldId) => allowed.has(fieldId))
  }, [arenaAvailableFields, defaultExcelIds, defaultVisibleArenaIds, selectedExcelIds])
  const hasManagementActions = canAdmin || canPartsEdit || canPartsDelete

  function attrsValue(fieldId: string) {
    const values = collectRecordValues(
      part?.attrs || {},
      canonicalFieldAliases(fieldConfig, fieldId, partDetailFieldFallbackAliases(fieldId)),
    )
    return values.find((value) => value !== undefined)
  }

  function rawSummaryValue(fieldId: string) {
    const fieldValue = readRecordValue(part?.field_values || {}, fieldId)
    if (fieldValue !== undefined) return fieldValue
    const topLevelValue = readRecordValue(part ? (part as unknown as Record<string, unknown>) : undefined, fieldId)
    if (topLevelValue !== undefined) return topLevelValue
    return attrsValue(fieldId)
  }

  const bomFieldMap = useMemo(
    () => new Map(bomFields.map((field) => [field.id, field] as const)),
    [bomFields],
  )
  const flatFilteredRows = useMemo(() => {
    const activeEntries = Object.entries(ttFilters || {}).filter(([fieldId, filterMeta]) => {
      if (fieldId === "pending_review_severity") return hasActiveFilterValue(filterMetaValue(filterMeta));
      const field = bomFieldMap.get(fieldId);
      if (!field || field.id === "thumbnail") return false;
      return hasActiveFilterValue(filterMetaValue(filterMeta));
    });

    if (!activeEntries.length) return flatBomRows;

    return flatBomRows.filter((row) =>
      activeEntries.every(([fieldId, filterMeta]) => {
        if (fieldId === "pending_review_severity") {
          return reviewFilterMatches(row.pending_review_severity, filterMetaValue(filterMeta));
        }
        const field = bomFieldMap.get(fieldId)
        if (!field) return true;

        return matchesFieldFilter(
          field,
          bomCellValue(row, fieldId),
          filterMetaValue(filterMeta),
        );
      }),
    )
  }, [bomFieldMap, flatBomRows, ttFilters])

  async function persistFieldPreferences(nextPrefs: FieldPreferences) {
    setFieldPreferences(nextPrefs)
    try {
      const resp = await saveFieldPreferences(nextPrefs)
      setFieldPreferences(resp.settings.field_preferences || nextPrefs)
    } catch {}
  }

  async function persistFieldSelection(contextName: string, fieldIds: string[]) {
    if (!fieldConfig) return
    const nextPrefs = updateContextSelection(fieldConfig, fieldPreferences, contextName, fieldIds)
    await persistFieldPreferences(nextPrefs)
  }

  async function persistFieldMode(contextName: string, useDefault: boolean) {
    const nextPrefs = updateContextMode(fieldPreferences, contextName, useDefault)
    await persistFieldPreferences(nextPrefs)
  }

  async function persistFieldSelectionAndMode(contextName: string, fieldIds: string[], useDefault: boolean) {
    if (!fieldConfig) return
    let nextPrefs = updateContextSelection(fieldConfig, fieldPreferences, contextName, fieldIds)
    nextPrefs = updateContextMode(nextPrefs, contextName, useDefault)
    await persistFieldPreferences(nextPrefs)
  }

  async function downloadArenaCsv(endpoint: string, body: Record<string, any>, kind: "bom" | "links", fallbackName: string) {
    setArenaBusy(kind)
    setArenaError(null)
    try {
      const resp = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!resp.ok) {
        let message = `HTTP ${resp.status}`
        const raw = await resp.text()
        try {
          const payload = JSON.parse(raw)
          message = payload?.error || payload?.message || message
        } catch {
          message = raw || message
        }
        throw new Error(message)
      }
      const blob = await resp.blob()
      const disp = resp.headers.get("Content-Disposition") || ""
      const match = disp.match(/filename="?([^";]+)"?/i)
      const filename = (match ? match[1] : fallbackName).replace(/\s+/g, "_")
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err: any) {
      setArenaError(err?.message || "Arena export failed.")
    } finally {
      setArenaBusy(null)
    }
  }

  async function handleArenaBomExport() {
    if (!pn) return
    await downloadArenaCsv(
      `/api/parts/${encodeURIComponent(pn)}/export/arena_bom`,
      {
        rev: effectiveRev || "",
        field_ids: !arenaUseDefault ? visibleSelectedArenaIds : [],
      },
      "bom",
      `${pn}_${effectiveRev || "no_rev"}_arena_bom.csv`,
    )
  }

  async function handleArenaFileLinksExport() {
    if (!pn) return
    if (!arenaBaseUrl.trim()) {
      setArenaError("BASE URL is required for Arena file links.")
      return
    }
    await downloadArenaCsv(
      `/api/parts/${encodeURIComponent(pn)}/export/arena_file_links`,
      {
        rev: effectiveRev || "",
        base_url: arenaBaseUrl.trim(),
      },
      "links",
      `${pn}_${effectiveRev || "no_rev"}_arena_file_links.csv`,
    )
  }

  async function loadShareLinks() {
    if (!canAdmin || isSharedView || !pn) return
    setShareLoading(true)
    setShareError(null)
    try {
      const qs = new URLSearchParams({ rev: effectiveRev || "" })
      const resp = await fetch(`/api/parts/${encodeURIComponent(pn)}/shares?${qs.toString()}`)
      if (!resp.ok) throw new Error(await resp.text())
      const data = await resp.json()
      setShareLinks(Array.isArray(data?.shares) ? data.shares : [])
    } catch (err: any) {
      setShareLinks([])
      setShareError(err?.message || "Failed to load share links.")
    } finally {
      setShareLoading(false)
    }
  }

  async function createShareLink() {
    if (!canAdmin || isSharedView || !pn) return
    setShareCreateBusy(true)
    setShareCreateError(null)
    setShareCopied(false)
    try {
      const resp = await fetch(`/api/parts/${encodeURIComponent(pn)}/shares`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rev: effectiveRev || "",
          expires_in_days: Number(shareExpiresDays || 30),
          allow_children: shareAllowChildren,
          allow_docpacks: shareAllowExtended,
          allow_attributes: shareAllowExtended,
        }),
      })
      if (!resp.ok) throw new Error(await resp.text())
      const data = await resp.json()
      setShareCreateUrl(String(data?.url || ""))
      await loadShareLinks()
    } catch (err: any) {
      setShareCreateError(err?.message || "Failed to create share link.")
    } finally {
      setShareCreateBusy(false)
    }
  }

  async function copyShareLink() {
    if (!shareCreateUrl) return
    try {
      await navigator.clipboard.writeText(shareCreateUrl)
      setShareCopied(true)
    } catch {
      setShareCopied(false)
    }
  }

  async function revokeShareLink(shareRow: PartShareRow) {
    if (!canAdmin || isSharedView || !pn || !shareRow?.id) return
    setShareRevokingId(shareRow.id)
    setShareError(null)
    try {
      const resp = await fetch(`/api/parts/${encodeURIComponent(pn)}/shares/${encodeURIComponent(shareRow.id)}`, {
        method: "DELETE",
      })
      if (!resp.ok) throw new Error(await resp.text())
      await loadShareLinks()
    } catch (err: any) {
      setShareError(err?.message || "Failed to revoke share link.")
    } finally {
      setShareRevokingId(null)
    }
  }

  useEffect(() => {
    if (!canAdmin || isSharedView) {
      setShareLinks([])
      setShareError(null)
      return
    }
    loadShareLinks()
  }, [canAdmin, isSharedView, pn, effectiveRev])

  function summaryValue(fieldId: string) {
    if (fieldId === "approved") return approvedInfo.approved
    if (fieldId === "approved_by") return approvedInfo.approved ? (approverIdentity || approvedInfo.label || "") : ""
    if (fieldId === "process" && processes.length) return processes
    return rawSummaryValue(fieldId)
  }

  const approvedAliases = useMemo(
    () => canonicalFieldAliases(fieldConfig, "approved", ["approved"]),
    [fieldConfig],
  )
  const approvedByAliases = useMemo(
    () => canonicalFieldAliases(fieldConfig, "approved_by", ["approved_by", "approvedby", "approved"]),
    [fieldConfig],
  )

  const approvedInfo = useMemo(() => {
    const fieldValues = part?.field_values || {}
    const attrs = part?.attrs || {}
    const explicitApproved = readRecordValue(fieldValues, "approved")
    const explicitBoolean = typeof explicitApproved === "boolean" ? explicitApproved : null
    const attrApprovedValues = collectRecordValues(attrs, approvedAliases)
    const fieldApprovedBy = readRecordValue(fieldValues, "approved_by")
    const attrApprovedByValues = collectRecordValues(attrs, approvedByAliases)
    const identitySource = [fieldApprovedBy, ...attrApprovedByValues].find((value) => !!approvalIdentityText(value))
    const label = approvalIdentityText(identitySource)

    if (explicitBoolean !== null) {
      return { approved: explicitBoolean, label: explicitBoolean ? label : "" }
    }

    const candidates = [explicitApproved, ...attrApprovedValues, fieldApprovedBy, ...attrApprovedByValues]
    const explicitStatuses = candidates
      .map((value) => explicitApprovalStatus(value))
      .filter((value): value is boolean => value !== null)

    if (explicitStatuses.includes(false)) return { approved: false, label: "" }
    if (explicitStatuses.includes(true)) return { approved: true, label: label || "" }

    const hasApprovalValue = candidates.some((value) => approvalStatus(value) === true)
    return { approved: hasApprovalValue, label: hasApprovalValue ? label || "" : "" }
  }, [approvedAliases, approvedByAliases, part])

  const uploaderIdentity = useMemo(() => {
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

  const approverIdentity = useMemo(() => {
    const fieldApprovedBy = readRecordValue(part?.field_values || {}, "approved_by")
    const attrApprovedByValues = collectRecordValues(part?.attrs || {}, approvedByAliases)
    return approvalIdentityText([fieldApprovedBy, ...attrApprovedByValues])
  }, [approvedByAliases, part])

  const uploaderName = useMemo(() => identityLabel(uploaderProfile, uploaderIdentity), [uploaderProfile, uploaderIdentity])
  const approverName = useMemo(
    () => (approvedInfo.approved ? identityLabel(approverProfile, approvedInfo.label || approverIdentity) : ""),
    [approvedInfo.approved, approvedInfo.label, approverIdentity, approverProfile],
  )

  const missingCritical = useMemo(() => {
    const missing: string[] = []
    const pnValue = (part?.part_number || pn || "").toString().trim()
    if (!pnValue) missing.push("partnumber")
    const desc = String(descriptionValue ?? "").trim()
    if (!desc) missing.push("description")
    const rev = String(revisionValue ?? "").trim()
    if (!rev) missing.push("revision")
    if (isBlankish(materialValue, true)) missing.push("material")
    if (isBlankish(finishValue, true)) missing.push("finish")
    if (!processes.length) missing.push("process")
    return missing
  }, [descriptionValue, finishValue, materialValue, part, pn, processes, revisionValue])

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
  const hasBomContent = bomNodes.length > 0 || flatBomRows.length > 0 || flatBomLoading;

  // ---------- Render ----------
  const [tabIndex, setTabIndex] = useState(0)
  useEffect(() => {
    setTabIndex(0)
    setShareCreateUrl("")
    setShareCopied(false)
  }, [effectiveRev, isSharedView, pn])
  // If there is no drawing preview image but there is a PDF, we still
  // consider that we have a drawing. Otherwise, hide the Drawing tab and
  // default to All attributes.
  const hasDrawing = Boolean(pdfHref) || (drawingUrls?.length || 0) > 0
  const hasMarkups = (markupLayer?.canvas_json?.objects?.length || 0) > 0
  type ReviewIndicator = "note" | "low" | "normal" | "high" | null
  const reviewIndicator = useMemo<ReviewIndicator>(() => {
    const priorities = [
      ...comments.filter((comment) => comment.status !== "resolved").map((comment) => comment.priority || "low"),
      ...markupThreads.filter((thread) => thread.status === "open").map((thread) => thread.priority),
    ]
    if (priorities.includes("high")) return "high"
    if (priorities.includes("normal")) return "normal"
    if (priorities.length || hasMarkups) return "low"
    return null
  }, [comments, hasMarkups, markupThreads])
  // Notes live on the Attributes & Notes tab now.
  const notesIndicator: ReviewIndicator = notes.trim() ? "note" : null
  const reviewTabIndex =
    Number(hasDrawing) +
    Number(hasDatasheetPreview) +
    Number(!isSharedView || sharedAllowsAttributes) +
    Number(threeDOptions.length > 0) +
    1 + // Files
    Number(!isSharedView || sharedAllowsDocpacks) +
    Number(!isSharedView && versions.length > 1) +
    Number(!isSharedView && jobsOrders.length > 0)
  const notesDirty = notes !== savedNotes

  function tabHeader(label: string, icon: string, indicator: ReviewIndicator = null) {
    const indicatorIcon = indicator === "note" ? "pi-file-edit" : icon
    return (
      <span className={`pd-tab-label${indicator ? ` pd-tab-label--${indicator}` : ""}`}>
        <i className={`pi ${indicatorIcon}`} aria-hidden="true" />
        <span>{label}</span>
      </span>
    )
  }

  useEffect(() => {
    if (!hasDrawing && hasDatasheetPreview) {
      setTabIndex(0)
    }
  }, [effectiveRev, hasDrawing, hasDatasheetPreview, isSharedView, pn])

  useEffect(() => {
    if (!isSharedView && sp.get("tab") === "reviews") {
      setTabIndex(reviewTabIndex)
    }
  }, [isSharedView, reviewTabIndex, sp])

  async function saveNotes(nextNotes = notes) {
    if (!canPartsNote || !part) return
    setNotesSaving(true)
    setNotesError(null)
    try {
      const resp = await fetch(`/api/parts/${encodeURIComponent(part.part_number)}/notes?rev=${encodeURIComponent(part.revision || "")}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes: nextNotes, rev: part.revision || "" }),
      })
      if (!resp.ok) {
        throw new Error(await resp.text())
      }
      const j = await resp.json()
      const persisted = String(j.notes || "")
      setNotes(persisted)
      setSavedNotes(persisted)
      setNotesSavedOnce(true)
    } catch (e: any) {
      setNotesError(e?.message || "Failed to save notes")
    } finally {
      setNotesSaving(false)
    }
  }

  function reviewFilterMatches(value: unknown, filterValue: unknown) {
    const filter = String(filterValue || "").toLowerCase();
    const severity = String(value || "").toLowerCase();
    if (!filter) return true;
    if (filter === "pending") return Boolean(severity);
    if (filter === "none") return !severity;
    return severity === filter;
  }

  function renderReviewFilter() {
    const value = String(filterMetaValue(ttFilters?.pending_review_severity) || "");
    return (
      <select
        className="form-select form-select-sm"
        aria-label="Filter BOM by pending reviews"
        value={value}
        onChange={(e) => setTTFilterValue("pending_review_severity", e.target.value, "custom")}
      >
        <option value="">Any</option>
        <option value="pending">Pending</option>
        <option value="high">High</option>
        <option value="normal">Normal</option>
        <option value="low">Low</option>
        <option value="none">None</option>
      </select>
    );
  }

  function bomReviewIndicator(row: any) {
    const data = bomData(row);
    if (!data?.has_pending_reviews) return <span className="text-muted">—</span>;
    const severity = data.pending_review_severity || "low";
    return (
      <span
        className={`parts-review-indicator parts-review-indicator--${severity}`}
        title={`${data.pending_review_count || 0} pending review item(s), ${severity} priority`}
      >
        <span aria-hidden="true" />
        {data.pending_review_count || 0}
      </span>
    );
  }

  async function clearNotes() {
    if (!notes && !savedNotes) return
    if (!window.confirm("Erase these notes? This cannot be undone.")) return
    setNotes("")
    await saveNotes("")
  }

  // Comment operations for the unified review panel (comments + markup
  // reviews share one list inside the markup workspace).
  async function commentRequest(path: string, body: Record<string, any>): Promise<any | null> {
    if (!canPartsNote || !part) return null
    setCommentSaving(true)
    setCommentError(null)
    try {
      const resp = await fetch(`/api/parts/${encodeURIComponent(part.part_number)}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rev: part.revision || "", ...body }),
      })
      const j = await resp.json().catch(() => null)
      if (!resp.ok || !j?.ok) throw new Error(j?.error || j?.message || `HTTP ${resp.status}`)
      return j
    } catch (e: any) {
      setCommentError(e?.message || "Comment request failed")
      return null
    } finally {
      setCommentSaving(false)
    }
  }

  function replaceComment(updated: CommentRow) {
    setComments((current) => current.map((row) => (row.id === updated.id ? updated : row)))
  }

  async function addComment(text: string, priority: string): Promise<boolean> {
    const trimmed = text.trim()
    if (!trimmed) return false
    const j = await commentRequest("/comments", { text: trimmed, priority: priority || undefined })
    if (!j?.comment) return false
    setComments((prev) => [...prev, j.comment as CommentRow])
    return true
  }

  async function replyComment(commentId: string, text: string): Promise<boolean> {
    const j = await commentRequest("/comments/reply", { id: commentId, text })
    if (!j?.comment) return false
    replaceComment(j.comment as CommentRow)
    return true
  }

  async function setCommentStatus(commentId: string, status: "open" | "resolved"): Promise<boolean> {
    const j = await commentRequest("/comments/status", { id: commentId, status })
    if (!j?.comment) return false
    replaceComment(j.comment as CommentRow)
    return true
  }

  async function setCommentPriority(commentId: string, priority: string): Promise<boolean> {
    const j = await commentRequest("/comments/priority", { id: commentId, priority })
    if (!j?.comment) return false
    replaceComment(j.comment as CommentRow)
    return true
  }

  async function deleteComment(comment: CommentRow): Promise<boolean> {
    if (!window.confirm("Erase this comment? This cannot be undone.")) return false
    const j = await commentRequest("/comments/delete", {
      id: comment.id || undefined,
      ts: comment.ts,
      text: comment.text,
    })
    if (!j) return false
    setComments(Array.isArray(j.comments) ? j.comments : [])
    return true
  }

  async function handleRefreshFiles() {
    if (!canPartsEdit || !part) return
    setRefreshBusy(true)
    setRefreshError(null)
    setRefreshMsg(null)
    try {
      const qs = new URLSearchParams({ rev: part.revision || "" })
      if (refreshIncludeChildren) qs.set("recursive", "1")
      const resp = await fetch(`/api/parts/${encodeURIComponent(part.part_number)}/refresh_files?${qs.toString()}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rev: part.revision || "", recursive: refreshIncludeChildren }),
      })
      const j = await resp.json().catch(() => ({}))
      if (!resp.ok) {
        const msg = j?.error || `HTTP ${resp.status}`
        throw new Error(msg)
      }
      const found = j?.files_found ?? 0
      const upserts = j?.artifacts_upserted ?? 0
      const removed = j?.artifacts_removed ?? 0
      const thumbs = j?.thumbnails_generated ?? 0
      const partsRefreshed = j?.parts_refreshed ?? 1
      const removedNote = removed > 0 ? ` Removed ${removed} entr${removed === 1 ? "y" : "ies"} for deleted file(s).` : ""
      if (found <= 0) {
        setRefreshMsg(
          (refreshIncludeChildren
            ? `No matching files found. Parts refreshed: ${partsRefreshed}.`
            : "No matching files found for this part.") + removedNote
        )
      } else if (upserts <= 0 && removed <= 0) {
        setRefreshMsg(`No new files found. ${found} file(s) already registered. Parts refreshed: ${partsRefreshed}.`)
      } else {
        setRefreshMsg(`Found ${found} file(s). Updated ${upserts}. Thumbs ${thumbs}. Parts refreshed: ${partsRefreshed}.${removedNote}`)
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
    let extra = deleteChildren
      ? "\n\nThis will also delete BOM children that are not used in any other assembly."
      : "";
    if (deleteFilesToo) {
      extra += "\n\nRelated files (PDF, STEP, images, extra files, thumbnails) will be PERMANENTLY deleted from the server storage.";
    }
    const ok = window.confirm(`Delete part ${label}? This cannot be undone.${extra}`);
    if (!ok) return;
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      const resp = await fetch("/api/part_delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pn: part.part_number,
          rev: part.revision || "",
          delete_children: deleteChildren,
          delete_files: deleteFilesToo,
        }),
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
      await loadFilesOverview();
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
      await loadFilesOverview();
    } catch (err) {
      console.error(err);
    } finally {
      setExtraDeleteBusy(null);
    }
  }

  function fileRowActions(row: FileOverviewRow, allowManageCurrent = false) {
    return (
      <div className="d-flex gap-2 flex-wrap">
        {row.url ? (
          <a className="btn btn-sm btn-outline-secondary" href={row.url} target="_blank" rel="noreferrer">
            Open
          </a>
        ) : (
          <span className="text-muted small">-</span>
        )}
        {allowManageCurrent && canPartsEdit && row.collection === "part_extra_files" ? (
          <button
            type="button"
            className="btn btn-sm btn-outline-danger"
            disabled={extraDeleteBusy === row.db_id}
            onClick={() => handleExtraDelete(row.db_id)}
          >
            {extraDeleteBusy === row.db_id ? "Deleting..." : "Delete"}
          </button>
        ) : null}
      </div>
    );
  }

  function renderFilesSection(section: FileOverviewSection | null, title: string, allowManageCurrent = false, note?: string) {
    const rows = asArr<FileOverviewRow>(section?.files);
    return (
      <div className="pd-card p-3">
        <div className="d-flex flex-column flex-md-row align-items-md-center justify-content-between gap-2 mb-2">
          <div>
            <h6 className="mb-0">{title}</h6>
            {note ? <div className="text-muted small mt-1">{note}</div> : null}
          </div>
          <div className="small text-muted">
            Total {section?.counts?.total ?? rows.length} · part_files {section?.counts?.part_files ?? 0} · part_extra_files {section?.counts?.part_extra_files ?? 0}
          </div>
        </div>
        {rows.length ? (
          <div className="table-responsive">
            <table className="table table-sm align-middle">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Collection</th>
                  <th>Group</th>
                  <th>Ext</th>
                  <th>Path</th>
                  <th>Size</th>
                  <th>Recorded</th>
                  <th>Source</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id || `${row.collection}-${row.rel_path}-${row.revision}`}>
                    <td>
                      <div>{row.name || "-"}</div>
                      {row.label ? <div className="text-muted small">Label: {row.label}</div> : null}
                      {row.mime ? <div className="text-muted small">{row.mime}</div> : null}
                    </td>
                    <td><code>{row.collection || "-"}</code></td>
                    <td>{row.ext_group || "-"}</td>
                    <td>{row.ext || "-"}</td>
                    <td className="pd-files-path">{row.rel_path || "-"}</td>
                    <td>{formatBytes(row.size)}</td>
                    <td>
                      <div>{row.recorded_at_display || row.recorded_at || "-"}</div>
                      {row.recorded_by ? <div className="text-muted small">{row.recorded_by}</div> : null}
                    </td>
                    <td>{row.source || "-"}</td>
                    <td>{fileRowActions(row, allowManageCurrent)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-muted small">No files recorded in the database for this revision.</div>
        )}
      </div>
    );
  }

  return (
    <div className="container-fluid py-3">
      {/* Title */}
      <div className="pb-2 border-bottom mb-3">
        <div className="d-flex align-items-start justify-content-between gap-3">
          <div>
            <h4 className="mb-0">
              {pn}
              {revisionValue ? ` REV ${revisionValue}` : ""}
              {descriptionValue ? ` - ${descriptionValue}` : ""}
            </h4>
            <div className="text-muted small">{categoryValue || ""}</div>
            {isSharedView ? (
              <div className="alert alert-info py-2 px-3 mt-2 mb-0 small">
                Read-only shared view.
                {publicShareInfo?.expires_at ? ` Expires ${publicShareInfo.expires_at_display || publicShareInfo.expires_at}.` : ""}
                {(sharedAllowsChildren || sharedAllowsDocpacks || sharedAllowsAttributes) ? (
                  <div className="mt-1">
                    Enabled:
                    {sharedAllowsChildren ? " child parts" : ""}
                    {sharedAllowsChildren && (sharedAllowsDocpacks || sharedAllowsAttributes) ? "," : ""}
                    {sharedAllowsDocpacks || sharedAllowsAttributes ? " doc packs and attributes" : ""}
                    .
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      {/* Top zone: Left (hero + quick facts) / Right (tabs) */}
      <div className="row g-3">
        {/* LEFT */}
        <div className="col-lg-4">
            <div className="pd-card">
            <div className="pd-hero">
              <ImageStrip pn={pn} rev={rev || ""} mode="preview" endpointBase={partImagesEndpoint} limit={1} fit cacheBust={refreshTick} />
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
                {selectedSummaryIds.map((fieldId) => {
                  const field = summaryFields.find((item) => item.id === fieldId)
                  return field ? <span key={field.id}>{renderSummaryField(field)}</span> : null
                })}
              </div>

              {!isSharedView && summaryFields.length > 0 && (
                <div className="pd-info-row">
                  <FieldSelector
                    title="Part summary fields"
                    buttonLabel="Summary fields"
                    availableFields={summaryFields}
                    selectedIds={selectedSummaryIds}
                    requiredIds={requiredSummaryIds}
                    onChange={(fieldIds) => persistFieldSelection("part_detail_summary", fieldIds)}
                    onReset={() => persistFieldSelection("part_detail_summary", defaultSummaryIds)}
                  />
                </div>
              )}

              <div className="pd-info-row pd-file-row">
                {(() => {
                  const href = String(linkValue || "").trim()
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
                  {identityAvatar(uploaderProfile, uploaderName || "Uploader")}
                  <span>{uploaderName ? `Uploaded by ${uploaderName}` : "Uploader unknown"}</span>
                </span>
                <span className="pd-user-pill">
                  {approverName ? (
                    identityAvatar(approverProfile, approverName)
                  ) : (
                    <img src={approvedInfo.approved ? "/static/images/approved.svg" : "/static/images/notapproved.svg"} alt="Approval" />
                  )}
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
          <TabView
            className="pd-tabs"
            scrollable
            activeIndex={tabIndex}
            onTabChange={(e: any) => setTabIndex(e.index)}
          >
            

            {hasDrawing && (
            <TabPanel
              header={tabHeader("Drawing", "pi-file-pdf")}
            >
              {pdfHref ? (
                <a
                  href={pdfHref}
                  target="_blank"
                  rel="noreferrer"
                  className="pd-drawing-link"
                  title="Open PDF drawing"
                >
                  <ImageStrip pn={pn} rev={rev || ""} mode="drawing" endpointBase={partImagesEndpoint} limit={1} fit cacheBust={refreshTick} />
                </a>
              ) : (
                <div className="pd-drawing-link">
                  <ImageStrip pn={pn} rev={rev || ""} mode="drawing" endpointBase={partImagesEndpoint} limit={1} fit cacheBust={refreshTick} />
                </div>
              )}
            </TabPanel>
            )}
            {hasDatasheetPreview && (
              <TabPanel header={tabHeader("Datasheet", "pi-book")}>
                <div className="pd-datasheet-viewer p-3">
                  <div className="pd-datasheet-toolbar">
                    {datasheetOptions.length > 1 && (
                      <div>
                        <label className="form-label small" htmlFor="datasheetSelect">
                          Datasheet file
                        </label>
                        <select
                          id="datasheetSelect"
                          className="form-select form-select-sm"
                          value={selectedDatasheetKey}
                          onChange={(e) => setSelectedDatasheetKey(e.target.value)}
                        >
                          {datasheetOptions.map((opt) => (
                            <option key={opt.key} value={opt.key}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                    {activeDatasheet && (
                      <a
                        className="btn btn-outline-secondary btn-sm"
                        href={activeDatasheet.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open datasheet
                      </a>
                    )}
                  </div>
                  {activeDatasheet ? (
                    !activeDatasheet.canPreview ? (
                      <div className="alert alert-secondary mb-0">
                        External datasheet links are not embedded. Use the button above to open the source document.
                      </div>
                    ) : isImageLike(activeDatasheet.ext, activeDatasheet.url) ? (
                      <img src={activeDatasheet.url} alt="Datasheet" className="pd-datasheet-image" />
                    ) : isPdfLike(activeDatasheet.ext, activeDatasheet.url) ? (
                      <iframe src={activeDatasheet.url} title="Datasheet" className="pd-datasheet-frame" />
                    ) : (
                      <iframe src={activeDatasheet.url} title="Datasheet" className="pd-datasheet-frame" />
                    )
                  ) : (
                    <div className="text-muted">No datasheet preview available.</div>
                  )}
                </div>
              </TabPanel>
            )}

            

            {(!isSharedView || sharedAllowsAttributes) && <TabPanel
              header={tabHeader("Attributes & Notes", "pi-list", notesIndicator)}
              headerClassName={notesIndicator ? "pd-tab-indicator pd-tab-indicator--note" : undefined}
            >
              {!isSharedView && (
                <div className="pd-card p-3 mb-3">
                  <div className="d-flex align-items-center justify-content-between gap-2">
                    <h6 className="mb-0">Notes</h6>
                    {canPartsNote ? (
                      <div className="d-flex align-items-center gap-2">
                        {notesDirty ? (
                          <span className="small text-warning-emphasis">Unsaved changes</span>
                        ) : notesSavedOnce ? (
                          <span className="small text-success"><i className="pi pi-check me-1" aria-hidden="true" />Saved</span>
                        ) : null}
                        <button
                          type="button"
                          className="btn btn-sm btn-outline-primary"
                          onClick={() => saveNotes()}
                          disabled={notesSaving || !notesDirty}
                        >
                          {notesSaving ? "Saving..." : "Save"}
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm btn-outline-danger"
                          onClick={clearNotes}
                          disabled={notesSaving || (!notes && !savedNotes)}
                          title="Erase notes"
                          aria-label="Erase notes"
                        >
                          <i className="pi pi-trash" aria-hidden="true" />
                        </button>
                      </div>
                    ) : null}
                  </div>
                  <textarea
                    className="form-control form-control-sm mt-2"
                    rows={4}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    onKeyDown={(e) => {
                      if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && canPartsNote && notesDirty && !notesSaving) {
                        e.preventDefault()
                        saveNotes()
                      }
                    }}
                    placeholder="Add notes for this part..."
                    disabled={!canPartsNote}
                  />
                  {notesError ? <div className="text-danger small mt-1">{notesError}</div> : null}
                  {canPartsNote
                    ? <div className="text-muted small mt-1">Ctrl+Enter to save</div>
                    : <div className="text-muted small mt-1">Read-only</div>}
                </div>
              )}
              {attrs.length === 0 ? (
                <div className="text-muted small">No attributes.</div>
              ) : (
                <div className="pd-attrs-wrap">
                  <div className="pd-attrs-list">
                    <div className="pd-attrs-search">
                      <i className="pi pi-search" aria-hidden="true" />
                      <input
                        type="search"
                        className="form-control form-control-sm"
                        value={attributeSearch}
                        onChange={(event) => setAttributeSearch(event.target.value)}
                        placeholder="Search fields and values..."
                        aria-label="Search attributes by field or value"
                      />
                      {attributeSearch && (
                        <button
                          type="button"
                          className="btn btn-sm btn-link"
                          onClick={() => setAttributeSearch("")}
                          aria-label="Clear attribute search"
                        >
                          Clear
                        </button>
                      )}
                    </div>
                    {filteredAttrs.map(([k, v]) => (
                      <div key={k} className="pd-attr">
                        <div className="pd-attr-k">{k}</div>
                        <div className="pd-attr-v">{String(v)}</div>
                      </div>
                    ))}
                    {filteredAttrs.length === 0 && (
                      <div className="pd-attrs-empty">No attributes match “{attributeSearch.trim()}”.</div>
                    )}
                  </div>
                </div>
              )}
            </TabPanel>}

            {/* 3D Preview tab at the end */}
            {threeDOptions.length > 0 && (
              <TabPanel header={tabHeader("3D Preview", "pi-box")}>
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
                      format={previewFormat || "ply"}
                      height={520}
                    />
                  </Suspense>
                ) : (
                  <div className="p-3 text-muted">Select a 3D file to preview.</div>
                )}
              </TabPanel>
            )}

            <TabPanel header={tabHeader("Files", "pi-paperclip")}>
              <div className="d-flex flex-column gap-3">
                <div className="pd-card p-3">
                  <div className="d-flex flex-column flex-md-row align-items-md-center justify-content-between gap-2">
                    <div>
                      <h6 className="mb-0">File visibility by revision</h6>
                      <div className="text-muted small mt-1">
                        Files are shown by the database revision key for this part number. Other revisions stay isolated below.
                      </div>
                    </div>
                    {canPartsEdit ? (
                      <div className="d-flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="btn btn-sm btn-outline-secondary"
                          onClick={handleRefreshFiles}
                          disabled={refreshBusy}
                        >
                          <i className={`pi ${refreshBusy ? "pi-spin pi-spinner" : "pi-refresh"} me-1`} aria-hidden="true" />
                          {refreshBusy ? "Updating..." : "Update related files"}
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm btn-outline-primary"
                          onClick={() => extraFileInputRef.current?.click()}
                          disabled={extraUploadBusy}
                        >
                          <i className="pi pi-upload me-1" aria-hidden="true" />
                          {extraUploadBusy ? "Uploading..." : "Upload files..."}
                        </button>
                      </div>
                    ) : null}
                  </div>
                  {canPartsEdit && (
                    <div className="form-check mt-2">
                      <input
                        className="form-check-input"
                        type="checkbox"
                        id="refreshChildrenCheck"
                        checked={refreshIncludeChildren}
                        disabled={refreshBusy}
                        onChange={(e) => setRefreshIncludeChildren(e.target.checked)}
                      />
                      <label className="form-check-label small" htmlFor="refreshChildrenCheck">
                        Include children recursively (assemblies)
                      </label>
                    </div>
                  )}
                  <input
                    ref={extraFileInputRef}
                    type="file"
                    multiple
                    className="d-none"
                    onChange={(e) => handleExtraUpload(e.target.files)}
                  />
                  {extraUploadError ? <div className="text-danger small mt-2">{extraUploadError}</div> : null}
                  {extraError ? <div className="text-danger small mt-2">{extraError}</div> : null}
                  {filesOverviewError ? <div className="text-danger small mt-2">{filesOverviewError}</div> : null}
                  {refreshMsg ? <div className="text-success small mt-2">{refreshMsg}</div> : null}
                  {refreshError ? <div className="text-danger small mt-2">{refreshError}</div> : null}
                  <div className="text-muted small mt-2">
                    Current revision rows: {currentFileRows.length}. Other revision rows: {otherRevisionFileCount}.
                  </div>
                </div>

                {filesOverviewLoading ? (
                  <div className="text-muted small">Loading file visibility...</div>
                ) : (
                  <>
                    {renderFilesSection(
                      filesOverviewCurrent,
                      `Current revision (${filesOverviewCurrent?.display_revision || (effectiveRev || "(no revision)")})`,
                      true,
                      "This section matches the exact part number and revision shown in the page header."
                    )}

                    <div className="pd-card p-3">
                      <div className="d-flex align-items-center justify-content-between mb-2">
                        <h6 className="mb-0">Other revisions</h6>
                        <div className="text-muted small">
                          {filesOverviewOther.length
                            ? `${filesOverviewOther.length} revision section${filesOverviewOther.length === 1 ? "" : "s"}`
                            : "No files found for other revisions."}
                        </div>
                      </div>
                      {filesOverviewOther.length ? (
                        <div className="d-flex flex-column gap-3">
                          {filesOverviewOther.map((section) => (
                            <div key={`files-other-${section.revision || "none"}`} className="pd-files-other">
                              {renderFilesSection(
                                section,
                                `Revision ${section.display_revision || section.revision || "(no revision)"}`,
                                false,
                                "These rows belong to another revision of the same part number."
                              )}
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </>
                )}
              </div>
            </TabPanel>

            {(!isSharedView || sharedAllowsDocpacks) && <TabPanel header={tabHeader("Doc Packs", "pi-folder")}>

              <div className="pd-card p-3 mt-3">
                <h6 className="mb-3">Scope</h6>
                <div className="row g-4">
                  <div className="col-md-4">
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

                  <div className="col-md-4">
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

                  <div className="col-md-4">
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

                <hr className="my-3" />

                <div className="row g-4">
                  <div className="col-md-6">
                    <div className="fw-semibold small mb-1">Process filter</div>
                    <div className="d-flex gap-3 mb-2">
                      <div className="form-check">
                        <input className="form-check-input" type="radio" name="procMode" id="procAll" checked={processMode==='all'} onChange={()=>setProcessMode('all')} />
                        <label className="form-check-label" htmlFor="procAll">All processes</label>
                      </div>
                      <div className="form-check">
                        <input className="form-check-input" type="radio" name="procMode" id="procSel" checked={processMode==='selected'} onChange={()=>setProcessMode('selected')} />
                        <label className="form-check-label" htmlFor="procSel">Only selected</label>
                      </div>
                    </div>
                    {processMode === 'selected' && (
                      <div className="border rounded p-2">
                        <div className="row g-2">
                          {docOpts.processes.map((p) => (
                            <div key={p} className="col-6 col-md-4">
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
                    )}
                  </div>

                  <div className="col-md-6">
                    <div className="fw-semibold small mb-1">File type filter</div>
                    <div className="border rounded p-2">
                      <div className="row g-2">
                        {docOpts.file_types.map((t) => (
                          <div key={t} className="col-6 col-md-4">
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
              </div>

              <div className="pd-card p-3 mt-3">
                <h6 className="mb-3">Outputs to generate</h6>
                <div className="row g-2">
                  <div className="col-md-6 col-lg-4"><div className="form-check"><input className="form-check-input" type="checkbox" id="docSel" checked={wantSelectedFiles} onChange={(e)=>{ setWantSelectedFiles(e.target.checked); if (!e.target.checked) setWantMarkupFiles(false); }} /><label className="form-check-label" htmlFor="docSel">Selected files</label></div></div>
                  <div className="col-md-6 col-lg-4"><div className="form-check"><input className="form-check-input" type="checkbox" id="docMarkupFiles" checked={wantMarkupFiles} disabled={!wantSelectedFiles || docOpts.markup_document_count === 0} onChange={(e)=>setWantMarkupFiles(e.target.checked)} /><label className="form-check-label" htmlFor="docMarkupFiles">Markup documents in selected files <span className="text-muted">({docOpts.markup_document_count})</span></label></div></div>
                  <div className="col-md-6 col-lg-4"><div className="form-check"><input className="form-check-input" type="checkbox" id="docExcel" checked={wantExcel} onChange={(e)=>setWantExcel(e.target.checked)} /><label className="form-check-label" htmlFor="docExcel">Excel BOM</label></div></div>
                  <div className="col-md-6 col-lg-4"><div className="form-check"><input className="form-check-input" type="checkbox" id="docBinder" checked={wantBinder} onChange={(e)=>setWantBinder(e.target.checked)} /><label className="form-check-label" htmlFor="docBinder">PDF binder</label></div></div>
                  <div className="col-md-6 col-lg-4"><div className="form-check"><input className="form-check-input" type="checkbox" id="docIndex" checked={wantIndex} onChange={(e)=>setWantIndex(e.target.checked)} /><label className="form-check-label" htmlFor="docIndex">Index (PDF, standalone)</label></div></div>
                  <div className="col-md-6 col-lg-4"><div className="form-check"><input className="form-check-input" type="checkbox" id="docVisual" checked={wantVisual} onChange={(e)=>setWantVisual(e.target.checked)} /><label className="form-check-label" htmlFor="docVisual">Visual summary (PDF)</label></div></div>
                  <div className="col-md-6 col-lg-4"><div className="form-check"><input className="form-check-input" type="checkbox" id="docHardware" checked={wantHardwareSummary} onChange={(e)=>setWantHardwareSummary(e.target.checked)} /><label className="form-check-label" htmlFor="docHardware">Hardware summary (standalone)</label></div></div>
                  <div className="col-md-6 col-lg-4"><div className="form-check"><input className="form-check-input" type="checkbox" id="docCover" checked={wantCoverPage} onChange={(e)=>setWantCoverPage(e.target.checked)} /><label className="form-check-label" htmlFor="docCover">Cover page (standalone)</label></div></div>
                  <div className="col-md-6 col-lg-4"><div className="form-check"><input className="form-check-input" type="checkbox" id="docWhere" checked={wantWhereusedReport} onChange={(e)=>setWantWhereusedReport(e.target.checked)} /><label className="form-check-label" htmlFor="docWhere">Where-used report (standalone)</label></div></div>
                  <div className="col-md-6 col-lg-4"><div className="form-check"><input className="form-check-input" type="checkbox" id="docMarkupReport" checked={wantMarkupReport} disabled={docOpts.markup_document_count === 0} onChange={(e)=>setWantMarkupReport(e.target.checked)} /><label className="form-check-label" htmlFor="docMarkupReport">Markup drawings report (print-only)</label></div></div>
                  <div className="col-md-6 col-lg-4">
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
                    }} /><label className="form-check-label" htmlFor="docFab">Fabrication Pack (preset)</label></div>
                  </div>
                </div>

                {wantExcel && excelFields.length > 0 && (
                  <div className="border rounded p-2 mt-3">
                    <div className="fw-semibold small mb-2">Excel BOM fields</div>
                    <div className="form-check">
                      <input
                        className="form-check-input"
                        type="radio"
                        name="excelMode"
                        id="excelModeDefault"
                        checked={excelUseDefault}
                        onChange={() => persistFieldMode("excel_bom", true)}
                      />
                      <label className="form-check-label small" htmlFor="excelModeDefault">Use admin default preset</label>
                    </div>
                    <div className="form-check mb-2">
                      <input
                        className="form-check-input"
                        type="radio"
                        name="excelMode"
                        id="excelModeCustom"
                        checked={!excelUseDefault}
                        onChange={() => persistFieldMode("excel_bom", false)}
                      />
                      <label className="form-check-label small" htmlFor="excelModeCustom">Use my selected fields</label>
                    </div>
                    {!excelUseDefault && (
                      <FieldSelector
                        inline
                        title="Excel BOM fields"
                        availableFields={excelFields}
                        selectedIds={selectedExcelIds}
                        requiredIds={requiredExcelIds}
                        onChange={(fieldIds) => {
                          persistFieldSelectionAndMode("excel_bom", fieldIds, false)
                        }}
                        onReset={() => {
                          persistFieldSelectionAndMode("excel_bom", defaultExcelIds, true)
                        }}
                      />
                    )}
                  </div>
                )}

                <div className="mt-3" style={{maxWidth: 360}}>
                  <label className="fw-semibold small form-label" htmlFor="docOutName">Output name (optional)</label>
                  <input
                    id="docOutName"
                    className="form-control form-control-sm"
                    value={outputName}
                    onChange={(e)=>setOutputName(e.target.value)}
                    placeholder={`${pn}${rev ? `_${rev}` : ''}_docpack`}
                  />
                </div>
              </div>

              {wantBinder && (
                <div className="row g-3 mt-0">
                  <div className="col-md-6">
                    <div className="pd-card p-3 h-100">
                      <h6 className="mb-3">Binder contents</h6>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="bCover" checked={binderAddCover} onChange={(e)=>setBinderAddCover(e.target.checked)} /><label className="form-check-label" htmlFor="bCover">Cover page</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="bIdx" checked={binderAddIndex} onChange={(e)=>setBinderAddIndex(e.target.checked)} /><label className="form-check-label" htmlFor="bIdx">Index</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="bVis" checked={binderAddVisualList} onChange={(e)=>setBinderAddVisualList(e.target.checked)} /><label className="form-check-label" htmlFor="bVis">Visual index section</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="bWhere" checked={binderAddWhereused} onChange={(e)=>setBinderAddWhereused(e.target.checked)} /><label className="form-check-label" htmlFor="bWhere">Where-used report section</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="bHard" checked={binderAddHardwareSummary} onChange={(e)=>setBinderAddHardwareSummary(e.target.checked)} /><label className="form-check-label" htmlFor="bHard">Hardware summary</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="bData" checked={binderAddDatasheets} onChange={(e)=>setBinderAddDatasheets(e.target.checked)} /><label className="form-check-label" htmlFor="bData">Datasheets</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="bMarkups" checked={binderAddMarkups} disabled={docOpts.markup_document_count === 0} onChange={(e)=>setBinderAddMarkups(e.target.checked)} /><label className="form-check-label" htmlFor="bMarkups">Markup drawings <span className="text-muted">({docOpts.markup_document_count})</span></label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="bFlat" checked={binderIncludeFlatPatterns} onChange={(e)=>setBinderIncludeFlatPatterns(e.target.checked)} /><label className="form-check-label" htmlFor="bFlat">Flat pattern PDFs</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="bNums" checked={binderPageNumbers} onChange={(e)=>setBinderPageNumbers(e.target.checked)} /><label className="form-check-label" htmlFor="bNums">Page numbers</label></div>
                    </div>
                  </div>
                  <div className="col-md-6">
                    <div className="pd-card p-3 h-100">
                      <h6 className="mb-3">Stamps</h6>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="sQuote" checked={stampQuote} onChange={(e)=>setStampQuote(e.target.checked)} /><label className="form-check-label" htmlFor="sQuote">For quotation</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="sConf" checked={stampConfidential} onChange={(e)=>setStampConfidential(e.target.checked)} /><label className="form-check-label" htmlFor="sConf">Confidential</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="sAppr" checked={stampApproved} onChange={(e)=>setStampApproved(e.target.checked)} /><label className="form-check-label" htmlFor="sAppr">Approved</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="sWip" checked={stampWip} onChange={(e)=>setStampWip(e.target.checked)} /><label className="form-check-label" htmlFor="sWip">WIP</label></div>
                      <div className="form-check"><input className="form-check-input" type="checkbox" id="sProg" checked={stampInprog} onChange={(e)=>setStampInprog(e.target.checked)} /><label className="form-check-label" htmlFor="sProg">In progress / Not approved</label></div>
                    </div>
                  </div>
                </div>
              )}

              <div className="pd-card p-3 mt-3">
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
                        excel_field_ids: !excelUseDefault ? selectedExcelIds : [],
                        pdf_binder: wantBinder,
                        index_pdf: wantIndex,
                        visual_list: wantVisual,
                        hardware_summary: wantHardwareSummary,
                        cover_page: wantCoverPage,
                        whereused_report: wantWhereusedReport,
                        markup_files: wantMarkupFiles,
                        markup_report: wantMarkupReport,
                        fabrication_pack: fabricationPack,
                        binder_add_cover: binderAddCover,
                        binder_add_visual_list: binderAddVisualList,
                        binder_add_whereused: binderAddWhereused,
                        binder_add_index: binderAddIndex,
                        binder_add_datasheets: binderAddDatasheets,
                        binder_add_hardware_summary: binderAddHardwareSummary,
                        binder_page_numbers: binderPageNumbers,
                        binder_include_flat_patterns: binderIncludeFlatPatterns,
                        binder_add_markups: binderAddMarkups,
                        stamp_quote: stampQuote,
                        stamp_confidential: stampConfidential,
                        stamp_approved: stampApproved,
                        stamp_wip: stampWip,
                        stamp_inprogress: stampInprog,
                      };
                      if (outputName.trim()) body.output_name = outputName.trim();
                      const buildUrl = isSharedView ? `${shareApiBase}/docpacks/build` : '/api/docpacks/build';
                      const resp = await fetch(buildUrl, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
                      if(!resp.ok) throw new Error(`HTTP ${resp.status}`);
                      const blob = await resp.blob();
                      const disp = resp.headers.get('Content-Disposition') || '';
                      const m = disp.match(/filename="?([^";]+)"?/i);
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
                          if (wantMarkupFiles) items.push("markup files");
                          if (wantMarkupReport) items.push("markup report");
                          if (wantBinder) items.push("Binder");
                          return `Preparing ${items.join(", ") || "outputs"}...`;
                        })()}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </TabPanel>}

          {!isSharedView && versions.length > 1 && (
            <TabPanel header={tabHeader("Other versions", "pi-history")}>
              <DataTable value={versions} dataKey="id" responsiveLayout="scroll" stripedRows>
                <Column header="" body={(r: VersionRow) => <ThumbImg urls={r.thumb_urls || []} maxH={32} maxW={48} />} style={{width:60}} />
                <Column field="part_number" header="Part Number" body={(r: VersionRow) => <a href={`/ui/part/${encodeURIComponent(r.part_number)}?rev=${encodeURIComponent(r.revision||"")}`}>{r.part_number}</a>} sortable />
                <Column field="revision" header="Rev" sortable />
                <Column field="description" header="Description" sortable />
              </DataTable>
            </TabPanel>
          )}

          {!isSharedView && jobsOrders.length > 0 && <TabPanel header={tabHeader("Jobs & Orders", "pi-briefcase")}>
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
          </TabPanel>}


            
          {!isSharedView && <TabPanel
            header={tabHeader("Comments & Markups", "pi-comments", reviewIndicator)}
            headerClassName={reviewIndicator ? `pd-tab-indicator pd-tab-indicator--${reviewIndicator}` : undefined}
          >
            <div className="pd-card p-3 mt-3">
              <div className="d-flex flex-column flex-md-row align-items-md-center justify-content-between gap-2 mb-2">
                <h6 className="mb-0 d-flex align-items-center gap-2">
                  Comments & drawing markups
                  <span className="badge rounded-pill text-bg-secondary">{comments.length} comments</span>
                  <span className="badge rounded-pill text-bg-secondary">{markupThreads.length} markup reviews</span>
                </h6>
                <input
                  type="search"
                  className="form-control form-control-sm"
                  style={{ maxWidth: 300 }}
                  value={notesSearch}
                  onChange={(e) => setNotesSearch(e.target.value)}
                  placeholder="Search comments & markups"
                  aria-label="Search comments and markups"
                />
              </div>
              {/* Canvas editor plus the unified review panel: general comments
                  and markup review threads share one list and one feature set. */}
              <DrawingMarkupWorkspace
                key={`${pn}::${revToken}::${drawingSource?.source_file_id || "none"}`}
                pn={pn}
                rev={effectiveRev || ""}
                pdfHref={pdfHref}
                drawingSource={drawingSource}
                layer={markupLayer}
                layerLoading={markupLoading}
                layerError={markupError}
                canEdit={canPartsNote}
                onLayerChange={setMarkupLayer}
                draftRef={markupDraftRef}
                searchText={notesSearch}
                comments={comments}
                commentsBusy={commentSaving}
                commentsError={commentError}
                onAddComment={addComment}
                onReplyComment={replyComment}
                onSetCommentStatus={setCommentStatus}
                onSetCommentPriority={setCommentPriority}
                onDeleteComment={deleteComment}
              />
            </div>
          </TabPanel>}


          {!isSharedView && <TabPanel header={tabHeader("Actions", "pi-cog")}>
            <div className="pd-card p-3 pd-actions-layout">
              <div className="border rounded p-3 pd-action-arena">
                <div>
                  <h6 className="mb-0">Export to Arena</h6>
                  <div className="text-muted small mt-1">
                    Generate Arena-compatible CSV exports for BOM structure, selected part properties, and file links.
                  </div>
                </div>
                <div className="text-muted small mt-3">
                  Required Arena BOM columns are always included: <code>item number</code>, <code>line number</code>, <code>level</code>, <code>quantity</code>, and <code>item name</code>.
                  Extra property columns come from the shared field configuration so the admin preset can be reused consistently by all users.
                </div>
                {arenaAvailableFields.length > 0 && (
                  <div className="border rounded p-2 mt-3">
                    <div className="fw-semibold small mb-2">Arena item properties</div>
                    <div className="form-check">
                      <input
                        className="form-check-input"
                        type="radio"
                        name="arenaMode"
                        id="arenaModeDefault"
                        checked={arenaUseDefault}
                        onChange={() => persistFieldMode("arena_bom", true)}
                      />
                      <label className="form-check-label small" htmlFor="arenaModeDefault">Use admin default preset</label>
                    </div>
                    <div className="form-check mb-2">
                      <input
                        className="form-check-input"
                        type="radio"
                        name="arenaMode"
                        id="arenaModeCustom"
                        checked={!arenaUseDefault}
                        onChange={() => persistFieldMode("arena_bom", false)}
                      />
                      <label className="form-check-label small" htmlFor="arenaModeCustom">Use my selected fields</label>
                    </div>
                    {!arenaUseDefault && (
                      <FieldSelector
                        inline
                        title="Arena item properties"
                        availableFields={arenaAvailableFields}
                        selectedIds={visibleSelectedArenaIds}
                        requiredIds={visibleRequiredArenaIds}
                        onChange={(fieldIds) => {
                          persistFieldSelectionAndMode("arena_bom", fieldIds, false)
                        }}
                        onReset={() => {
                          persistFieldSelectionAndMode("arena_bom", defaultVisibleArenaIds.length ? defaultVisibleArenaIds : arenaSuggestedFieldIds, true)
                        }}
                      />
                    )}
                  </div>
                )}
                <div className="d-flex flex-wrap gap-2 mt-3">
                  <button
                    type="button"
                    className="btn btn-sm btn-primary"
                    onClick={handleArenaBomExport}
                    disabled={arenaBusy !== null}
                  >
                    {arenaBusy === "bom" ? "Generating..." : "Bom and part properties"}
                  </button>
                </div>
                <div className="mt-3">
                  <label className="form-label small fw-semibold mb-1" htmlFor="arenaBaseUrl">BASE for file links</label>
                  <input
                    id="arenaBaseUrl"
                    className="form-control form-control-sm font-monospace"
                    value={arenaBaseUrl}
                    onChange={(e) => setArenaBaseUrl(e.target.value)}
                    placeholder="https://your.web.chain/touse/aspattern/"
                  />
                  <div className="text-muted small mt-1">
                    The file-links CSV appends extension subfolders and a normalized <code>PART_REV</code> file name to this prefix, for example <code>PDF/PART_REV_A.pdf</code>.
                  </div>
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-primary mt-2"
                    onClick={handleArenaFileLinksExport}
                    disabled={arenaBusy !== null}
                  >
                    {arenaBusy === "links" ? "Generating..." : "File links"}
                  </button>
                </div>
                {arenaError ? <div className="text-danger small mt-2">{arenaError}</div> : null}
              </div>
              {hasManagementActions ? (
                <div className="d-flex flex-column gap-3 pd-action-management">
                  {canAdmin && (
                    <div className="border rounded p-3">
                      <div className="d-flex flex-column flex-md-row align-items-md-center justify-content-between gap-2">
                        <div>
                          <h6 className="mb-0">External share link</h6>
                          <div className="text-muted small mt-1">
                            Creates a read-only public link for this part only. The raw link is shown once at creation time.
                          </div>
                        </div>
                        <div className="d-flex align-items-center gap-2">
                          <select
                            className="form-select form-select-sm"
                            style={{ width: 130 }}
                            value={shareExpiresDays}
                            onChange={(e) => setShareExpiresDays(e.target.value)}
                            disabled={shareCreateBusy}
                          >
                            <option value="7">Expires in 7 days</option>
                            <option value="30">Expires in 30 days</option>
                            <option value="90">Expires in 90 days</option>
                          </select>
                          <button
                            type="button"
                            className="btn btn-sm btn-outline-primary"
                            onClick={createShareLink}
                            disabled={shareCreateBusy}
                          >
                            {shareCreateBusy ? "Creating..." : "Create share link"}
                          </button>
                        </div>
                      </div>
                      <div className="row g-3 mt-1">
                        <div className="col-md-6">
                          <div className="form-check">
                            <input
                              className="form-check-input"
                              type="checkbox"
                              id="shareAllowChildren"
                              checked={shareAllowChildren}
                              disabled={shareCreateBusy}
                              onChange={(e) => setShareAllowChildren(e.target.checked)}
                            />
                            <label className="form-check-label" htmlFor="shareAllowChildren">
                              Allow access to BOM children
                            </label>
                          </div>
                          <div className="text-muted small mt-1">
                            Lets external users open descendant part pages inside the same shared link.
                          </div>
                        </div>
                        <div className="col-md-6">
                          <div className="form-check">
                            <input
                              className="form-check-input"
                              type="checkbox"
                              id="shareAllowExtended"
                              checked={shareAllowExtended}
                              disabled={shareCreateBusy}
                              onChange={(e) => setShareAllowExtended(e.target.checked)}
                            />
                            <label className="form-check-label" htmlFor="shareAllowExtended">
                              Allow doc packs and attributes
                            </label>
                          </div>
                          <div className="text-muted small mt-1">
                            Exposes the All attributes and Doc Packs tabs for this shared link.
                          </div>
                        </div>
                      </div>
                      {shareCreateError ? <div className="text-danger small mt-2">{shareCreateError}</div> : null}
                      {shareCreateUrl ? (
                        <div className="mt-2">
                          <label className="form-label small fw-semibold mb-1">New share URL</label>
                          <div className="input-group input-group-sm">
                            <input className="form-control" value={shareCreateUrl} readOnly />
                            <button type="button" className="btn btn-outline-secondary" onClick={copyShareLink}>
                              Copy
                            </button>
                          </div>
                          <div className="text-muted small mt-1">
                            {shareCopied ? "Copied to clipboard." : "If this link is lost, create a new one and revoke the old link."}
                          </div>
                        </div>
                      ) : null}
                      <div className="mt-3">
                        <div className="fw-semibold small mb-2">Existing share links</div>
                        {shareLoading ? (
                          <div className="text-muted small">Loading share links...</div>
                        ) : shareLinks.length ? (
                          <div className="table-responsive">
                            <table className="table table-sm align-middle mb-0">
                              <thead>
                                <tr>
                                  <th>Prefix</th>
                                  <th>Status</th>
                                  <th>Children</th>
                                  <th>Doc packs / attrs</th>
                                  <th>Created</th>
                                  <th>Expires</th>
                                  <th>Last access</th>
                                  <th>Accesses</th>
                                  <th />
                                </tr>
                              </thead>
                              <tbody>
                                {shareLinks.map((item) => (
                                  <tr key={item.id}>
                                    <td><code>{item.token_prefix || "-"}</code></td>
                                    <td>{item.status || "-"}</td>
                                    <td>{item.allow_children ? "Yes" : "-"}</td>
                                    <td>{item.allow_docpacks || item.allow_attributes ? "Yes" : "-"}</td>
                                    <td>{item.created_at_display || item.created_at || "-"}</td>
                                    <td>{item.expires_at_display || item.expires_at || "-"}</td>
                                    <td>{item.last_accessed_at_display || item.last_accessed_at || "-"}</td>
                                    <td>{item.access_count ?? 0}</td>
                                    <td>
                                      {item.status === "active" ? (
                                        <button
                                          type="button"
                                          className="btn btn-sm btn-outline-danger"
                                          disabled={shareRevokingId === item.id}
                                          onClick={() => revokeShareLink(item)}
                                        >
                                          {shareRevokingId === item.id ? "Revoking..." : "Revoke"}
                                        </button>
                                      ) : (
                                        <span className="text-muted small">-</span>
                                      )}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <div className="text-muted small">No share links created for this revision.</div>
                        )}
                        {shareError ? <div className="text-danger small mt-2">{shareError}</div> : null}
                      </div>
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
                      <div className="form-check mt-2">
                        <input
                          className="form-check-input"
                          type="checkbox"
                          id="deleteChildrenCheck"
                          checked={deleteChildren}
                          disabled={deleteBusy}
                          onChange={(e) => setDeleteChildren(e.target.checked)}
                        />
                        <label className="form-check-label small" htmlFor="deleteChildrenCheck">
                          Also delete BOM children (only if not used in other assemblies)
                        </label>
                      </div>
                      <div className="form-check">
                        <input
                          className="form-check-input"
                          type="checkbox"
                          id="deleteFilesCheck"
                          checked={deleteFilesToo}
                          disabled={deleteBusy}
                          onChange={(e) => setDeleteFilesToo(e.target.checked)}
                        />
                        <label className="form-check-label small" htmlFor="deleteFilesCheck">
                          Also delete related files from the server storage (permanent)
                        </label>
                      </div>
                      {deleteError ? <div className="text-danger small mt-1">{deleteError}</div> : null}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-muted small">No management actions available.</div>
              )}
            </div>
          </TabPanel>}

            </TabView>
            </div>

            {/* Used in (always visible under tabs) */}
            {!isSharedView && <div className="pd-usedin pd-card">
            <div className="d-flex align-items-center justify-content-between mb-2">
              <h6 className="mb-0">Used in</h6>
            </div>
            <DataTable value={wu} size="small" stripedRows responsiveLayout="scroll" filterDisplay="row">
              {selectedWhereUsedIds.map((fieldId) => {
                const field = whereUsedFields.find((item) => item.id === fieldId)
                if (!field) return null
                const isThumbnail = field.id === "thumbnail"
                const showColumnSelector = field.id === whereUsedSelectorFieldId && whereUsedFields.length > 0
                return (
                  <Column
                    key={field.id}
                    field={field.id}
                    header={
                      showColumnSelector ? (
                        <div className="d-flex align-items-center gap-2">
                          {!isThumbnail && <span>{field.label}</span>}
                          <FieldSelector
                            title="Where-used fields"
                            buttonLabel="Columns"
                            buttonIcon="pi pi-table"
                            buttonClassName="btn btn-sm d-inline-flex align-items-center gap-1 parts-columns-trigger"
                            menuAlign="start"
                            availableFields={whereUsedFields}
                            selectedIds={selectedWhereUsedIds}
                            requiredIds={requiredWhereUsedIds}
                            onChange={(fieldIds) => persistFieldSelection("where_used", fieldIds)}
                            onReset={() => persistFieldSelection("where_used", defaultWhereUsedIds)}
                          />
                        </div>
                      ) : (
                        isThumbnail ? "" : field.label
                      )
                    }
                    sortable={field.sortable !== false}
                    filter={field.filterable !== false}
                    showFilterMenu={false}
                    filterPlaceholder={fieldFilterPlaceholder(field)}
                    body={(row: WURow) => renderWhereUsedCell(field, row)}
                    style={isThumbnail ? { width: 110 } : field.id === "revision" ? { width: 100 } : field.id === "qty" ? { width: 100 } : undefined}
                  />
                )
              })}
            </DataTable>
          </div>}
        </div>
      </div>

      {/* Components table */}
      {hasBomContent ? (
      <div className="mt-4">
        <div className="d-flex align-items-center justify-content-between mb-2">
          <h6 className="mb-0">BOM</h6>
          <div className="d-flex gap-2 flex-wrap">
            <div className="btn-group" role="group" aria-label="BOM mode">
              <button
                type="button"
                className={`btn btn-sm ${bomMode === "tree" ? "btn-primary" : "btn-outline-secondary"}`}
                onClick={() => setBomMode("tree")}
              >
                Tree
              </button>
              <button
                type="button"
                className={`btn btn-sm ${bomMode === "flat" ? "btn-primary" : "btn-outline-secondary"}`}
                onClick={() => setBomMode("flat")}
              >
                Flat
              </button>
            </div>
            {bomMode === "tree" ? (
              <>
                <button type="button" className="btn btn-sm btn-outline-secondary" onClick={expandAll}>
                  Expand all
                </button>
                <button
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() => setBomExpanded({})}
                >
                  Collapse all
                </button>
              </>
            ) : (
              <span className="text-muted small align-self-center">
                Flat mode deduplicates child part numbers and rolls quantities up.
              </span>
            )}
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
        </div>

        {bomMode === "tree" ? (
          <TreeTable
            key={`tree-${ttKey}`}
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
            <Column
              expander
              className="tt-expander"
              bodyClassName="tt-expander"
              headerClassName="tt-expander"
              style={{ width: 30, minWidth: 30, maxWidth: 30 }}
            />

            <Column
              field="pending_review_severity"
              header="Reviews"
              body={bomReviewIndicator}
              sortable
              filter
              filterMatchMode="custom"
              filterFunction={reviewFilterMatches}
              showFilterMenu={false}
              filterElement={renderReviewFilter()}
              style={{ width: 105 }}
            />

            {selectedBomIds.map((fieldId) => {
              const field = bomFields.find((item) => item.id === fieldId)
              if (!field) return null
              const isThumbnail = field.id === "thumbnail"
              const showColumnSelector = !isSharedView && field.id === bomSelectorFieldId && bomFields.length > 0
              const style =
                isThumbnail
                  ? { width: 110 }
                  : field.id === "part_number"
                  ? { width: 240, textAlign: "left" as const }
                  : field.id === "revision"
                  ? { width: 90 }
                  : field.id === "qty"
                  ? { width: 110 }
                  : undefined
              return (
                <Column
                  key={field.id}
                  field={field.id}
                  filterField={field.id}
                  header={
                    showColumnSelector ? (
                      <div className="d-flex align-items-center gap-2">
                        {!isThumbnail && <span>{field.label}</span>}
                        {renderBomColumnsSelector()}
                      </div>
                    ) : (
                      isThumbnail ? "" : field.label
                    )
                  }
                  sortable={field.sortable !== false}
                  filter={field.filterable !== false}
                  filterMatchMode="custom"
                  filterFunction={(value, flt) => matchesFieldFilter(field, value, flt)}
                  showFilterMenu={false}
                  filterPlaceholder={field.data_type === "boolean" ? undefined : fieldFilterPlaceholder(field)}
                  filterElement={renderBomColumnFilter(field)}
                  body={(node: any) => renderBomCell(field, node)}
                  style={style}
                />
              )
            })}
          </TreeTable>
        ) : flatBomLoading ? (
          <div className="text-muted small">Loading flat BOM...</div>
        ) : (
          <DataTable
            key={`flat-${ttKey}`}
            value={flatFilteredRows}
            dataKey="row_key"
            stripedRows
            responsiveLayout="scroll"
            filterDisplay="row"
            showGridlines
            scrollable
            scrollHeight="55vh"
            resizableColumns
            size="small"
            rowClassName={flatReviewRowClassName}
          >
            <Column
              field="pending_review_severity"
              header="Reviews"
              body={bomReviewIndicator}
              sortable
              filter
              showFilterMenu={false}
              filterElement={renderReviewFilter()}
              style={{ width: 105 }}
            />
            {selectedBomIds.map((fieldId) => {
              const field = bomFields.find((item) => item.id === fieldId)
              if (!field) return null
              const isThumbnail = field.id === "thumbnail"
              const showColumnSelector = !isSharedView && field.id === bomSelectorFieldId && bomFields.length > 0
              const style =
                isThumbnail
                  ? { width: 110 }
                  : field.id === "part_number"
                  ? { width: 240 }
                  : field.id === "revision"
                  ? { width: 90 }
                  : field.id === "qty"
                  ? { width: 110 }
                  : undefined
              const label = isThumbnail ? "" : field.id === "qty" ? "Total Qty" : field.label
              return (
                <Column
                  key={field.id}
                  field={field.id}
                  filterField={field.id}
                  header={
                    showColumnSelector ? (
                      <div className="d-flex align-items-center gap-2">
                        {!isThumbnail && <span>{label}</span>}
                        {renderBomColumnsSelector()}
                      </div>
                    ) : (
                      label
                    )
                  }
                  sortable={field.sortable !== false}
                  filter={field.filterable !== false}
                  filterMatchMode="custom"
                  filterFunction={() => true}
                  showFilterMenu={false}
                  filterPlaceholder={field.data_type === "boolean" ? undefined : fieldFilterPlaceholder(field)}
                  filterElement={renderFlatBomColumnFilter(field)}
                  body={(row: FlatBomRow) => renderBomCell(field, row)}
                  style={style}
                />
              )
            })}
          </DataTable>
        )}
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


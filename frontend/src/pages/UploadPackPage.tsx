import { useEffect, useMemo, useRef, useState } from "react";
import "./uploadpack.css";
import { apiErrorMessage, apiFetch } from "../lib/api";
import {
  actionClass,
  groupOf,
  resolveModes,
  valueText,
  type CategoryMode,
  type GroupKey,
  type Tier,
} from "../lib/importPlan";

type Capability = Record<string, boolean>;
type Change = {
  field_id?: string;
  label?: string;
  source_key?: string;
  before?: unknown;
  after?: unknown;
  action: string;
  reason?: string;
};
type BomChange = {
  part_number: string;
  revision: string;
  before_qty?: number | null;
  after_qty?: number | null;
  action: string;
  planned_action?: string;
};
type FileChange = {
  kind: string;
  name: string;
  category: string;
  action: string;
  reason?: string;
};
// Actions that represent an actual effect; everything else is context the
// "changed only" view hides.
const EFFECT_ACTIONS = new Set([
  "add",
  "replace",
  "remove",
  "change",
  "clear",
  "quantity_change",
  "link",
  "blocked",
]);
const isEffect = (action: string) => EFFECT_ACTIONS.has(action);
type PlanPart = {
  part_number: string;
  revision: string;
  target_state: "new" | "existing_unapproved" | "existing_approved";
  properties: Change[];
  approval: Change[];
  bom: { action: string; reason?: string; changes: BomChange[] };
  files: FileChange[];
  changed: boolean;
  blocked: boolean;
  allowed: boolean;
  blocked_change_count: number;
  /** Thumbnail carried by the pack; the only image a part that does not exist yet has. */
  preview?: string;
};
type DuplicateChoice = {
  part_number: string;
  revision: string;
  options: Array<{ index: number; label: string; description: string }>;
};
type Plan = {
  parts: PlanPart[];
  duplicates?: DuplicateChoice[];
  required_permissions: string[];
  missing_permissions: string[];
  allowed: boolean;
  blocked_change_count: number;
  summary: {
    parts: number;
    new: number;
    changed: number;
    blocked: number;
    modified_approved: number;
  };
};
type Metrics = {
  parts_created?: number;
  parts_updated?: number;
  links_created?: number;
  files_written?: number;
  managed_files_written?: number;
  associated_files_written?: number;
  files_discovered?: number;
  thumbnails_generated?: number;
  operation_id?: string;
};
type UploadResult = {
  zip?: string;
  dry_run?: boolean;
  root?: string;
  root_rev?: string;
  /** Inline preview of the top-level part; response-only, never stored. */
  root_preview?: string;
  plan?: Plan;
  metrics?: Metrics;
  timings?: Record<string, number>;
  diagnostics?: Record<string, number | string | boolean>;
  capabilities?: Capability;
  warnings?: Array<string | { stage?: string; message?: string }>;
  errors?: Array<{ stage?: string; message?: string }>;
  previously_imported_operation_id?: string;
  previously_imported_at?: string;
  /** When the result arrived, so an applied import is visibly a past event. */
  received_at?: string;
};

const TIER_META: Record<Tier, { label: string; hint: string }> = {
  add: {
    label: "Add without overwriting",
    hint: "Fills blanks, empty BOMs and missing files, and records a release the pack brings. Nothing that already has a value is touched.",
    },
  overwrite: {
    label: "Overwrite with the pack",
    hint: "The pack wins: values are replaced and properties it does not carry are removed. Approved parts stay protected unless you tick the box.",
  },
};

const stateLabels: Record<PlanPart["target_state"], string> = {
  new: "New",
  existing_unapproved: "Draft",
  existing_approved: "Approved",
};
const stateBadgeClass: Record<PlanPart["target_state"], string> = {
  new: "text-bg-info",
  existing_unapproved: "text-bg-secondary",
  existing_approved: "text-bg-warning",
};

// The outcome groups the redline is organised by. Order matters: what needs a
// decision comes first, and the long tail of untouched parts comes last.
const GROUPS: Array<{
  key: GroupKey;
  title: string;
  hint: string;
  tone: string;
  openByDefault: boolean;
}> = [
  {
    key: "blocked",
    title: "Blocked",
    hint: "Your policy or permissions stop these changes. Applying leaves them alone.",
    tone: "border-danger",
    openByDefault: true,
  },
  {
    key: "modified_approved",
    title: "Approved parts being changed",
    hint: "Approved data this import overwrites. Review these before applying.",
    tone: "border-warning",
    openByDefault: true,
  },
  { key: "new", title: "New parts", hint: "Created by this import.", tone: "", openByDefault: false },
  { key: "changed", title: "Modified", hint: "Existing drafts this import changes.", tone: "", openByDefault: false },
  {
    key: "unchanged",
    title: "No changes",
    hint: "Present in the pack, identical to what is stored.",
    tone: "",
    openByDefault: false,
  },
];

function saveJson(name: string, data: unknown) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

function PolicySelect({
  id,
  label,
  help,
  value,
  onChange,
  canOverwrite,
}: {
  id: string;
  label: string;
  help: string;
  value: CategoryMode;
  onChange: (value: CategoryMode) => void;
  canOverwrite: boolean;
}) {
  return (
    <div className="col-md-4">
      <label className="form-label fw-semibold mb-1" htmlFor={id}>
        {label}
      </label>
      <select
        id={id}
        className="form-select form-select-sm"
        value={value}
        onChange={(event) => onChange(event.target.value as CategoryMode)}
      >
        <option value="skip">Skip</option>
        <option value="add">Add without overwriting</option>
        <option value="overwrite" disabled={!canOverwrite}>
          Overwrite with the pack
        </option>
      </select>
      <div className="form-text">{help}</div>
    </div>
  );
}

// One row shape for properties, approval, BOM and files, so a single foldable
// section renders every kind of change identically.
type Row = { name: string; note?: string; before?: unknown; after?: unknown; action: string; reason?: string };

const toPropertyRows = (rows: Change[]): Row[] =>
  rows.map((row) => ({
    name: row.label || row.field_id || "",
    note: row.source_key ? `from ${row.source_key}` : "",
    before: row.before,
    after: row.after,
    action: row.action,
    reason: row.reason,
  }));

const toBomRows = (rows: BomChange[]): Row[] =>
  rows.map((row) => ({
    name: row.part_number,
    note: row.revision ? `REV ${row.revision}` : "",
    before: row.before_qty,
    after: row.after_qty,
    action: row.action,
    reason: row.planned_action ? `Planned: ${row.planned_action.replaceAll("_", " ")}` : "",
  }));

const toFileRows = (rows: FileChange[]): Row[] =>
  rows.map((row) => ({
    name: row.name,
    note: row.kind === "discovered" ? `${row.category} · found in storage` : row.category,
    action: row.action,
    reason: row.reason,
  }));

// Folded by default and labelled with its effect count, so the part opens on a
// summary and drills down only where something actually happened.
function Section({
  title,
  rows,
  showValues = true,
  changedOnly,
  headline,
  empty,
}: {
  title: string;
  rows: Row[];
  showValues?: boolean;
  changedOnly: boolean;
  headline?: string;
  empty: string;
}) {
  const effects = rows.filter((row) => isEffect(row.action));
  const visible = changedOnly ? effects : rows;
  return (
    <details className="border rounded mt-2" open={effects.length > 0}>
      <summary className="px-2 py-1 d-flex flex-wrap align-items-center gap-2">
        <strong>{title}</strong>
        <span className={`badge ${effects.length ? "text-bg-primary" : "text-bg-light text-muted"}`}>
          {effects.length ? `${effects.length} change${effects.length > 1 ? "s" : ""}` : "no change"}
        </span>
        {headline ? <span className="small text-muted">{headline}</span> : null}
      </summary>
      <div className="px-2 pb-2">
        {!visible.length ? (
          <div className="text-muted small">{rows.length ? "No changes — switch to “All rows”." : empty}</div>
        ) : (
          <div className="table-responsive">
            <table className="table table-sm align-middle mb-0">
              <thead>
                <tr>
                  <th>Item</th>
                  {showValues ? <th>Before</th> : null}
                  {showValues ? <th>After</th> : null}
                  <th>Action</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((row, index) => (
                  <tr key={`${row.name}-${index}`}>
                    <td>
                      <div>{row.name}</div>
                      {row.note ? <small className="text-muted">{row.note}</small> : null}
                    </td>
                    {showValues ? (
                      <td className={["replace", "clear"].includes(row.action) ? "text-danger" : ""}>
                        {valueText(row.before)}
                      </td>
                    ) : null}
                    {showValues ? (
                      <td className={["add", "replace", "change"].includes(row.action) ? "text-primary" : ""}>
                        {valueText(row.after)}
                      </td>
                    ) : null}
                    <td className={`text-capitalize ${actionClass(row.action)}`}>
                      {row.action.replaceAll("_", " ")}
                    </td>
                    <td className="small">{row.reason || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </details>
  );
}

/** A part thumbnail: from the pack when it carries one, otherwise from storage. */
function PartThumb({
  part,
  applied,
  size = 40,
}: {
  part: PlanPart;
  applied: boolean;
  size?: number;
}) {
  const [stored, setStored] = useState<string | null>(null);
  const packed = part.preview || "";
  // A stored image only exists once the part does, so it is worth fetching
  // exactly when the pack carried nothing and the part is not new.
  const wantStored = !packed && (applied || part.target_state !== "new");

  useEffect(() => {
    if (!wantStored) return;
    let cancelled = false;
    const qs = new URLSearchParams({ pn: part.part_number, rev: part.revision, mode: "preview" });
    fetch(`/api/part_images?${qs.toString()}`)
      .then((response) => (response.ok ? response.json() : Promise.reject(response)))
      .then((rows) => {
        if (cancelled) return;
        const url = Array.isArray(rows) && rows.length ? rows[0]?.urls?.[0] : "";
        if (url) setStored(url);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [wantStored, part.part_number, part.revision]);

  const src = packed || stored;
  const style = { width: size, height: size, objectFit: "cover" as const, flex: "0 0 auto" };
  if (!src) {
    return <div className="rounded border bg-light" style={style} aria-hidden="true" />;
  }
  return (
    <img
      src={src}
      alt={`${part.part_number} preview`}
      className="rounded border"
      style={style}
      loading="lazy"
    />
  );
}

function RootPartCard({
  as: Tag,
  href,
  previewUrl,
  partNumber,
  revision,
  caption,
}: {
  as: "a" | "div";
  href?: string;
  previewUrl: string | null;
  partNumber: string;
  revision: string;
  caption: string;
}) {
  return (
    <Tag
      href={href}
      className="d-flex align-items-center gap-2 mt-3 p-2 border rounded text-decoration-none"
    >
      {previewUrl ? (
        <img
          src={previewUrl}
          alt={`${partNumber} preview`}
          className="rounded border flex-shrink-0"
          style={{ width: 48, height: 48, objectFit: "cover" }}
        />
      ) : (
        <div
          className="rounded border bg-light flex-shrink-0"
          style={{ width: 48, height: 48 }}
          aria-hidden="true"
        />
      )}
      <div className="small">
        <div className="fw-semibold">
          Top-level part: {partNumber}
          {revision ? ` — REV ${revision}` : ""}
        </div>
        <div className="text-muted">{caption}</div>
      </div>
    </Tag>
  );
}

/** Counts of what happens to one part, so the collapsed row still says enough. */
function partTally(part: PlanPart): string {
  const effects = (rows: Row[]) => rows.filter((row) => isEffect(row.action)).length;
  const bits: string[] = [];
  const properties = effects(toPropertyRows([...part.properties, ...part.approval]));
  const files = effects(toFileRows(part.files));
  if (properties) bits.push(`${properties} propert${properties === 1 ? "y" : "ies"}`);
  if (files) bits.push(`${files} file${files === 1 ? "" : "s"}`);
  if (part.bom.action !== "unchanged") bits.push(`BOM ${part.bom.action.replaceAll("_", " ")}`);
  return bits.join(" · ") || "no changes";
}

function PartRedline({
  part,
  changedOnly,
  applied,
}: {
  part: PlanPart;
  changedOnly: boolean;
  applied: boolean;
}) {
  const overridingApproved = part.target_state === "existing_approved" && part.changed;
  const sections = [
    {
      title: "Properties",
      label: "properties",
      rows: toPropertyRows([...part.properties, ...part.approval]),
      empty: "No incoming values.",
    },
    {
      title: "Files",
      label: "files",
      rows: toFileRows(part.files),
      showValues: false,
      empty: "No files for this part/revision.",
    },
    {
      title: "BOM",
      label: "BOM",
      rows: toBomRows(part.bom.changes),
      headline: `${part.bom.action.replaceAll("_", " ")}${part.bom.reason ? ` — ${part.bom.reason}` : ""}`,
      empty: "No incoming BOM definition.",
    },
  ];
  return (
    <details className="border rounded bg-white upload-pack-part">
      <summary className="d-flex flex-wrap align-items-center gap-2 p-2">
        <PartThumb part={part} applied={applied} />
        <strong>
          {part.part_number} — {part.revision || "No revision"}
        </strong>
        <span className={`badge ${stateBadgeClass[part.target_state]}`}>{stateLabels[part.target_state]}</span>
        {overridingApproved ? (
          <span className={`badge ${part.allowed ? "text-bg-danger" : "text-bg-warning"}`}>
            {part.allowed ? "Overriding approved" : "Needs admin to override"}
          </span>
        ) : !part.allowed ? (
          <span className="badge text-bg-danger">Blocked</span>
        ) : null}
        <span className="small text-muted ms-auto">{partTally(part)}</span>
      </summary>
      <div className="px-2 pb-2">
        {sections.map((section) => (
          <Section key={section.title} {...section} changedOnly={changedOnly} />
        ))}
      </div>
    </details>
  );
}

export default function UploadPackPage() {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [result, setResult] = useState<UploadResult | null>(null);
  const [search, setSearch] = useState("");
  const [changedOnly, setChangedOnly] = useState(true);
  // Operator picks for part numbers that appear more than once in the pack.
  const [duplicateChoices, setDuplicateChoices] = useState<Record<string, number>>({});
  const [capabilities, setCapabilities] = useState<Capability>({});
  const [capabilitiesError, setCapabilitiesError] = useState("");
  const [tier, setTier] = useState<Tier>("add");
  const [includeApproved, setIncludeApproved] = useState(false);
  const [dataCategory, setDataCategory] = useState<CategoryMode | null>(null);
  const [bomCategory, setBomCategory] = useState<CategoryMode | null>(null);
  const [fileCategory, setFileCategory] = useState<CategoryMode | null>(null);
  const [rootPreviewUrl, setRootPreviewUrl] = useState<string | null>(null);
  const [rootPreviewStatus, setRootPreviewStatus] = useState("");
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(GROUPS.map((group) => [group.key, group.openByDefault])),
  );
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    apiFetch<{ imports?: Capability }>("/api/import/capabilities")
      .then((payload) => {
        setCapabilities(payload?.imports || {});
        setCapabilitiesError("");
      })
      .catch((requestError) => {
        setCapabilities({});
        setCapabilitiesError(apiErrorMessage(requestError, "Failed to load import permissions."));
      });
  }, []);

  const rootPn = result?.root || "";
  const rootRev = result?.root_rev || "";
  const rootHref = rootPn
    ? `/ui/part/${encodeURIComponent(rootPn)}?rev=${encodeURIComponent(rootRev)}`
    : "";
  // A preview of a part that does not exist yet has nowhere to link to. After
  // an applied import it does, and an existing part always did.
  const rootExists =
    !!rootPn &&
    (!result?.dry_run ||
      (result?.plan?.parts ?? []).some(
        (part) =>
          part.part_number === rootPn &&
          part.revision === rootRev &&
          part.target_state !== "new",
      ));

  useEffect(() => {
    let cancelled = false;
    if (!rootPn) {
      setRootPreviewUrl(null);
      setRootPreviewStatus("");
      return () => {
        cancelled = true;
      };
    }
    const packPreview = result?.root_preview || "";
    if (!rootExists) {
      // Nothing stored yet -- show the image straight from the pack.
      setRootPreviewUrl(packPreview || null);
      setRootPreviewStatus(packPreview ? "" : "No preview image in this pack.");
      return () => {
        cancelled = true;
      };
    }
    setRootPreviewUrl(null);
    setRootPreviewStatus("Loading preview…");
    const qs = new URLSearchParams({ pn: rootPn, rev: rootRev, mode: "preview" });
    fetch(`/api/part_images?${qs.toString()}`)
      .then((response) => (response.ok ? response.json() : Promise.reject(response)))
      .then((rows) => {
        if (cancelled) return;
        const url = Array.isArray(rows) && rows.length ? rows[0]?.urls?.[0] : "";
        if (url) {
          setRootPreviewUrl(url);
          setRootPreviewStatus("");
        } else if (packPreview) {
          setRootPreviewUrl(packPreview);
          setRootPreviewStatus("");
        } else {
          setRootPreviewStatus("No preview image stored for the top-level part.");
        }
      })
      .catch(() => {
        if (cancelled) return;
        if (packPreview) {
          setRootPreviewUrl(packPreview);
          setRootPreviewStatus("");
          return;
        }
        setRootPreviewStatus("Failed to load preview image.");
      });
    return () => {
      cancelled = true;
    };
  }, [rootPn, rootRev, rootExists, result?.root_preview]);

  const canPreview = !!capabilities["imports.preview"];
  const canLowRisk = !!capabilities["imports.execute_low_risk"];
  const canAdvanced = !!capabilities["imports.execute_approved"];
  const canOverride = canAdvanced && !!capabilities["imports.override_approved"];

  // The tier sets all three categories; the advanced panel can pull one out of
  // step. Approved parts are only reachable through the tick, and only for a
  // category that is actually overwriting.
  const categories = useMemo(
    () => ({
      data: dataCategory ?? tier,
      bom: bomCategory ?? tier,
      file: fileCategory ?? tier,
    }),
    [tier, dataCategory, bomCategory, fileCategory],
  );

  const overrideActive = includeApproved && canOverride;
  const modes = useMemo(
    () => resolveModes({ tier, categories, includeApproved, canOverride }),
    [tier, categories, includeApproved, canOverride],
  );
  const { data_mode: dataMode, bom_mode: bomMode, file_mode: fileMode, approval_mode: approvalMode } = modes;
  const customised =
    (dataCategory !== null && dataCategory !== tier) ||
    (bomCategory !== null && bomCategory !== tier) ||
    (fileCategory !== null && fileCategory !== tier);

  function applyTier(next: Tier) {
    setTier(next);
    setDataCategory(null);
    setBomCategory(null);
    setFileCategory(null);
    if (next === "add") setIncludeApproved(false);
  }

  // The plan on screen only describes the ZIP and the policy it was built from.
  // Changing either makes it stale, and applying a stale plan is exactly the
  // mistake the preview exists to prevent.
  const policySignature = `${dataMode}|${bomMode}|${fileMode}|${approvalMode}|${JSON.stringify(duplicateChoices)}`;
  const [previewedSignature, setPreviewedSignature] = useState("");
  const [previewedFile, setPreviewedFile] = useState<File | null>(null);
  const previewCurrent =
    !!result?.dry_run && previewedFile === file && previewedSignature === policySignature;

  const plan = result?.plan;
  const applied = !!result && !result.dry_run;
  const groups = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const matches = (part: PlanPart) => {
      if (!needle) return true;
      // Search part identity plus the names of everything it touches, so a
      // file or child part number finds its parent row.
      return [
        part.part_number,
        part.revision,
        ...part.properties.map((row) => `${row.label || row.field_id} ${valueText(row.after)}`),
        ...part.files.map((row) => `${row.name} ${row.category}`),
        ...part.bom.changes.map((row) => row.part_number),
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle);
    };
    const buckets: Record<GroupKey, PlanPart[]> = {
      blocked: [],
      modified_approved: [],
      new: [],
      changed: [],
      unchanged: [],
    };
    for (const part of plan?.parts || []) {
      if (!matches(part)) continue;
      buckets[groupOf(part)].push(part);
    }
    return buckets;
  }, [plan, search]);
  const totals = useMemo(() => {
    const buckets: Record<GroupKey, number> = {
      blocked: 0,
      modified_approved: 0,
      new: 0,
      changed: 0,
      unchanged: 0,
    };
    for (const part of plan?.parts || []) buckets[groupOf(part)] += 1;
    return buckets;
  }, [plan]);

  function chooseFile(files: FileList | null) {
    const chosen = files?.[0] || null;
    setFile(chosen);
    setResult(null);
    setError("");
    setProgress(0);
  }

  function submit(dryRun: boolean) {
    if (!file) {
      setError("Select a ZIP file first.");
      return;
    }
    setBusy(true);
    setError("");
    setProgress(1);
    const form = new FormData();
    form.append("file", file);
    form.append("data_mode", dataMode);
    form.append("bom_mode", bomMode);
    form.append("file_mode", fileMode);
    form.append("approval_mode", approvalMode);
    if (Object.keys(duplicateChoices).length) {
      form.append("duplicate_choices", JSON.stringify(duplicateChoices));
    }
    if (dryRun) form.append("dry_run", "1");

    const signature = policySignature;
    const submitted = file;
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload/pack");
    xhr.responseType = "json";
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) setProgress(Math.min(85, Math.round((event.loaded / event.total) * 85)));
    };
    xhr.onload = () => {
      const payload = xhr.response || {};
      if (xhr.status < 200 || xhr.status >= 300 || payload.error) {
        const missing = Array.isArray(payload.missing_permissions)
          ? ` Missing: ${payload.missing_permissions.join(", ")}.`
          : "";
        setError(`${payload.detail || payload.error || `HTTP ${xhr.status}`}.${missing}`);
      } else {
        setResult({ ...payload, received_at: new Date().toLocaleString() });
        if (payload.capabilities) setCapabilities(payload.capabilities);
        if (dryRun) {
          setPreviewedSignature(signature);
          setPreviewedFile(submitted);
        } else {
          // The plan just became history: it describes what was written, not
          // what would happen if you pressed Apply again.
          setPreviewedSignature("");
          setPreviewedFile(null);
        }
      }
      setProgress(100);
      setBusy(false);
    };
    xhr.onerror = () => {
      setError("Network error while uploading the package.");
      setBusy(false);
    };
    xhr.send(form);
  }

  // What an apply would destroy, counted from the plan on screen. This is the
  // number worth confirming, not the number of parts.
  const destructive = useMemo(() => {
    let approvedParts = 0;
    let removals = 0;
    for (const part of plan?.parts || []) {
      if (!part.changed) continue;
      if (part.target_state === "existing_approved") approvedParts += 1;
      removals += part.properties.filter((row) => row.action === "clear").length;
      removals += part.approval.filter((row) => row.action === "clear").length;
      removals += part.bom.changes.filter((row) => row.action === "remove").length;
      removals += part.files.filter((row) => row.action === "replace").length;
    }
    return { approvedParts, removals };
  }, [plan]);

  const overwriting = tier === "overwrite" || customised;
  const tone = overrideActive ? "admin" : overwriting ? "draft" : "safe";
  const toneAlert = tone === "admin" ? "alert-danger" : tone === "draft" ? "alert-warning" : "alert-success";
  const applyBlockedReason = !file
    ? "Select a ZIP first."
    : !(canLowRisk || canAdvanced)
      ? "Your roles cannot apply imports."
      : overwriting && !canAdvanced
        ? "Overwriting needs imports.execute_approved."
        : overrideActive && !canOverride
          ? "Overwriting approved parts needs imports.override_approved."
          : !previewCurrent
            ? "Preview the current ZIP and policy first."
            : "";

  return (
    <div className="container-xxl py-3">
      <div className="border-bottom mb-3 pb-2 d-flex flex-wrap justify-content-between align-items-start gap-2">
        <div>
          <h4 className="mb-1">Import upload pack</h4>
          <div className="text-muted small">
            Select a ZIP, choose how it should be written, preview the exact redline, then apply it.
          </div>
        </div>
        {/* The policies decide what is filled, replaced or refused, so the page
            links straight at the chapter that spells that out. */}
        <a
          className="btn btn-sm btn-outline-secondary"
          href="/help#import-what-each-choice-does"
          target="_blank"
          rel="noreferrer"
        >
          Help: what each choice does
        </a>
      </div>

      <div className="card p-3 mb-3">
        <h6>1. Select ZIP</h6>
        <div
          className={`upload-pack-drop ${dragging ? "drag-over" : ""}`}
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
          }}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            chooseFile(event.dataTransfer.files);
          }}
        >
          <strong>{file?.name || "Drag a ZIP here or click to browse"}</strong>
          {file ? <div className="small text-muted">{(file.size / 1024 / 1024).toFixed(2)} MB</div> : null}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".zip"
          className="d-none"
          onChange={(event) => chooseFile(event.target.files)}
        />

        <h6 className="mt-4">2. Choose how the pack is written</h6>
        <div className="btn-group" role="group" aria-label="Import mode">
          {(Object.keys(TIER_META) as Tier[]).map((name) => (
            <button
              key={name}
              type="button"
              className={`btn ${
                tier === name
                  ? name === "overwrite"
                    ? "btn-warning"
                    : "btn-success"
                  : "btn-outline-secondary"
              }`}
              disabled={name === "overwrite" && !canAdvanced}
              onClick={() => applyTier(name)}
            >
              {TIER_META[name].label}
            </button>
          ))}
        </div>
        <div className="small text-muted mt-1">
          {TIER_META[tier].hint}
          {customised ? " (one or more categories adjusted below)" : ""}
        </div>

        <div className="form-check mt-2">
          <input
            className="form-check-input"
            type="checkbox"
            id="includeApproved"
            checked={includeApproved}
            disabled={!canOverride || tier === "add"}
            onChange={(event) => setIncludeApproved(event.target.checked)}
          />
          <label className="form-check-label" htmlFor="includeApproved">
            Also overwrite <strong>approved</strong> part/revisions
            {!canOverride ? " (needs imports.override_approved)" : ""}
          </label>
        </div>

        <div className={`alert ${toneAlert} small mt-2 mb-0`}>
          {tone === "admin" ? (
            <>
              <strong>Approved data will be overwritten.</strong> Approved part/revisions this pack
              describes are rewritten to match it — including their approval status, which is cleared
              if the pack does not carry one.
            </>
          ) : tone === "draft" ? (
            <>
              <strong>Drafts are rewritten to match the pack.</strong> Properties the pack does not
              carry are removed. Approved part/revisions stay untouched and are reported as blocked.
            </>
          ) : (
            <>
              <strong>Nothing existing is overwritten.</strong> Blanks, empty BOMs and missing files
              are filled, and a release the pack carries is recorded on a draft. Approved
              part/revisions stay untouched.
            </>
          )}{" "}
          Approval always comes from the pack; TinyMRP never sets it.{" "}
          <a href="/help#what-counts-as-approved" target="_blank" rel="noreferrer">
            How approval is read
          </a>
          .
        </div>

        <details className="mt-3">
          <summary className="fw-semibold">Advanced: set properties, BOM and files separately</summary>
          <div className="row g-3 mt-1">
            <PolicySelect
              id="dataMode"
              label="Properties"
              help="Ordinary, custom and approval fields. Overwriting also removes properties the pack does not carry."
              value={categories.data}
              canOverwrite={canAdvanced}
              onChange={setDataCategory}
            />
            <PolicySelect
              id="bomMode"
              label="BOM"
              help="Add writes a BOM only when the exact parent/revision has none. Overwriting replaces the whole definition."
              value={categories.bom}
              canOverwrite={canAdvanced}
              onChange={setBomCategory}
            />
            <PolicySelect
              id="fileMode"
              label="Files"
              help="Deliverables and associated files. Overwriting replaces a file of the same identity; files the pack omits are never deleted."
              value={categories.file}
              canOverwrite={canAdvanced}
              onChange={setFileCategory}
            />
          </div>
          <div className="form-text mt-2">
            Sent as data_mode=<code>{dataMode}</code>, bom_mode=<code>{bomMode}</code>, file_mode=
            <code>{fileMode}</code>, approval_mode=<code>{approvalMode}</code>.
          </div>
        </details>

        <h6 className="mt-4">3. Preview &nbsp; 4. Apply</h6>
        <div className="d-flex gap-2 flex-wrap align-items-center">
          <button
            className="btn btn-outline-primary"
            type="button"
            disabled={busy || !file || !canPreview}
            onClick={() => submit(true)}
          >
            Preview changes
          </button>
          <button
            className={`btn ${tone === "admin" ? "btn-danger" : "btn-primary"}`}
            type="button"
            disabled={busy || !!applyBlockedReason}
            onClick={() => {
              if (destructive.approvedParts || destructive.removals) {
                setConfirming(true);
                return;
              }
              submit(false);
            }}
          >
            Apply import
          </button>
          {busy ? <span className="text-muted small">Validating and planning…</span> : null}
          {!busy && applyBlockedReason ? (
            <span className="text-muted small">{applyBlockedReason}</span>
          ) : null}
          {!busy && !applyBlockedReason ? (
            <span className="text-success small">Preview is current — apply writes exactly what it shows.</span>
          ) : null}
        </div>
        {busy || progress ? (
          <div className="progress mt-3" role="progressbar" aria-valuenow={progress}>
            <div className="progress-bar" style={{ width: `${progress}%` }}>
              {progress}%
            </div>
          </div>
        ) : null}
        {!canPreview && Object.keys(capabilities).length ? (
          <div className="text-danger small mt-2">Your roles do not include import preview access.</div>
        ) : null}
        {capabilitiesError ? <div className="alert alert-danger mt-3 mb-0" role="alert">{capabilitiesError}</div> : null}
        {error ? <div className="alert alert-danger mt-3 mb-0">{error}</div> : null}
      </div>

      {confirming ? (
        <div className="card border-danger p-3 mb-3">
          <h6 className="text-danger mb-2">Confirm this import</h6>
          <ul className="small mb-2">
            {destructive.approvedParts ? (
              <li>
                <strong>{destructive.approvedParts}</strong> approved part/revision
                {destructive.approvedParts === 1 ? "" : "s"} will be changed.
              </li>
            ) : null}
            {destructive.removals ? (
              <li>
                <strong>{destructive.removals}</strong> value{destructive.removals === 1 ? "" : "s"},
                BOM row{destructive.removals === 1 ? "" : "s"} or file{destructive.removals === 1 ? "" : "s"} will be
                removed or overwritten.
              </li>
            ) : null}
          </ul>
          <div className="d-flex gap-2">
            <button
              className="btn btn-danger btn-sm"
              type="button"
              onClick={() => {
                setConfirming(false);
                submit(false);
              }}
            >
              Yes, apply it
            </button>
            <button className="btn btn-outline-secondary btn-sm" type="button" onClick={() => setConfirming(false)}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {plan ? (
        <div className="card p-3">
          {/* Whether anything was written is the first thing to read, so it is a
              banner rather than a heading that changes wording. */}
          <div className={`alert ${applied ? "alert-success" : "alert-warning"} d-flex flex-wrap gap-2 align-items-center`}>
            <span className="fs-5 fw-semibold">
              {applied ? "IMPORTED" : "PREVIEW"}
            </span>
            <span>
              {applied ? (
                <>
                  {result?.metrics?.parts_created || 0} part(s) created,{" "}
                  {result?.metrics?.parts_updated || 0} updated, {result?.metrics?.links_created || 0} BOM row(s),{" "}
                  {result?.metrics?.files_written || 0} file(s) written,{" "}
                  {result?.metrics?.files_discovered || 0} file record(s) reconciled.
                </>
              ) : (
                <>Nothing has been written. This is what applying would do.</>
              )}
            </span>
            <span className="ms-auto small text-muted">
              {result?.zip}
              {result?.received_at ? ` · ${result.received_at}` : ""}
              {applied && result?.metrics?.operation_id ? ` · op ${result.metrics.operation_id.slice(0, 8)}` : ""}
            </span>
          </div>
          {applied ? (
            <div className="small text-muted mb-2">
              To run another import, choose a ZIP and preview again.
            </div>
          ) : null}
          {result?.previously_imported_operation_id ? (
            <div className="alert alert-info small">
              This exact pack and policy was already imported
              {result.previously_imported_at ? ` on ${result.previously_imported_at}` : ""}. Running it
              again is allowed and simply repeats it.
            </div>
          ) : null}

          <div className="d-flex justify-content-between align-items-start flex-wrap gap-2">
            <div className="small text-muted">
              {plan.summary.parts} exact part/revisions · {plan.summary.changed} changed ·{" "}
              {plan.summary.blocked} blocked
              {plan.summary.modified_approved ? (
                <span className="badge text-bg-danger ms-2">
                  {plan.summary.modified_approved} approved changed
                </span>
              ) : (
                <span className="text-success ms-2">No approved data affected.</span>
              )}
            </div>
            <button
              className="btn btn-sm btn-outline-secondary"
              type="button"
              onClick={() => saveJson(`import-redline-${result?.zip || "report"}.json`, result)}
            >
              Download JSON report
            </button>
          </div>

          {rootPn ? (
            // Always show what is being imported; only link once it exists.
            <RootPartCard
              as={rootExists ? "a" : "div"}
              href={rootExists ? rootHref : undefined}
              previewUrl={rootPreviewUrl}
              partNumber={rootPn}
              revision={rootRev}
              caption={
                rootPreviewStatus ||
                (rootExists ? "Open part details" : "Not imported yet — apply to create it.")
              }
            />
          ) : null}

          {plan.required_permissions.length ? (
            <div className={`alert ${plan.allowed ? "alert-info" : "alert-warning"} small mt-3`}>
              Required: {plan.required_permissions.join(", ")}
              {plan.missing_permissions.length
                ? `. Missing: ${plan.missing_permissions.join(", ")}`
                : ". Current roles satisfy the planned effects."}
            </div>
          ) : (
            <div className="alert alert-secondary small mt-3">No permanent changes are planned.</div>
          )}

          {plan.duplicates?.length ? (
            <div className="alert alert-warning small mt-3">
              <div className="fw-semibold mb-2">
                {plan.duplicates.length} part number(s) appear more than once in this pack.
              </div>
              <div className="mb-2">
                SolidWorks exports virtual components under their parent, so several rows can share
                one part number. The first row is kept unless you pick another, then preview again.
              </div>
              {plan.duplicates.map((dup) => {
                const key = `${dup.part_number}␟${dup.revision}`;
                return (
                  <div key={key} className="mb-2">
                    <div>
                      <code>{dup.part_number}</code>
                      {dup.revision ? ` REV ${dup.revision}` : ""}
                    </div>
                    <select
                      className="form-select form-select-sm mt-1"
                      style={{ maxWidth: 520 }}
                      value={duplicateChoices[key] ?? 0}
                      onChange={(event) => {
                        // Same rule as the group toggle: read the value
                        // before handing a function to setState.
                        const choice = Number(event.target.value);
                        setDuplicateChoices((prev) => ({ ...prev, [key]: choice }));
                      }}
                    >
                      {dup.options.map((option) => (
                        <option key={option.index} value={option.index}>
                          {option.label}
                          {option.description ? ` — ${option.description}` : ""}
                        </option>
                      ))}
                    </select>
                  </div>
                );
              })}
            </div>
          ) : null}

          <div className="d-flex flex-wrap align-items-center gap-2 my-3">
            <input
              type="search"
              className="form-control form-control-sm"
              style={{ maxWidth: 260 }}
              placeholder="Search part, file or field…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <div className="btn-group btn-group-sm" role="group" aria-label="Detail level">
              <button
                type="button"
                className={`btn ${changedOnly ? "btn-secondary" : "btn-outline-secondary"}`}
                onClick={() => setChangedOnly(true)}
              >
                Changes only
              </button>
              <button
                type="button"
                className={`btn ${changedOnly ? "btn-outline-secondary" : "btn-secondary"}`}
                onClick={() => setChangedOnly(false)}
              >
                All rows
              </button>
            </div>
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary"
              onClick={() =>
                setOpenGroups(Object.fromEntries(GROUPS.map((group) => [group.key, true])))
              }
            >
              Expand all groups
            </button>
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary"
              onClick={() =>
                setOpenGroups(Object.fromEntries(GROUPS.map((group) => [group.key, false])))
              }
            >
              Collapse all
            </button>
          </div>

          <div className="d-flex flex-column gap-2">
            {GROUPS.map((group) => {
              const parts = groups[group.key];
              const total = totals[group.key];
              if (!total) return null;
              return (
                <details
                  key={group.key}
                  className={`border rounded ${group.tone}`}
                  open={openGroups[group.key]}
                  onToggle={(event) => {
                    // Read the element NOW. React calls the updater below
                    // later, and by then currentTarget is null -- which
                    // crashed the whole redline the moment a group rendered,
                    // because <details> fires toggle on mount.
                    const isOpen = (event.currentTarget as HTMLDetailsElement | null)?.open ?? false;
                    setOpenGroups((prev) =>
                      prev[group.key] === isOpen ? prev : { ...prev, [group.key]: isOpen },
                    );
                  }}
                >
                  <summary className="px-2 py-2 d-flex flex-wrap align-items-center gap-2">
                    <strong>{group.title}</strong>
                    <span className="badge text-bg-secondary">{total}</span>
                    <span className="small text-muted">{group.hint}</span>
                  </summary>
                  <div className="p-2 d-flex flex-column gap-2">
                    {parts.length ? (
                      parts.map((part) => (
                        <PartRedline
                          key={`${part.part_number}:${part.revision}`}
                          part={part}
                          changedOnly={changedOnly}
                          applied={applied}
                        />
                      ))
                    ) : (
                      <div className="text-muted small">No part in this group matches the search.</div>
                    )}
                  </div>
                </details>
              );
            })}
            {!plan.parts.length ? (
              <div className="text-muted small">This pack describes no part/revisions.</div>
            ) : null}
          </div>

          {result?.warnings?.length ? (
            <details className="mt-3 border-top pt-3">
              <summary className="fw-semibold text-warning-emphasis">
                Warnings ({result.warnings.length})
              </summary>
              <ul className="small mt-2 mb-0">
                {result.warnings.map((warning, index) => (
                  <li key={index}>
                    {typeof warning === "string"
                      ? warning
                      : `${warning.stage ? `${warning.stage}: ` : ""}${warning.message || ""}`}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}

          <details className="mt-3 border-top pt-3">
            <summary className="fw-semibold">Advanced details</summary>
            <div className="row g-3 small mt-1">
              <div className="col-md-6">
                <strong>Timing</strong>
                <pre className="bg-light rounded p-2 mt-1">{JSON.stringify(result?.timings || {}, null, 2)}</pre>
              </div>
              <div className="col-md-6">
                <strong>Diagnostics</strong>
                <pre className="bg-light rounded p-2 mt-1">{JSON.stringify(result?.diagnostics || {}, null, 2)}</pre>
              </div>
            </div>
          </details>
        </div>
      ) : null}
    </div>
  );
}

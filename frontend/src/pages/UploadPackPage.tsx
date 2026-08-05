import { useEffect, useMemo, useRef, useState } from "react";
import "./uploadpack.css";
import { apiErrorMessage, apiFetch } from "../lib/api";
import { actionClass, valueText } from "../lib/importPlan";

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
type UploadResult = {
  zip?: string;
  dry_run?: boolean;
  root?: string;
  root_rev?: string;
  /** Inline preview of the top-level part; response-only, never stored. */
  root_preview?: string;
  plan?: Plan;
  metrics?: {
    parts_created?: number;
    parts_updated?: number;
    links_created?: number;
    files_written?: number;
    managed_files_written?: number;
    associated_files_written?: number;
    files_discovered?: number;
    thumbnails_generated?: number;
  };
  timings?: Record<string, number>;
  diagnostics?: Record<string, number | string | boolean>;
  capabilities?: Capability;
  warnings?: Array<string | { stage?: string; message?: string }>;
  errors?: Array<{ stage?: string; message?: string }>;
};

type Filter = "all" | "changed" | "blocked" | "modified_approved";
type DataMode = "skip" | "fill_blanks" | "replace_unapproved" | "replace_all";
type BomMode = "skip" | "fill_if_empty" | "replace_unapproved" | "replace_all";
type FileMode = "skip" | "add_missing" | "replace_unapproved" | "replace_all";
type ApprovalMode = "preserve" | "import_unapproved" | "replace_all";
type Preset = "preserve" | "unless_existing_approved" | "always" | "custom";

// Quick presets that set the three independent policies at once. Touching an
// individual policy below detaches it from the preset ("Custom").
const PRESETS: Record<Exclude<Preset, "custom">, [DataMode, BomMode, FileMode]> = {
  preserve: ["fill_blanks", "fill_if_empty", "add_missing"],
  unless_existing_approved: ["replace_unapproved", "replace_unapproved", "replace_unapproved"],
  always: ["replace_all", "replace_all", "replace_all"],
};

// Approval is just another property: it follows the Properties policy, gated by
// the same permissions and the target's existing approved state.
const APPROVAL_FOR_DATA: Record<DataMode, ApprovalMode> = {
  skip: "preserve",
  fill_blanks: "preserve",
  replace_unapproved: "import_unapproved",
  replace_all: "replace_all",
};

type Tone = "safe" | "draft" | "admin";
const TIER_META: Record<Exclude<Preset, "custom">, { label: string; hint: string }> = {
  preserve: {
    label: "Fill only",
    hint: "Fills blanks, empty BOMs and missing files. New parts import in full, including their approval. Nothing on an existing approved part is changed.",
  },
  unless_existing_approved: {
    label: "Update drafts",
    hint: "Also replaces existing draft (unapproved) data. Existing approved parts stay protected.",
  },
  always: {
    label: "Override approved (Admin)",
    hint: "Also changes existing approved parts -- their properties, BOM, files and approval status.",
  },
};
const TONE_ALERT: Record<Tone, string> = { safe: "alert-success", draft: "alert-warning", admin: "alert-danger" };
const TONE_BUTTON: Record<Tone, string> = { safe: "btn-success", draft: "btn-warning", admin: "btn-danger" };

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

function PolicySelect<T extends string>({
  id,
  label,
  help,
  value,
  onChange,
  options,
}: {
  id: string;
  label: string;
  help: string;
  value: T;
  onChange: (value: T) => void;
  options: Array<{ value: T; label: string; disabled?: boolean }>;
}) {
  return (
    <div className="col-md-6">
      <label className="form-label fw-semibold mb-1" htmlFor={id}>
        {label}
      </label>
      <select
        id={id}
        className="form-select form-select-sm"
        value={value}
        onChange={(event) => onChange(event.target.value as T)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value} disabled={option.disabled}>
            {option.label}
          </option>
        ))}
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
                      <td className={row.action === "replace" ? "text-danger" : ""}>{valueText(row.before)}</td>
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

function PartRedline({ part, changedOnly }: { part: PlanPart; changedOnly: boolean }) {
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
  const badges = sections
    .map((section) => [section.label, section.rows.filter((row) => isEffect(row.action)).length] as const)
    .filter(([, count]) => count > 0);
  return (
    <details className="border rounded p-2 bg-white">
      <summary className="d-flex flex-wrap align-items-center gap-2">
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
        <span className="small text-muted ms-auto">
          {badges.length ? badges.map(([label, count]) => `${count} ${label}`).join(" · ") : "no changes"}
        </span>
      </summary>
      <div className="mt-2">
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
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [changedOnly, setChangedOnly] = useState(true);
  // Operator picks for part numbers that appear more than once in the pack.
  const [duplicateChoices, setDuplicateChoices] = useState<Record<string, number>>({});
  const [capabilities, setCapabilities] = useState<Capability>({});
  const [capabilitiesError, setCapabilitiesError] = useState("");
  const [dataMode, setDataMode] = useState<DataMode>("fill_blanks");
  const [bomMode, setBomMode] = useState<BomMode>("fill_if_empty");
  const [fileMode, setFileMode] = useState<FileMode>("add_missing");
  const [rootPreviewUrl, setRootPreviewUrl] = useState<string | null>(null);
  const [rootPreviewStatus, setRootPreviewStatus] = useState("");

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

  const approvalMode = APPROVAL_FOR_DATA[dataMode];

  const preset = useMemo<Preset>(() => {
    const match = (Object.entries(PRESETS) as Array<[Exclude<Preset, "custom">, typeof PRESETS[Exclude<Preset, "custom">]]>).find(
      ([, tuple]) => tuple[0] === dataMode && tuple[1] === bomMode && tuple[2] === fileMode,
    );
    return match ? match[0] : "custom";
  }, [dataMode, bomMode, fileMode]);

  function applyPreset(name: Exclude<Preset, "custom">) {
    const [nextData, nextBom, nextFile] = PRESETS[name];
    setDataMode(nextData);
    setBomMode(nextBom);
    setFileMode(nextFile);
  }

  const plan = result?.plan;
  const matchesFilter = (part: PlanPart, name: Filter) => {
    if (name === "changed") return part.changed;
    if (name === "blocked") return part.blocked || !part.allowed;
    // Approved parts the import actually alters — the ones worth reviewing.
    if (name === "modified_approved") return part.target_state === "existing_approved" && part.changed;
    return true;
  };
  const tabCounts = useMemo(() => {
    const parts = plan?.parts || [];
    return {
      all: parts.length,
      changed: parts.filter((part) => matchesFilter(part, "changed")).length,
      blocked: parts.filter((part) => matchesFilter(part, "blocked")).length,
      modified_approved: parts.filter((part) => matchesFilter(part, "modified_approved")).length,
    } as Record<Filter, number>;
  }, [plan]);
  const visibleParts = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return (plan?.parts || []).filter((part) => {
      if (!matchesFilter(part, filter)) return false;
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
    });
  }, [plan, filter, search]);
  // Surfaced at the top of the report so it's obvious at a glance whether approved data was touched.
  const overrideCounts = useMemo(() => {
    let overriding = 0;
    let needsAdmin = 0;
    for (const part of plan?.parts || []) {
      if (part.target_state !== "existing_approved" || !part.changed) continue;
      if (part.allowed) overriding += 1;
      else needsAdmin += 1;
    }
    return { overriding, needsAdmin };
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
        setResult(payload);
        if (payload.capabilities) setCapabilities(payload.capabilities);
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

  const advancedSelected =
    dataMode.includes("replace") ||
    bomMode.includes("replace") ||
    fileMode.includes("replace") ||
    approvalMode !== "preserve";
  const overrideSelected =
    dataMode === "replace_all" || bomMode === "replace_all" || fileMode === "replace_all" || approvalMode === "replace_all";
  // Red whenever approved data could be touched, amber for draft-only updates, green when nothing but blanks fill.
  // Computed from the actual selected modes (not just the preset) so it stays accurate in "Custom".
  const activeTone: Tone = overrideSelected ? "admin" : advancedSelected ? "draft" : "safe";

  return (
    <div className="container-xxl py-3">
      <div className="border-bottom mb-3 pb-2">
        <h4 className="mb-1">Import upload pack</h4>
        <div className="text-muted small">
          Select a ZIP, choose an import policy, preview the exact redline, then apply it.
        </div>
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

        <h6 className="mt-4">2. Select import policy</h6>
        <div className="btn-group" role="group" aria-label="Import tier">
          {(Object.keys(TIER_META) as Array<Exclude<Preset, "custom">>).map((tier) => {
            const tierDisabled = tier === "unless_existing_approved" ? !canAdvanced : tier === "always" ? !canOverride : false;
            const tierTone: Tone = tier === "always" ? "admin" : tier === "unless_existing_approved" ? "draft" : "safe";
            return (
              <button
                key={tier}
                type="button"
                className={`btn ${preset === tier ? TONE_BUTTON[tierTone] : "btn-outline-secondary"}`}
                disabled={tierDisabled}
                onClick={() => applyPreset(tier)}
              >
                {TIER_META[tier].label}
              </button>
            );
          })}
        </div>
        <div className="small text-muted mt-1">
          {preset === "custom" ? "Custom — set via the advanced options below." : TIER_META[preset].hint}
        </div>
        <div className={`alert ${TONE_ALERT[activeTone]} small mt-2 mb-0 fw-semibold`}>
          {activeTone === "admin"
            ? "Admin override active — existing approved parts will be overwritten if they differ."
            : activeTone === "draft"
              ? "Draft (unapproved) parts will be updated. Existing approved parts stay protected."
              : "Safe: only blanks, empty BOMs and missing files are filled. Existing approved parts stay protected."}{" "}
          Any uploader may import a new part that arrives already approved. Changing an
          existing approved part — its properties, BOM or files — always needs the
          override permission, regardless of policy.
        </div>

        <details className="mt-3">
          <summary className="fw-semibold">Advanced: adjust properties, BOM and files individually</summary>
          <div className="row g-3 mt-1">
            <PolicySelect
              id="dataMode"
              label="Properties"
              help="Ordinary, custom and approval fields. Skip writes none of them. Approval follows this policy: any uploader may import a new part that is already approved, but changing one afterwards needs the override."
              value={dataMode}
              onChange={setDataMode}
              options={[
                { value: "skip", label: "Skip" },
                { value: "fill_blanks", label: "Fill only", disabled: !canLowRisk },
                { value: "replace_unapproved", label: "Update drafts", disabled: !canAdvanced },
                { value: "replace_all", label: "Override approved (Admin)", disabled: !canOverride },
              ]}
            />
            <PolicySelect
              id="bomMode"
              label="BOM"
              help="Fill creates a whole BOM only when the exact parent/revision has none. Changing the BOM of an existing approved part needs the override."
              value={bomMode}
              onChange={setBomMode}
              options={[
                { value: "skip", label: "Skip" },
                { value: "fill_if_empty", label: "Fill only", disabled: !canLowRisk },
                { value: "replace_unapproved", label: "Update drafts", disabled: !canAdvanced },
                { value: "replace_all", label: "Override approved (Admin)", disabled: !canOverride },
              ]}
            />
            <PolicySelect
              id="fileMode"
              label="Files"
              help="The same policy applies to managed deliverables and associated files. Replacing a file on an existing approved part needs the override. Files never create parts: anything not listed in the BOM is skipped and reported."
              value={fileMode}
              onChange={setFileMode}
              options={[
                { value: "skip", label: "Skip" },
                { value: "add_missing", label: "Fill only", disabled: !canLowRisk },
                { value: "replace_unapproved", label: "Update drafts", disabled: !canAdvanced },
                { value: "replace_all", label: "Override approved (Admin)", disabled: !canOverride },
              ]}
            />
          </div>
        </details>

        <h6 className="mt-4">3. Preview changes &nbsp; 4. Apply import</h6>
        <div className="d-flex gap-2 flex-wrap">
          <button
            className="btn btn-outline-primary"
            type="button"
            disabled={busy || !file || !canPreview}
            onClick={() => submit(true)}
          >
            Preview changes
          </button>
          <button
            className="btn btn-primary"
            type="button"
            disabled={
              busy ||
              !file ||
              !(canLowRisk || canAdvanced) ||
              (advancedSelected && !canAdvanced) ||
              (overrideSelected && !canOverride)
            }
            onClick={() => submit(false)}
          >
            Apply import
          </button>
          {busy ? <span className="align-self-center text-muted small">Validating and planning…</span> : null}
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

      {plan ? (
        <div className="card p-3">
          <div className="d-flex justify-content-between align-items-start flex-wrap gap-2">
            <div>
              <h5 className="mb-1">{result?.dry_run ? "Preview redline" : "Applied import redline"}</h5>
              <div className="small text-muted">
                {plan.summary.parts} exact part/revisions · {plan.summary.changed} changed ·{" "}
                {plan.summary.blocked} blocked
              </div>
              {overrideCounts.overriding || overrideCounts.needsAdmin ? (
                <div className="small mt-1">
                  {overrideCounts.overriding ? (
                    <span className="badge text-bg-danger me-1">
                      {overrideCounts.overriding} overriding approved
                    </span>
                  ) : null}
                  {overrideCounts.needsAdmin ? (
                    <span className="badge text-bg-warning">{overrideCounts.needsAdmin} need admin to override</span>
                  ) : null}
                </div>
              ) : (
                <div className="small text-success mt-1">No approved data is affected.</div>
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
                one part number. Pick which row to keep, then preview again.
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
                      onChange={(event) =>
                        setDuplicateChoices((prev) => ({
                          ...prev,
                          [key]: Number(event.target.value),
                        }))
                      }
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

          <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
            <div className="btn-group btn-group-sm" role="group" aria-label="Redline filter">
              {(
                [
                  ["all", "All"],
                  ["changed", "Changed"],
                  ["blocked", "Blocked"],
                  ["modified_approved", "Modified approved"],
                ] as Array<[Filter, string]>
              ).map(([name, label]) => (
                <button
                  key={name}
                  type="button"
                  className={`btn ${filter === name ? "btn-secondary" : "btn-outline-secondary"}`}
                  onClick={() => setFilter(name)}
                >
                  {label} <span className="badge text-bg-light text-muted">{tabCounts[name]}</span>
                </button>
              ))}
            </div>
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
          </div>

          <div className="d-flex flex-column gap-2">
            {visibleParts.map((part) => (
              <PartRedline
                key={`${part.part_number}:${part.revision}`}
                part={part}
                changedOnly={changedOnly}
              />
            ))}
            {!visibleParts.length ? (
              <div className="text-muted small">
                {search.trim()
                  ? "No parts match this search in the selected tab."
                  : filter === "modified_approved"
                    ? "No approved parts are altered by this import."
                    : `No parts are ${filter === "blocked" ? "blocked" : "changed"} by this import.`}
              </div>
            ) : null}
          </div>

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

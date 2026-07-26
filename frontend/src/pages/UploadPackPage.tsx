import { useEffect, useMemo, useRef, useState } from "react";
import "./uploadpack.css";

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
type Plan = {
  parts: PlanPart[];
  required_permissions: string[];
  missing_permissions: string[];
  allowed: boolean;
  blocked_change_count: number;
  summary: {
    parts: number;
    new: number;
    changed: number;
    blocked: number;
    approved_targets: number;
  };
};
type UploadResult = {
  zip?: string;
  dry_run?: boolean;
  plan?: Plan;
  import?: {
    root?: string;
    root_rev?: string;
    parts_created?: number;
    parts_updated?: number;
    links_created?: number;
    artifacts_added?: number;
    extra_files_written?: number;
    thumbnails_generated?: number;
    warnings?: Array<{ stage?: string; message?: string }>;
    errors?: Array<{ stage?: string; message?: string }>;
  };
  timings?: Record<string, number>;
  diagnostics?: Record<string, number | boolean>;
  capabilities?: Capability;
  warnings?: Array<string | { stage?: string; message?: string }>;
};

type Filter = "all" | "changed" | "blocked" | "approved";
type DataMode = "skip" | "fill_blanks" | "replace_unapproved" | "replace_all";
type BomMode = "skip" | "fill_if_empty" | "replace_unapproved" | "replace_all";
type FileMode = "skip" | "add_missing" | "replace_unapproved" | "replace_all";
type ApprovalMode = "preserve" | "import_unapproved" | "replace_all";
type Preset = "preserve" | "unless_existing_approved" | "always" | "custom";

// Same three tiers as the backend's legacy override_mode (app/services/import_zip.py):
// quick presets that set all four independent policies at once. Touching an
// individual policy below detaches it from the preset ("Custom").
const PRESETS: Record<Exclude<Preset, "custom">, [DataMode, BomMode, FileMode, ApprovalMode]> = {
  preserve: ["fill_blanks", "fill_if_empty", "add_missing", "preserve"],
  unless_existing_approved: ["replace_unapproved", "replace_unapproved", "replace_unapproved", "preserve"],
  always: ["replace_all", "replace_all", "replace_all", "replace_all"],
};

const stateLabels: Record<PlanPart["target_state"], string> = {
  new: "New",
  existing_unapproved: "Existing unapproved",
  existing_approved: "Existing approved",
};

function valueText(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function actionClass(action: string) {
  if (action === "add") return "text-success";
  if (["remove", "replace", "clear"].includes(action)) return "text-danger";
  if (["blocked", "skipped"].includes(action)) return "text-warning";
  if (["change", "quantity_change"].includes(action)) return "text-primary";
  return "text-muted";
}

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

function ChangeTable({ rows }: { rows: Change[] }) {
  if (!rows.length) return <div className="text-muted small">No incoming values.</div>;
  return (
    <div className="table-responsive">
      <table className="table table-sm align-middle mb-0">
        <thead>
          <tr>
            <th>Field</th>
            <th>Before</th>
            <th>After</th>
            <th>Action</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row.field_id || row.label}-${index}`}>
              <td>
                <div>{row.label || row.field_id}</div>
                {row.source_key ? <small className="text-muted">from {row.source_key}</small> : null}
              </td>
              <td className={row.action === "replace" ? "text-danger" : ""}>{valueText(row.before)}</td>
              <td className={["add", "replace", "change"].includes(row.action) ? "text-primary" : ""}>
                {valueText(row.after)}
              </td>
              <td className={`text-capitalize ${actionClass(row.action)}`}>{row.action.replaceAll("_", " ")}</td>
              <td className="small">{row.reason || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PartRedline({ part }: { part: PlanPart }) {
  return (
    <details className="border rounded p-2 bg-white">
      <summary className="d-flex flex-wrap align-items-center gap-2">
        <strong>
          {part.part_number} — {part.revision || "No revision"}
        </strong>
        <span className={`badge ${part.target_state === "existing_approved" ? "text-bg-warning" : "text-bg-secondary"}`}>
          {stateLabels[part.target_state]}
        </span>
        <span className={`badge ${part.allowed ? "text-bg-success" : "text-bg-danger"}`}>
          {part.allowed ? "Allowed" : "Blocked"}
        </span>
      </summary>
      <div className="mt-3">
        <h6>Properties</h6>
        <ChangeTable rows={part.properties} />
        <h6 className="mt-3">Approval</h6>
        <ChangeTable rows={part.approval} />
        <h6 className="mt-3">BOM</h6>
        <div className={`small mb-1 ${actionClass(part.bom.action)}`}>
          <strong className="text-capitalize">{part.bom.action.replaceAll("_", " ")}</strong>
          {part.bom.reason ? ` — ${part.bom.reason}` : ""}
        </div>
        {part.bom.changes.length ? (
          <ul className="small mb-0">
            {part.bom.changes.map((change, index) => (
              <li className={actionClass(change.action)} key={`${change.part_number}:${change.revision}:${index}`}>
                {change.part_number} {change.revision ? `REV ${change.revision}` : ""}:{" "}
                {change.before_qty ?? "—"} → {change.after_qty ?? "—"} ({change.action.replaceAll("_", " ")})
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-muted small">No incoming BOM definition.</div>
        )}
        <h6 className="mt-3">Files</h6>
        {part.files.length ? (
          <ul className="small mb-0">
            {part.files.map((file, index) => (
              <li className={actionClass(file.action)} key={`${file.kind}:${file.name}:${index}`}>
                <strong>{file.action.toUpperCase()}</strong> {file.category}: {file.name}
                {file.reason ? ` — ${file.reason}` : ""}
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-muted small">No files for this part/revision.</div>
        )}
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
  const [strict, setStrict] = useState(false);
  const [capabilities, setCapabilities] = useState<Capability>({});
  const [dataMode, setDataMode] = useState<DataMode>("fill_blanks");
  const [bomMode, setBomMode] = useState<BomMode>("fill_if_empty");
  const [fileMode, setFileMode] = useState<FileMode>("add_missing");
  const [approvalMode, setApprovalMode] = useState<ApprovalMode>("preserve");
  const [rootPreviewUrl, setRootPreviewUrl] = useState<string | null>(null);
  const [rootPreviewStatus, setRootPreviewStatus] = useState("");

  useEffect(() => {
    fetch("/api/field-config")
      .then((response) => (response.ok ? response.json() : Promise.reject(response)))
      .then((payload) => setCapabilities(payload?.permissions?.imports || {}))
      .catch(() => setCapabilities({}));
  }, []);

  const rootPn = result?.import?.root || "";
  const rootRev = result?.import?.root_rev || "";
  const rootHref = rootPn
    ? `/ui/part/${encodeURIComponent(rootPn)}?rev=${encodeURIComponent(rootRev)}`
    : "";

  useEffect(() => {
    let cancelled = false;
    if (!rootPn) {
      setRootPreviewUrl(null);
      setRootPreviewStatus("");
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
        } else {
          setRootPreviewStatus("No preview image found for the top-level part.");
        }
      })
      .catch(() => {
        if (!cancelled) setRootPreviewStatus("Failed to load preview image.");
      });
    return () => {
      cancelled = true;
    };
  }, [rootPn, rootRev]);

  const canPreview = !!capabilities["imports.preview"];
  const canLowRisk = !!capabilities["imports.execute_low_risk"];
  const canAdvanced = !!capabilities["imports.execute_approved"];
  const canOverride = canAdvanced && !!capabilities["imports.override_approved"];

  const preset = useMemo<Preset>(() => {
    const match = (Object.entries(PRESETS) as Array<[Exclude<Preset, "custom">, typeof PRESETS[Exclude<Preset, "custom">]]>).find(
      ([, tuple]) => tuple[0] === dataMode && tuple[1] === bomMode && tuple[2] === fileMode && tuple[3] === approvalMode,
    );
    return match ? match[0] : "custom";
  }, [dataMode, bomMode, fileMode, approvalMode]);

  function applyPreset(name: Exclude<Preset, "custom">) {
    const [nextData, nextBom, nextFile, nextApproval] = PRESETS[name];
    setDataMode(nextData);
    setBomMode(nextBom);
    setFileMode(nextFile);
    setApprovalMode(nextApproval);
  }

  const plan = result?.plan;
  const visibleParts = useMemo(
    () =>
      (plan?.parts || []).filter((part) => {
        if (filter === "changed") return part.changed;
        if (filter === "blocked") return part.blocked || !part.allowed;
        if (filter === "approved") return part.target_state === "existing_approved";
        return true;
      }),
    [plan, filter],
  );

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
    if (dryRun) form.append("dry_run", "1");
    if (strict) form.append("strict_structure", "1");

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
        <div className="row g-3">
          <div className="col-md-6">
            <label className="form-label fw-semibold mb-1" htmlFor="importPreset">
              Properties, BOM, files and approval
            </label>
            <select
              id="importPreset"
              className="form-select form-select-sm"
              value={preset}
              onChange={(event) => {
                const value = event.target.value as Preset;
                if (value !== "custom") applyPreset(value);
              }}
            >
              <option value="preserve">Fill safely (default)</option>
              <option value="unless_existing_approved" disabled={!canAdvanced}>
                Override if not approved
              </option>
              <option value="always" disabled={!canOverride}>
                Override for admin users
              </option>
              {preset === "custom" ? <option value="custom">Custom (see advanced options below)</option> : null}
            </select>
            <div className="form-text">
              Fill only adds blanks, empty BOMs and missing files without touching approval. Override if not
              approved replaces unapproved targets. Override for admin users also replaces approved targets and
              their approval status. Approved targets can never be filled or replaced without admin permissions,
              no matter which policy is selected.
            </div>
          </div>
        </div>

        <details className="mt-3">
          <summary className="fw-semibold">Advanced: adjust properties, BOM and files individually</summary>
          <div className="row g-3 mt-1">
            <PolicySelect
              id="dataMode"
              label="Properties"
              help="Control ordinary and configured custom fields. Approval is governed separately."
              value={dataMode}
              onChange={setDataMode}
              options={[
                { value: "skip", label: "Skip properties" },
                { value: "fill_blanks", label: "Fill blank values", disabled: !canLowRisk },
                { value: "replace_unapproved", label: "Replace on unapproved targets", disabled: !canAdvanced },
                { value: "replace_all", label: "Replace on all targets (admin)", disabled: !canOverride },
              ]}
            />
            <PolicySelect
              id="bomMode"
              label="BOM"
              help="Fill creates a whole BOM only when the exact parent/revision has none."
              value={bomMode}
              onChange={setBomMode}
              options={[
                { value: "skip", label: "Skip BOM" },
                { value: "fill_if_empty", label: "Fill only if empty", disabled: !canLowRisk },
                { value: "replace_unapproved", label: "Replace unapproved BOMs", disabled: !canAdvanced },
                { value: "replace_all", label: "Replace all BOMs (admin)", disabled: !canOverride },
              ]}
            />
            <PolicySelect
              id="fileMode"
              label="Files"
              help="The same policy applies to managed deliverables and associated files."
              value={fileMode}
              onChange={setFileMode}
              options={[
                { value: "skip", label: "Skip files" },
                { value: "add_missing", label: "Add missing files", disabled: !canLowRisk },
                { value: "replace_unapproved", label: "Replace files on unapproved targets", disabled: !canAdvanced },
                { value: "replace_all", label: "Replace files on all targets (admin)", disabled: !canOverride },
              ]}
            />
            <PolicySelect
              id="approvalMode"
              label="Approval"
              help="Approval aliases are resolved through the configured canonical field rules."
              value={approvalMode}
              onChange={setApprovalMode}
              options={[
                { value: "preserve", label: "Preserve existing approval" },
                { value: "import_unapproved", label: "Import on unapproved targets", disabled: !canAdvanced },
                { value: "replace_all", label: "Replace approval on all targets (admin)", disabled: !canOverride },
              ]}
            />
          </div>
        </details>
        {advancedSelected && !canAdvanced ? (
          <div className="alert alert-warning small mt-3 mb-0">
            Your roles cannot execute replacement effects. Preview remains available and will identify any
            required permissions.
          </div>
        ) : null}
        {overrideSelected && !canOverride ? (
          <div className="alert alert-warning small mt-2 mb-0">
            Your roles cannot modify existing approved targets.
          </div>
        ) : null}
        <div className="form-check mt-3">
          <input
            id="strictImport"
            type="checkbox"
            className="form-check-input"
            checked={strict}
            onChange={(event) => setStrict(event.target.checked)}
          />
          <label className="form-check-label" htmlFor="strictImport">
            Reject unknown package entries
          </label>
        </div>

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
            <a
              href={rootHref}
              className="d-flex align-items-center gap-2 mt-3 p-2 border rounded text-decoration-none"
            >
              {rootPreviewUrl ? (
                <img
                  src={rootPreviewUrl}
                  alt={`${rootPn} preview`}
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
                  Top-level part: {rootPn}
                  {rootRev ? ` — REV ${rootRev}` : ""}
                </div>
                <div className="text-muted">{rootPreviewStatus || "Open part details"}</div>
              </div>
            </a>
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

          <div className="btn-group btn-group-sm mb-3" role="group" aria-label="Redline filter">
            {(["all", "changed", "blocked", "approved"] as Filter[]).map((name) => (
              <button
                key={name}
                type="button"
                className={`btn ${filter === name ? "btn-secondary" : "btn-outline-secondary"}`}
                onClick={() => setFilter(name)}
              >
                {name === "approved" ? "Approved targets" : name[0].toUpperCase() + name.slice(1)}
              </button>
            ))}
          </div>

          <div className="d-flex flex-column gap-2">
            {visibleParts.map((part) => (
              <PartRedline key={`${part.part_number}:${part.revision}`} part={part} />
            ))}
            {!visibleParts.length ? <div className="text-muted small">No redline entries match this filter.</div> : null}
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

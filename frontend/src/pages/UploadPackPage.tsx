import { useEffect, useMemo, useRef, useState } from "react";
import "./uploadpack.css";

type UploadItem = {
  pn: string;
  rev: string;
  imported?: boolean;
  extra_files_added?: number;
  warnings?: string[];
};

type ImportIssue = {
  stage?: string;
  file?: string;
  line_number?: number;
  part_number?: string;
  path?: string;
  message?: string;
  exception_type?: string;
  exception_message?: string;
  traceback?: string;
};

type ImportDataChange = {
  scope?: string;
  field?: string;
  before?: any;
  after?: any;
};

type ImportBomItem = {
  part_number?: string;
  revision?: string;
  qty?: number;
  before_qty?: number;
  after_qty?: number;
};

type ImportFileChange = {
  part_number?: string;
  revision?: string;
  kind?: string;
  action?: string;
  name?: string;
  rel_path?: string;
  ext_group?: string;
  ext?: string;
  changed_fields?: string[];
  label?: string;
};

type ModifiedPartSummary = {
  part_number?: string;
  revision?: string;
  data_changes?: ImportDataChange[];
  bom_changes?: {
    before_children?: number;
    after_children?: number;
    added?: ImportBomItem[];
    removed?: ImportBomItem[];
    qty_changed?: ImportBomItem[];
  } | null;
  file_changes?: ImportFileChange[];
};

type ImportReport = {
  zip?: string;
  flatbom_file?: string;
  treebom_file?: string;
  root?: string;
  root_revision?: string;
  parts_created?: number;
  parts_updated?: number;
  modified_parts_count?: number;
  modified_parts?: ModifiedPartSummary[];
  links_created?: number;
  links_skipped?: number;
  links_removed?: number;
  parts_seeded?: number;
  parts_seeded_list?: Array<{ part_number?: string; revision?: string }>;
  parts_with_props?: number;
  artifacts_added?: number;
  artifacts_found_by_type?: Record<string, number>;
  thumbnails_built?: number;
  thumbnails_generated?: number;
  rows_skipped_blank_part?: number;
  flat_lines_failed_parse?: number;
  flat_lines_skipped_not_dict?: number;
  flat_lines_failed_normalize?: number;
  tree_rows_failed_qty?: number;
  errors?: ImportIssue[];
  warnings?: ImportIssue[];
  timings?: Record<string, { elapsed_s?: number; cpu_s?: number; idle_s?: number }>;
  resources_start?: any;
  resources_end?: any;
};

type UploadResult = {
  zip?: string;
  dry_run?: boolean;
  items?: UploadItem[];
  warnings?: string[];
  deliverables_written?: number;
  extra_files_written?: number;
  import?: ImportReport | null;
  timings?: Record<string, { elapsed_s?: number; cpu_s?: number; idle_s?: number }>;
  resources_start?: any;
  resources_end?: any;
};

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

function parseJsonResponse(xhr: XMLHttpRequest): any {
  if (xhr.response && typeof xhr.response === "object") return xhr.response;
  try {
    return JSON.parse(xhr.responseText || "{}");
  } catch {
    return {};
  }
}

function formatImportIssue(issue: ImportIssue): string {
  const bits: string[] = [];
  if (issue.stage) bits.push(issue.stage);
  if (issue.file) bits.push(issue.file);
  if (issue.line_number) bits.push(`line ${issue.line_number}`);
  if (issue.part_number) bits.push(`pn ${issue.part_number}`);
  if (issue.path) bits.push(issue.path);
  const head = bits.length ? `[${bits.join(" | ")}] ` : "";
  const msg = issue.message || "";
  const exc = issue.exception_message ? ` (${issue.exception_message})` : "";
  return `${head}${msg}${exc}`.trim() || "Unknown issue";
}

function formatChangeValue(value: any): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function formatPartRef(pn?: string, rev?: string): string {
  const partNumber = String(pn || "").trim() || "(blank PN)";
  const revision = String(rev || "").trim();
  return revision ? `${partNumber} REV ${revision}` : partNumber;
}

function downloadJson(filename: string, data: unknown) {
  try {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch {
    // ignore
  }
}

function formatSeconds(value: any): string {
  const n = Number(value || 0);
  if (!isFinite(n) || n <= 0) return "0.00s";
  if (n < 1) return `${(n * 1000).toFixed(0)}ms`;
  return `${n.toFixed(2)}s`;
}

export default function UploadPackPage() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const progressTimer = useRef<number | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [dryRun, setDryRun] = useState(false);
  const [strictStructure, setStrictStructure] = useState(false);
  const [overrideMode, setOverrideMode] = useState<
    "unless_existing_approved" | "preserve" | "approved_only" | "always"
  >("unless_existing_approved");
  const [progressPct, setProgressPct] = useState(0);
  const [progressLabel, setProgressLabel] = useState("Waiting to start...");
  const [showProgress, setShowProgress] = useState(false);
  const [uploadPct, setUploadPct] = useState(0);
  const [uploadBytes, setUploadBytes] = useState(0);
  const [uploadTotal, setUploadTotal] = useState(0);
  const [processingSeconds, setProcessingSeconds] = useState(0);
  const processingTimer = useRef<number | null>(null);
  const [rootPreviewUrl, setRootPreviewUrl] = useState<string | null>(null);
  const [rootPreviewStatus, setRootPreviewStatus] = useState("Preview will appear after import.");

  const items = useMemo(() => result?.items || [], [result]);
  const importSummary = result?.import || null;
  const importErrors = useMemo(
    () => (Array.isArray(importSummary?.errors) ? importSummary?.errors || [] : []),
    [importSummary],
  );
  const importWarnings = useMemo(
    () => (Array.isArray(importSummary?.warnings) ? importSummary?.warnings || [] : []),
    [importSummary],
  );
  const importErrorCount = importErrors.length;
  const importWarningCount = importWarnings.length;
  const importHasIssues = importErrorCount > 0 || importWarningCount > 0;

  const skippedBlankParts = Number(importSummary?.rows_skipped_blank_part ?? 0);
  const flatParseFailures = Number(importSummary?.flat_lines_failed_parse ?? 0);
  const flatNormalizeFailures = Number(importSummary?.flat_lines_failed_normalize ?? 0);
  const treeQtyFailures = Number(importSummary?.tree_rows_failed_qty ?? 0);
  const reportHasDiagnostics =
    skippedBlankParts > 0 || flatParseFailures > 0 || flatNormalizeFailures > 0 || treeQtyFailures > 0;

  const rootPn = importSummary?.root || "";
  const rootRev = importSummary?.root_revision || "";
  const rootHref = rootPn
    ? `/ui/part/${encodeURIComponent(rootPn)}?rev=${encodeURIComponent(rootRev)}`
    : "";

  const filesByTypeEntries = useMemo(() => {
    const map = importSummary?.artifacts_found_by_type;
    if (!map || typeof map !== "object") return [] as Array<[string, number]>;
    return Object.keys(map)
      .sort()
      .map((key) => [key, Number(map[key] || 0)] as [string, number]);
  }, [importSummary]);

  const seededParts = useMemo(() => {
    const list = importSummary?.parts_seeded_list || [];
    return Array.isArray(list) ? list : [];
  }, [importSummary]);
  const modifiedParts = useMemo(() => {
    const list = importSummary?.modified_parts || [];
    return Array.isArray(list) ? list : [];
  }, [importSummary]);

  const topTimings = useMemo(() => {
    const t = result?.timings;
    if (!t || typeof t !== "object") return [] as Array<[string, any]>;
    return Object.entries(t).sort((a, b) => a[0].localeCompare(b[0]));
  }, [result]);

  const bomTimings = useMemo(() => {
    const t = importSummary?.timings;
    if (!t || typeof t !== "object") return [] as Array<[string, any]>;
    return Object.entries(t).sort((a, b) => a[0].localeCompare(b[0]));
  }, [importSummary]);

  useEffect(() => {
    return () => {
      if (progressTimer.current) {
        window.clearInterval(progressTimer.current);
        progressTimer.current = null;
      }
      if (processingTimer.current) {
        window.clearInterval(processingTimer.current);
        processingTimer.current = null;
      }
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!rootPn) {
      setRootPreviewUrl(null);
      setRootPreviewStatus(importSummary ? "No root part reported." : "Preview will appear after import.");
      return () => {
        cancelled = true;
      };
    }
    setRootPreviewUrl(null);
    setRootPreviewStatus("Loading preview...");

    const qs = new URLSearchParams({ pn: rootPn, mode: "preview" });
    qs.set("rev", rootRev || "");
    fetch(`/api/part_images?${qs.toString()}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r)))
      .then((rows) => {
        if (cancelled) return;
        const urls = Array.isArray(rows) && rows.length ? rows[0].urls : [];
        const url = urls && urls.length ? urls[0] : "";
        if (url) {
          setRootPreviewUrl(url);
          setRootPreviewStatus("");
        } else {
          setRootPreviewStatus("No preview image found for the root part.");
        }
      })
      .catch(() => {
        if (!cancelled) setRootPreviewStatus("Failed to load preview image.");
      });

    return () => {
      cancelled = true;
    };
  }, [rootPn, rootRev, importSummary]);

  function onPickFile(files: FileList | null) {
    if (!files || !files.length) return;
    const next = files[0];
    setFile(next);
    setResult(null);
    setError(null);
    setShowProgress(false);
    setProgressPct(0);
    setProgressLabel("Waiting to start...");
    setUploadPct(0);
    setUploadBytes(0);
    setUploadTotal(0);
    setProcessingSeconds(0);
  }

  function stopProgressTimer() {
    if (progressTimer.current) {
      window.clearInterval(progressTimer.current);
      progressTimer.current = null;
    }
  }

  function stopProcessingTimer() {
    if (processingTimer.current) {
      window.clearInterval(processingTimer.current);
      processingTimer.current = null;
    }
  }

  function setProgress(pct: number, label?: string) {
    const clamped = Math.max(1, Math.min(100, pct));
    setProgressPct(clamped);
    if (label) setProgressLabel(label);
  }

  function startIndeterminate(from: number) {
    stopProgressTimer();
    let p = from;
    progressTimer.current = window.setInterval(() => {
      if (p < 90) p += Math.max(1, Math.round((90 - p) * 0.08));
      setProgress(p, "Processing import...");
    }, 700);
  }

  function startProcessingTimer() {
    stopProcessingTimer();
    setProcessingSeconds(0);
    processingTimer.current = window.setInterval(() => {
      setProcessingSeconds((s) => s + 1);
    }, 1000);
  }

  function runImport() {
    if (!file) {
      setError("Select a ZIP file first.");
      return;
    }
    setBusy(true);
    setError(null);
    setResult(null);
    setShowProgress(true);
    setProgress(2, "Starting upload...");
    setUploadPct(0);
    setUploadBytes(0);
    setUploadTotal(0);
    setProcessingSeconds(0);

    const form = new FormData();
    form.append("file", file);
    if (dryRun) form.append("dry_run", "1");
    if (strictStructure) form.append("strict_structure", "1");
    form.append("override_mode", overrideMode);

    let lastPct = 2;
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload/pack");
    xhr.responseType = "json";

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const pct = Math.min(95, Math.round((e.loaded / e.total) * 80));
        lastPct = pct;
        setProgress(pct, `Uploading... ${pct}%`);
        const uploadP = Math.min(100, Math.round((e.loaded / e.total) * 100));
        setUploadPct(uploadP);
        setUploadBytes(e.loaded);
        setUploadTotal(e.total);
      }
    };

    xhr.onload = () => {
      stopProgressTimer();
      stopProcessingTimer();
      const ok = xhr.status >= 200 && xhr.status < 300;
      const data = parseJsonResponse(xhr) || {};
      if (!ok || data?.error) {
        const base = data?.error || `HTTP ${xhr.status}`;
        const detail = data?.detail ? ` (${data.detail})` : "";
        const msg = `${base}${detail}`;
        setError(msg);
        setProgress(100, `Failed: ${msg}`);
      } else {
        setResult(data || {});
        const imp = data?.import;
        const errCount = Array.isArray(imp?.errors) ? imp.errors.length : 0;
        const warnCount = Array.isArray(imp?.warnings) ? imp.warnings.length : 0;
        if (errCount > 0) setProgress(100, `Done (errors: ${errCount})`);
        else if (warnCount > 0) setProgress(100, `Done (warnings: ${warnCount})`);
        else setProgress(100, "Done");
      }
      setBusy(false);
    };

    xhr.onerror = () => {
      stopProgressTimer();
      stopProcessingTimer();
      setError("Network error.");
      setProgress(100, "Network error");
      setBusy(false);
    };

    xhr.upload.onloadend = () => {
      if (uploadPct < 100) setUploadPct(100);
      startIndeterminate(Math.min(85, lastPct || 70));
      startProcessingTimer();
    };

    xhr.send(form);
  }

  const thumbCount = importSummary?.thumbnails_generated ?? importSummary?.thumbnails_built ?? 0;
  const processingStages = [
    "Validating ZIP",
    "Scanning BOM",
    "Writing deliverables",
    "Writing extra files",
    "Importing BOM",
    "Finalizing",
  ];
  const stageIndex = Math.min(Math.floor(processingSeconds / 4), processingStages.length - 1);
  const processingStage = showProgress && busy ? processingStages[stageIndex] : "";

  return (
    <div className="container-xxl py-3">
      <div className="pb-2 border-bottom mb-3">
        <h4 className="mb-0">Import</h4>
        <div className="text-muted small">
          Upload a ZIP with BOM + deliverables + associated files. The system assigns files by Part Number + Revision.
        </div>
      </div>

      <div className="row g-3">
        <div className="col-lg-7">
          <div className="card p-3">
            <h6 className="mb-2">Step 1: Select ZIP</h6>
            <div
              className={`upload-pack-drop ${dragOver ? "drag-over" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                onPickFile(e.dataTransfer.files);
              }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  fileInputRef.current?.click();
                }
              }}
              onClick={() => fileInputRef.current?.click()}
            >
              <div className="fw-semibold">Drag and drop the ZIP here</div>
              <div className="text-muted small">or click to browse</div>
              {file ? (
                <div className="mt-2 small">
                  <strong>{file.name}</strong> ({formatBytes(file.size)})
                </div>
              ) : null}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip"
              className="d-none"
              disabled={busy}
              onChange={(e) => onPickFile(e.target.files)}
            />

            <div className="mt-3">
              <h6 className="mb-2">Step 2: Import</h6>
              <div className="form-check">
                <input
                  className="form-check-input"
                  type="checkbox"
                  id="dryRunCheck"
                  checked={dryRun}
                  onChange={(e) => setDryRun(e.target.checked)}
                />
                <label className="form-check-label" htmlFor="dryRunCheck">
                  Dry run (preview only)
                </label>
              </div>
              <div className="form-check">
                <input
                  className="form-check-input"
                  type="checkbox"
                  id="strictCheck"
                  checked={strictStructure}
                  onChange={(e) => setStrictStructure(e.target.checked)}
                />
                <label className="form-check-label" htmlFor="strictCheck">
                  Strict structure checks
                </label>
              </div>
              <div className="mt-3">
                <div className="fw-semibold small">Existing part data</div>
                <div className="form-check">
                  <input
                    className="form-check-input"
                    type="radio"
                    id="overrideDefault"
                    name="overrideMode"
                    checked={overrideMode === "unless_existing_approved"}
                    onChange={() => setOverrideMode("unless_existing_approved")}
                  />
                  <label className="form-check-label" htmlFor="overrideDefault">
                    Override data unless existing part is approved
                  </label>
                </div>
                <div className="form-check">
                  <input
                    className="form-check-input"
                    type="radio"
                    id="overridePreserve"
                    name="overrideMode"
                    checked={overrideMode === "preserve"}
                    onChange={() => setOverrideMode("preserve")}
                  />
                  <label className="form-check-label" htmlFor="overridePreserve">
                    Keep existing data, only fill blanks
                  </label>
                </div>
                <div className="form-check">
                  <input
                    className="form-check-input"
                    type="radio"
                    id="overrideApproved"
                    name="overrideMode"
                    checked={overrideMode === "approved_only"}
                    onChange={() => setOverrideMode("approved_only")}
                  />
                  <label className="form-check-label" htmlFor="overrideApproved">
                    Override only when the incoming part is approved
                  </label>
                </div>
                <div className="form-check">
                  <input
                    className="form-check-input"
                    type="radio"
                    id="overrideAlways"
                    name="overrideMode"
                    checked={overrideMode === "always"}
                    onChange={() => setOverrideMode("always")}
                  />
                  <label className="form-check-label" htmlFor="overrideAlways">
                    Always override importable part data
                  </label>
                </div>
                <div className="text-muted small mt-1">
                  Internal notes and comments are preserved even when import data overrides other fields.
                </div>
              </div>
              <button className="btn btn-primary mt-3" onClick={runImport} disabled={busy}>
                {busy ? "Importing..." : "Import"}
              </button>
              {error && <div className="text-danger small mt-2">{error}</div>}
            </div>

            {showProgress && (
              <div className="mt-3">
                {uploadTotal > 0 ? (
                  <>
                    <div className="small text-muted mb-1">Upload progress</div>
                    <div className="progress" style={{ height: 10 }}>
                      <div
                        className="progress-bar"
                        role="progressbar"
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={uploadPct}
                        style={{ width: `${Math.max(1, uploadPct)}%` }}
                      />
                    </div>
                    <div className="small text-muted mt-1">
                      {formatBytes(uploadBytes)} / {formatBytes(uploadTotal)} ({uploadPct}%)
                    </div>
                  </>
                ) : null}
                <div className="progress" style={{ height: 10 }}>
                  <div
                    className="progress-bar progress-bar-striped progress-bar-animated"
                    role="progressbar"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={progressPct}
                    style={{ width: `${Math.max(1, progressPct)}%` }}
                  />
                </div>
                <div className="small text-muted mt-2">
                  {processingStage
                    ? `${processingStage} • ${processingSeconds}s`
                    : progressLabel}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="col-lg-5">
          {importSummary ? (
            <div className="card p-3">
              <h6 className="mb-2">Root part preview</h6>
              {rootPreviewUrl ? (
                <img
                  src={rootPreviewUrl}
                  alt={rootPn ? `${rootPn} preview` : "Root preview"}
                  className="img-fluid border rounded"
                />
              ) : (
                <div className="text-muted small">{rootPreviewStatus}</div>
              )}
              {rootPn ? (
                <div className="small mt-2">
                  <div>
                    Root: <code>{rootPn}</code>
                    {rootRev ? <span className="ms-2">REV {rootRev}</span> : null}
                  </div>
                  <a href={rootHref}>Open part details</a>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="card p-3">
              <h6 className="mb-2">Expected ZIP structure</h6>
              <pre className="small mb-0">
{`bom/
  *_FLATBOM.txt
  *_TREEBOM.txt
deliverables/
  pdf/PN_REV_A.pdf
  step/PN_REV_A.step
extra/
  PN/A/scan.e57
  PN/__no_rev__/photo.jpg`}
              </pre>
              <div className="text-muted small mt-2">
                If revision is empty, use the <code>__no_rev__</code> token in paths.
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="card p-3 mt-3">
        <h6 className="mb-2">Results</h6>
        {result ? (
          <>
            <div className="small text-muted mb-2">
              {result.dry_run ? "Dry run only." : "Import complete."}{" "}
              {result.deliverables_written !== undefined
                ? `Deliverables: ${result.deliverables_written}.`
                : ""}
              {result.extra_files_written !== undefined
                ? ` Extra files: ${result.extra_files_written}.`
                : ""}
            </div>

            <div className="small">
              <div>
                ZIP: <code>{result.zip || "-"}</code>
              </div>
            {importSummary ? (
              <>
                  <div>
                    Root: <code>{rootPn || "-"}</code>
                    {rootPn ? (
                      <a className="ms-2" href={rootHref}>
                        Open part details
                      </a>
                    ) : null}
                  </div>
                  <div>
                    Parts created: <b>{importSummary.parts_created ?? 0}</b>, updated:{" "}
                    <b>{importSummary.parts_updated ?? 0}</b>
                  </div>
                  <div>
                    Existing parts modified: <b>{importSummary.modified_parts_count ?? modifiedParts.length}</b>
                  </div>
                  <div>
                    Parts seeded: <b>{importSummary.parts_seeded ?? 0}</b>
                  </div>
                  <div>
                    Links created: <b>{importSummary.links_created ?? 0}</b>, skipped:{" "}
                    <b>{importSummary.links_skipped ?? 0}</b>
                  </div>
                  <div>
                    Parts with properties: <b>{importSummary.parts_with_props ?? 0}</b>
                  </div>
                  <div>
                    Artifacts added: <b>{importSummary.artifacts_added ?? 0}</b>, thumbnails:{" "}
                    <b>{thumbCount}</b>
                  </div>
                </>
              ) : (
                <div className="text-muted">Import summary is available after a non-dry run upload.</div>
              )}
            </div>

            {(topTimings.length > 0 || bomTimings.length > 0) && (
              <div className="mt-2">
                <details>
                  <summary>Timing diagnostics</summary>
                  {topTimings.length > 0 && (
                    <div className="mt-2">
                      <div className="fw-semibold">Upload pack</div>
                      <table className="table table-sm w-auto mb-0">
                        <thead>
                          <tr>
                            <th>Stage</th>
                            <th>Elapsed</th>
                            <th>CPU</th>
                            <th>Idle</th>
                          </tr>
                        </thead>
                        <tbody>
                          {topTimings.map(([k, v]) => (
                            <tr key={k}>
                              <td>{k}</td>
                              <td>{formatSeconds(v?.elapsed_s)}</td>
                              <td>{formatSeconds(v?.cpu_s)}</td>
                              <td>{formatSeconds(v?.idle_s)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {bomTimings.length > 0 && (
                    <div className="mt-2">
                      <div className="fw-semibold">BOM import</div>
                      <table className="table table-sm w-auto mb-0">
                        <thead>
                          <tr>
                            <th>Stage</th>
                            <th>Elapsed</th>
                            <th>CPU</th>
                            <th>Idle</th>
                          </tr>
                        </thead>
                        <tbody>
                          {bomTimings.map(([k, v]) => (
                            <tr key={k}>
                              <td>{k}</td>
                              <td>{formatSeconds(v?.elapsed_s)}</td>
                              <td>{formatSeconds(v?.cpu_s)}</td>
                              <td>{formatSeconds(v?.idle_s)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </details>
              </div>
            )}

            {seededParts.length > 0 && (
              <div className="mt-2">
                <details>
                  <summary>Seeded parts</summary>
                  <ul className="small mb-0">
                    {seededParts.map((item: any) => (
                      <li key={`${item.part_number || ""}:${item.revision || ""}`}>
                        {item.part_number || ""}
                        {item.revision ? ` REV ${item.revision}` : ""}
                      </li>
                    ))}
                  </ul>
                </details>
              </div>
            )}

            {filesByTypeEntries.length > 0 && (
              <div className="mt-3">
                <h6 className="mb-2">Files found by type</h6>
                <table className="table table-sm w-auto mb-0">
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filesByTypeEntries.map(([key, count]) => (
                      <tr key={key}>
                        <td>{key}</td>
                        <td>{count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {modifiedParts.length > 0 && (
              <div className="mt-3">
                <h6 className="mb-2">Modified existing parts</h6>
                <div className="text-muted small mb-2">
                  Field, BOM, and file changes detected while updating existing part records.
                </div>
                <div className="d-flex flex-column gap-2">
                  {modifiedParts.map((part) => {
                    const dataChanges = Array.isArray(part.data_changes) ? part.data_changes : [];
                    const bomChanges = part.bom_changes || null;
                    const fileChanges = Array.isArray(part.file_changes) ? part.file_changes : [];
                    return (
                      <details
                        key={`${part.part_number || ""}:${part.revision || ""}`}
                        className="border rounded p-2"
                      >
                        <summary className="fw-semibold">
                          {formatPartRef(part.part_number, part.revision)}
                          <span className="text-muted ms-2 small">
                            {dataChanges.length ? `${dataChanges.length} field change${dataChanges.length === 1 ? "" : "s"}` : ""}
                            {dataChanges.length && (bomChanges || fileChanges.length) ? " · " : ""}
                            {bomChanges ? "BOM updated" : ""}
                            {bomChanges && fileChanges.length ? " · " : ""}
                            {fileChanges.length ? `${fileChanges.length} file change${fileChanges.length === 1 ? "" : "s"}` : ""}
                          </span>
                        </summary>

                        {dataChanges.length > 0 && (
                          <div className="mt-2">
                            <div className="fw-semibold small">Field changes</div>
                            <ul className="small mb-0">
                              {dataChanges.map((change, idx) => (
                                <li key={`data-${idx}`}>
                                  {change.scope === "attribute" ? "Attribute" : "Part"} <code>{change.field || "-"}</code>:{" "}
                                  <span className="text-muted">{formatChangeValue(change.before)}</span> to{" "}
                                  <span>{formatChangeValue(change.after)}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {bomChanges && (
                          <div className="mt-2">
                            <div className="fw-semibold small">
                              BOM changes ({bomChanges.before_children ?? 0} to {bomChanges.after_children ?? 0} children)
                            </div>
                            {Array.isArray(bomChanges.added) && bomChanges.added.length > 0 && (
                              <div className="small">
                                Added:{" "}
                                {bomChanges.added
                                  .map((item) => `${formatPartRef(item.part_number, item.revision)} x ${item.qty ?? 0}`)
                                  .join(", ")}
                              </div>
                            )}
                            {Array.isArray(bomChanges.removed) && bomChanges.removed.length > 0 && (
                              <div className="small">
                                Removed:{" "}
                                {bomChanges.removed
                                  .map((item) => `${formatPartRef(item.part_number, item.revision)} x ${item.qty ?? 0}`)
                                  .join(", ")}
                              </div>
                            )}
                            {Array.isArray(bomChanges.qty_changed) && bomChanges.qty_changed.length > 0 && (
                              <div className="small">
                                Qty changed:{" "}
                                {bomChanges.qty_changed
                                  .map(
                                    (item) =>
                                      `${formatPartRef(item.part_number, item.revision)} ${item.before_qty ?? 0} to ${item.after_qty ?? 0}`,
                                  )
                                  .join(", ")}
                              </div>
                            )}
                          </div>
                        )}

                        {fileChanges.length > 0 && (
                          <div className="mt-2">
                            <div className="fw-semibold small">File changes</div>
                            <ul className="small mb-0">
                              {fileChanges.map((change, idx) => (
                                <li key={`file-${idx}`}>
                                  {String(change.action || "updated").toUpperCase()} {change.kind || "file"}:{" "}
                                  {change.name || change.rel_path || `${change.ext_group || "file"}.${change.ext || ""}`}
                                  {change.changed_fields && change.changed_fields.length
                                    ? ` (${change.changed_fields.join(", ")})`
                                    : ""}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </details>
                    );
                  })}
                </div>
              </div>
            )}

            {importSummary && (
              <div className="mt-3">
                {rootPreviewStatus ? (
                  <div className="text-muted small mb-2">{rootPreviewStatus}</div>
                ) : null}
                {rootPreviewUrl && rootHref ? (
                  <a className="d-inline-block" href={rootHref}>
                    <img
                      src={rootPreviewUrl}
                      className="img-fluid border rounded"
                      alt="Root preview"
                      style={{ maxWidth: "40vw" }}
                    />
                  </a>
                ) : null}
              </div>
            )}

            {importSummary && (importHasIssues || reportHasDiagnostics) ? (
              <div className={`alert ${importErrorCount ? "alert-danger" : "alert-warning"} small mt-3`}>
                <div className="fw-semibold mb-1">
                  Import completed
                  {importErrorCount ? ` with ${importErrorCount} error${importErrorCount === 1 ? "" : "s"}` : ""}
                  {importWarningCount
                    ? `${importErrorCount ? " and " : " with "}${importWarningCount} warning${
                        importWarningCount === 1 ? "" : "s"
                      }`
                    : ""}
                  {!importErrorCount && !importWarningCount ? " (with warnings)" : ""}.
                </div>
                {reportHasDiagnostics ? (
                  <div className="text-muted">
                    Skipped blank PN rows: <b>{skippedBlankParts}</b>. FLATBOM parse failures:{" "}
                    <b>{flatParseFailures}</b>. FLATBOM normalize failures: <b>{flatNormalizeFailures}</b>. TREEBOM qty
                    failures: <b>{treeQtyFailures}</b>.
                  </div>
                ) : null}
                <div className="mt-2">
                  <button
                    className="btn btn-sm btn-outline-secondary"
                    type="button"
                    onClick={() => downloadJson(`import_report_${result?.zip || "report"}.json`, importSummary)}
                  >
                    Download report JSON
                  </button>
                </div>
                {importHasIssues ? (
                  <div className="mt-2">
                    <details>
                      <summary>Show import issues</summary>
                      {importErrorCount ? (
                        <div className="mt-2">
                          <div className="fw-semibold">Errors</div>
                          <ul className="mb-0">
                            {importErrors.slice(0, 50).map((it, idx) => (
                              <li key={`err-${idx}`}>{formatImportIssue(it)}</li>
                            ))}
                          </ul>
                          {importErrorCount > 50 ? (
                            <div className="text-muted mt-1">Showing first 50 errors.</div>
                          ) : null}
                        </div>
                      ) : null}
                      {importWarningCount ? (
                        <div className="mt-2">
                          <div className="fw-semibold">Warnings</div>
                          <ul className="mb-0">
                            {importWarnings.slice(0, 50).map((it, idx) => (
                              <li key={`warn-${idx}`}>{formatImportIssue(it)}</li>
                            ))}
                          </ul>
                          {importWarningCount > 50 ? (
                            <div className="text-muted mt-1">Showing first 50 warnings.</div>
                          ) : null}
                        </div>
                      ) : null}
                    </details>
                  </div>
                ) : null}
              </div>
            ) : null}

            {result.warnings && result.warnings.length ? (
              <div className="alert alert-warning small mt-3">
                <div className="fw-semibold mb-1">Warnings</div>
                <ul className="mb-0">
                  {result.warnings.map((w, idx) => (
                    <li key={`${idx}-${w}`}>{w}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {items.length ? (
              <div className="table-responsive mt-2">
                <table className="table table-sm">
                  <thead>
                    <tr>
                      <th>Part Number</th>
                      <th>Rev</th>
                      <th>Imported</th>
                      <th>Extra files</th>
                      <th>Warnings</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => (
                      <tr key={`${item.pn}:${item.rev}`}>
                        <td>{item.pn}</td>
                        <td>{item.rev || "-"}</td>
                        <td>{item.imported ? "Yes" : "No"}</td>
                        <td>{item.extra_files_added ?? 0}</td>
                        <td>
                          {item.warnings && item.warnings.length ? (
                            <ul className="mb-0 small">
                              {item.warnings.map((w, idx) => (
                                <li key={`${idx}-${w}`}>{w}</li>
                              ))}
                            </ul>
                          ) : (
                            "-"
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-muted small mt-2">No results yet.</div>
            )}
          </>
        ) : (
          <div className="text-muted small">No results yet.</div>
        )}
      </div>
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import "./uploadpack.css";

type UploadItem = {
  pn: string;
  rev: string;
  imported?: boolean;
  extra_files_added?: number;
  warnings?: string[];
};

type UploadResult = {
  zip?: string;
  dry_run?: boolean;
  items?: UploadItem[];
  warnings?: string[];
  deliverables_written?: number;
  extra_files_written?: number;
  import?: any;
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
  const [progressPct, setProgressPct] = useState(0);
  const [progressLabel, setProgressLabel] = useState("Waiting to start...");
  const [showProgress, setShowProgress] = useState(false);
  const [rootPreviewUrl, setRootPreviewUrl] = useState<string | null>(null);
  const [rootPreviewStatus, setRootPreviewStatus] = useState("Preview will appear after import.");

  const items = useMemo(() => result?.items || [], [result]);
  const importSummary = result?.import || null;
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

  useEffect(() => {
    return () => {
      if (progressTimer.current) {
        window.clearInterval(progressTimer.current);
        progressTimer.current = null;
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
  }

  function stopProgressTimer() {
    if (progressTimer.current) {
      window.clearInterval(progressTimer.current);
      progressTimer.current = null;
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

    const form = new FormData();
    form.append("file", file);
    if (dryRun) form.append("dry_run", "1");
    if (strictStructure) form.append("strict_structure", "1");

    let lastPct = 2;
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload/pack");
    xhr.responseType = "json";

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const pct = Math.min(95, Math.round((e.loaded / e.total) * 80));
        lastPct = pct;
        setProgress(pct, `Uploading... ${pct}%`);
      }
    };

    xhr.onload = () => {
      stopProgressTimer();
      const ok = xhr.status >= 200 && xhr.status < 300;
      const data = parseJsonResponse(xhr) || {};
      if (!ok || data?.error) {
        const msg = data?.error || `HTTP ${xhr.status}`;
        setError(msg);
        setProgress(100, `Failed: ${msg}`);
      } else {
        setResult(data || {});
        setProgress(100, "Done");
      }
      setBusy(false);
    };

    xhr.onerror = () => {
      stopProgressTimer();
      setError("Network error.");
      setProgress(100, "Network error");
      setBusy(false);
    };

    xhr.upload.onloadend = () => {
      startIndeterminate(Math.min(85, lastPct || 70));
    };

    xhr.send(form);
  }

  const thumbCount = importSummary?.thumbnails_generated ?? importSummary?.thumbnails_built ?? 0;

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
              <button className="btn btn-primary mt-3" onClick={runImport} disabled={busy}>
                {busy ? "Importing..." : "Import"}
              </button>
              {error && <div className="text-danger small mt-2">{error}</div>}
            </div>

            {showProgress && (
              <div className="mt-3">
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
                <div className="small text-muted mt-2">{progressLabel}</div>
              </div>
            )}
          </div>
        </div>

        <div className="col-lg-5">
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
                      <a className="ms-2" href={rootHref} target="_blank" rel="noreferrer">
                        Open part details
                      </a>
                    ) : null}
                  </div>
                  <div>
                    Parts created: <b>{importSummary.parts_created ?? 0}</b>, updated:{" "}
                    <b>{importSummary.parts_updated ?? 0}</b>
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

            {importSummary && (
              <div className="mt-3">
                {rootPreviewStatus ? (
                  <div className="text-muted small mb-2">{rootPreviewStatus}</div>
                ) : null}
                {rootPreviewUrl && rootHref ? (
                  <a className="d-inline-block" href={rootHref} target="_blank" rel="noreferrer">
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

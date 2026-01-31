import { useMemo, useRef, useState } from "react";
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

export default function UploadPackPage() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [dryRun, setDryRun] = useState(false);
  const [strictStructure, setStrictStructure] = useState(false);

  const items = useMemo(() => result?.items || [], [result]);

  function onPickFile(files: FileList | null) {
    if (!files || !files.length) return;
    const next = files[0];
    setFile(next);
    setResult(null);
    setError(null);
  }

  async function runImport() {
    if (!file) {
      setError("Select a ZIP file first.");
      return;
    }
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      if (dryRun) form.append("dry_run", "1");
      if (strictStructure) form.append("strict_structure", "1");
      const resp = await fetch("/api/upload/pack", { method: "POST", body: form });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        const msg = data?.error || `HTTP ${resp.status}`;
        throw new Error(msg);
      }
      setResult(data || {});
    } catch (err: any) {
      setError(err?.message || "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container-xxl py-3">
      <div className="pb-2 border-bottom mb-3">
        <h4 className="mb-0">Upload Pack</h4>
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
            {result.warnings && result.warnings.length ? (
              <div className="alert alert-warning small">
                <div className="fw-semibold mb-1">Warnings</div>
                <ul className="mb-0">
                  {result.warnings.map((w, idx) => (
                    <li key={`${idx}-${w}`}>{w}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {items.length ? (
              <div className="table-responsive">
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
              <div className="text-muted small">No results yet.</div>
            )}
          </>
        ) : (
          <div className="text-muted small">No results yet.</div>
        )}
      </div>
    </div>
  );
}

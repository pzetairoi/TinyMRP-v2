import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { loadFieldConfig } from '../lib/fieldConfig'

type Summary = {
  counts: { total_parts: number; updated_7d: number; approved: number }
  doc_coverage: { pdf: number; png: number; dxf: number; step: number; datasheet: number }
  data_health: { missing_material: number; missing_process: number; missing_description: number }
  top_processes: { process: string; count: number }[]
  recent_parts: { part_number: string; revision: string; description: string; updated_at: string }[]
  top_hardware: { part_number: string; revision: string; description: string; where_used_count: number; total_qty: number }[]
}

export default function DashboardPage() {
  const [data, setData] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [canAdmin, setCanAdmin] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch('/api/dashboard/summary')
        if (!res.ok) throw new Error(await res.text())
        const j = await res.json()
        if (!cancelled) setData(j as Summary)
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load dashboard')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const resp = await loadFieldConfig()
        if (!cancelled) setCanAdmin(!!resp.permissions?.can_admin)
      } catch {}
    })()
    return () => { cancelled = true }
  }, [])

  const totals = data?.counts || { total_parts: 0, updated_7d: 0, approved: 0 }
  const doc = data?.doc_coverage || { pdf: 0, png: 0, dxf: 0, step: 0, datasheet: 0 }
  const health = data?.data_health || { missing_material: 0, missing_process: 0, missing_description: 0 }

  const docPct = useMemo(() => {
    const total = totals.total_parts || 0
    if (!total) return 0
    return Math.round((doc.pdf / total) * 100)
  }, [doc.pdf, totals.total_parts])

  if (loading) {
    return <div className="text-muted">Loading dashboard...</div>
  }
  if (error) {
    return <div className="text-danger">Dashboard error: {error}</div>
  }

  return (
    <div>
      <div className="d-flex align-items-center justify-content-between mb-3">
        <h4 className="mb-0">Dashboard</h4>
        <div className="text-muted small">Quick health snapshot</div>
      </div>

      <div className="row g-3">
        <div className="col-md-3">
          <div className="card p-3 h-100">
            <div className="text-muted small">Total parts</div>
            <div className="fs-4 fw-semibold">{totals.total_parts}</div>
          </div>
        </div>
        <div className="col-md-3">
          <div className="card p-3 h-100">
            <div className="text-muted small">Updated last 7d</div>
            <div className="fs-4 fw-semibold">{totals.updated_7d}</div>
          </div>
        </div>
        <div className="col-md-3">
          <div className="card p-3 h-100">
            <div className="text-muted small">Doc coverage (PDF)</div>
            <div className="fs-4 fw-semibold">{docPct}%</div>
            <div className="small text-muted">PDF {doc.pdf} of {totals.total_parts}</div>
          </div>
        </div>
        <div className="col-md-3">
          <div className="card p-3 h-100">
            <div className="text-muted small">Release signals</div>
            <div className="fs-4 fw-semibold">{totals.approved}</div>
            <div className="small text-muted">Approved or signed off</div>
          </div>
        </div>
      </div>

      <div className="row g-3 mt-1">
        {canAdmin && (
          <div className="col-lg-4">
            <div className="card p-3 h-100">
              <div className="fw-semibold">Field Configuration</div>
              <div className="small text-muted mt-2">
                Manage JSON field mapping, default columns, and Excel BOM field presets.
              </div>
              <div className="mt-3">
                <Link className="btn btn-sm btn-outline-primary" to="/ui/admin/fields">
                  Open field admin
                </Link>
              </div>
            </div>
          </div>
        )}
        <div className="col-lg-4">
          <div className="card p-3 h-100">
            <div className="d-flex justify-content-between align-items-center">
              <div className="fw-semibold">Data health</div>
              <span className="text-muted small">Missing fields</span>
            </div>
            <div className="mt-2 small">
              <div>Material: <span className="fw-semibold">{health.missing_material}</span></div>
              <div>Process: <span className="fw-semibold">{health.missing_process}</span></div>
              <div>Description: <span className="fw-semibold">{health.missing_description}</span></div>
            </div>
            <div className="mt-3 fw-semibold">Top processes</div>
            <div className="mt-2 d-flex flex-wrap gap-2">
              {(data?.top_processes || []).map((p) => (
                <span key={p.process} className="badge bg-light text-dark">
                  {p.process} ({p.count})
                </span>
              ))}
              {(!data?.top_processes || !data.top_processes.length) && (
                <span className="text-muted small">No process data yet.</span>
              )}
            </div>
          </div>
        </div>

        <div className="col-lg-8">
          <div className="card p-3 h-100">
            <div className="fw-semibold">Doc coverage breakdown</div>
            <div className="row mt-2 g-2 small">
              <div className="col-6 col-md-4">PDF: <span className="fw-semibold">{doc.pdf}</span></div>
              <div className="col-6 col-md-4">PNG: <span className="fw-semibold">{doc.png}</span></div>
              <div className="col-6 col-md-4">DXF: <span className="fw-semibold">{doc.dxf}</span></div>
              <div className="col-6 col-md-4">STEP: <span className="fw-semibold">{doc.step}</span></div>
              <div className="col-6 col-md-4">Datasheet: <span className="fw-semibold">{doc.datasheet}</span></div>
            </div>
            <div className="mt-3 text-muted small">Counts are per part revision with at least one deliverable.</div>
          </div>
        </div>
      </div>

      <div className="row g-3 mt-1">
        <div className="col-lg-6">
          <div className="card p-3 h-100">
            <div className="fw-semibold mb-2">Recently updated parts</div>
            <div className="table-responsive">
              <table className="table table-sm align-middle mb-0">
                <thead>
                  <tr>
                    <th>Part</th>
                    <th>Rev</th>
                    <th>Description</th>
                    <th>Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {(data?.recent_parts || []).map((row) => (
                    <tr key={`${row.part_number}:${row.revision}`}>
                      <td>
                        <Link to={`/ui/part/${encodeURIComponent(row.part_number)}?rev=${encodeURIComponent(row.revision || '')}`}>
                          {row.part_number}
                        </Link>
                      </td>
                      <td>{row.revision || '-'}</td>
                      <td className="text-truncate" style={{ maxWidth: 240 }}>{row.description || '-'}</td>
                      <td className="text-muted small">
                        {row.updated_at ? new Date(row.updated_at).toLocaleString() : '-'}
                      </td>
                    </tr>
                  ))}
                  {(!data?.recent_parts || !data.recent_parts.length) && (
                    <tr><td colSpan={4} className="text-muted small">No recent parts.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="col-lg-6">
          <div className="card p-3 h-100">
            <div className="fw-semibold mb-2">Top hardware used</div>
            <div className="table-responsive">
              <table className="table table-sm align-middle mb-0">
                <thead>
                  <tr>
                    <th>Part</th>
                    <th>Rev</th>
                    <th>Description</th>
                    <th>Used in</th>
                    <th>Total qty</th>
                  </tr>
                </thead>
                <tbody>
                  {(data?.top_hardware || []).map((row) => (
                    <tr key={`${row.part_number}:${row.revision}`}>
                      <td>
                        <Link to={`/ui/part/${encodeURIComponent(row.part_number)}?rev=${encodeURIComponent(row.revision || '')}`}>
                          {row.part_number}
                        </Link>
                      </td>
                      <td>{row.revision || '-'}</td>
                      <td className="text-truncate" style={{ maxWidth: 220 }}>{row.description || '-'}</td>
                      <td>{row.where_used_count}</td>
                      <td>{row.total_qty}</td>
                    </tr>
                  ))}
                  {(!data?.top_hardware || !data.top_hardware.length) && (
                    <tr><td colSpan={5} className="text-muted small">No hardware usage yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

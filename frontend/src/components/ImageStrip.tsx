import { useEffect, useState } from "react"

type ApiRow = { urls: string[]; best?: string; revision?: string }

export default function ImageStrip({ pn, rev, urls }: { pn?: string; rev?: string; urls?: any }) {
  const list: string[] = Array.isArray(urls) ? urls : []
  const [rows, setRows] = useState<ApiRow[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const qs = new URLSearchParams({ pn })
        // pass rev even if empty string so backend can prefer exact rev (‘’ means “no rev”)
        if (rev !== undefined) qs.set("rev", String(rev))
        const r = await fetch(`/api/part_images?${qs.toString()}`)
        if (!r.ok) throw new Error(await r.text())
        const j: ApiRow[] = await r.json()
        if (!cancelled) setRows(j || [])
      } catch (e) {
        console.error("ImageStrip fetch failed", e)
        if (!cancelled) setRows([])
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [pn, rev])

  if (loading) return <div className="text-muted small mb-3">Loading images…</div>
  if (!rows.length) return <div className="text-muted small mb-3">No images.</div>

  return (
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
      {rows.map((row, i) => (
        <FallbackImg key={i} urls={row.urls} />
      ))}
    </div>
  )
}

function FallbackImg({ urls }: { urls: string[] }) {
  const [idx, setIdx] = useState(0)
  const src = urls[idx]

  // If first URL (HTTP server) fails (404/401/etc), try token fallback automatically
  const onErr = () => {
    if (idx < urls.length - 1) setIdx(idx + 1)
  }

  return (
    <img
      src={src}
      onError={onErr}
      alt=""
      style={{
        maxHeight: 160,
        maxWidth: 240,
        objectFit: "contain",
        border: "1px solid rgba(0,0,0,.08)",
        borderRadius: 8,
        padding: 6,
        background: "white",
      }}
    />
  )
}

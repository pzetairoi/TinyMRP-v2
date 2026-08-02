// frontend/src/components/ImageStrip.tsx
import { useEffect, useState } from "react"
import { apiErrorMessage, apiFetch } from "../lib/api"
type ApiRow = { urls: string[] }

type Props = {
  pn: string
  rev?: string
  mode?: 'preview' | 'drawing'
  endpointBase?: string
  limit?: number         // render first N only when provided
  fit?: boolean          // when true, image fills parent (hero use)
  cacheBust?: string | number
}

export default function ImageStrip({ pn, rev = '', mode = 'preview', endpointBase = '/api/part_images', limit, fit = false, cacheBust }: Props) {
  const [rows, setRows] = useState<ApiRow[]>([])
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false
    ;(async ()=>{
      const qs = new URLSearchParams({ pn, mode })  // <--- tell backend which set we want
      if (rev !== undefined) qs.set('rev', rev)
      setError(null)
      try {
        const j = await apiFetch<ApiRow[]>(`${endpointBase}?${qs.toString()}`)
        if (!cancelled) setRows(Array.isArray(j) ? j : [])
      } catch (err) {
        if (!cancelled) {
          setRows([])
          setError(apiErrorMessage(err, 'Failed to load part images.'))
        }
      }
    })()
    return ()=>{cancelled=true}
  }, [pn, rev, mode, endpointBase, cacheBust])

  const list = rows.length
    ? (typeof limit === 'number' ? rows.slice(0, Math.max(0, limit)) : rows)
    : [{ urls: [] }]
  const wrapStyle = fit
    ? { display:'block', width:'100%', height:'100%' }
    : { display:'flex', gap:12, flexWrap:'wrap', marginBottom:16 }
  return (
    <div style={wrapStyle as any}>
      {error && <div className="text-danger small" role="alert">{error}</div>}
      {list.map((row, i) => <FallbackImg key={i} urls={row.urls} fit={fit} cacheBust={cacheBust} />)}
    </div>
  )
}

function withCacheBust(url: string, cacheBust: string | number | undefined): string {
  if (!url || cacheBust === undefined || cacheBust === null || url.startsWith("/branding/")) return url
  const cb = encodeURIComponent(String(cacheBust))
  return url + (url.includes("?") ? "&" : "?") + "t=" + cb
}

function FallbackImg({ urls, fit, cacheBust }:{ urls:string[]; fit?: boolean; cacheBust?: string | number }) {
  const [idx, setIdx] = useState(0)
  const fallback = "/branding/logo"
  const rawSrc = urls.length && idx < urls.length ? urls[idx] : fallback
  const src = withCacheBust(rawSrc, cacheBust)
  const baseStyle = fit
    ? { height:'100%', width:'100%', objectFit:'contain', display:'block' }
    : { maxHeight:160, maxWidth:240, objectFit:'contain', border:'1px solid rgba(0,0,0,.08)', borderRadius:8, padding:6 }
  const onErr = () => {
    if (urls.length && idx < urls.length - 1) {
      setIdx(idx + 1)
    }
  }
  return (
    <img
      src={src}
      onError={onErr}
      style={baseStyle as any}
      alt=""
    />
  )
}

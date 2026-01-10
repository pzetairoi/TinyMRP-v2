// frontend/src/components/ImageStrip.tsx
import { useEffect, useState } from "react"
type ApiRow = { urls: string[] }

type Props = {
  pn: string
  rev?: string
  mode?: 'preview' | 'drawing'
  limit?: number         // render first N only when provided
  fit?: boolean          // when true, image fills parent (hero use)
}

export default function ImageStrip({ pn, rev = '', mode = 'preview', limit, fit = false }: Props) {
  const [rows, setRows] = useState<ApiRow[]>([])
  useEffect(() => {
    let cancelled = false
    ;(async ()=>{
      const qs = new URLSearchParams({ pn, mode })  // <--- tell backend which set we want
      if (rev !== undefined) qs.set('rev', rev)
      const r = await fetch(`/api/part_images?${qs.toString()}`)
      const j = (r.ok ? await r.json() : []) as ApiRow[]
      if (!cancelled) setRows(Array.isArray(j) ? j : [])
    })()
    return ()=>{cancelled=true}
  }, [pn, rev, mode])

  const list = rows.length
    ? (typeof limit === 'number' ? rows.slice(0, Math.max(0, limit)) : rows)
    : [{ urls: [] }]
  const wrapStyle = fit
    ? { display:'block', width:'100%', height:'100%' }
    : { display:'flex', gap:12, flexWrap:'wrap', marginBottom:16 }
  return (
    <div style={wrapStyle as any}>
      {list.map((row, i) => <FallbackImg key={i} urls={row.urls} fit={fit} />)}
    </div>
  )
}

function FallbackImg({ urls, fit }:{ urls:string[]; fit?: boolean }) {
  const [idx, setIdx] = useState(0)
  const fallback = "/static/images/logo.png"
  const src = urls.length && idx < urls.length ? urls[idx] : fallback
  const baseStyle = fit
    ? { height:'100%', width:'100%', objectFit:'contain', display:'block', background:'white' }
    : { maxHeight:160, maxWidth:240, objectFit:'contain', border:'1px solid rgba(0,0,0,.08)', borderRadius:8, padding:6, background:'white' }
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

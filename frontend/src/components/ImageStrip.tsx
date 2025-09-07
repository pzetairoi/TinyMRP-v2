// frontend/src/components/ImageStrip.tsx
import { useEffect, useState } from "react"
type ApiRow = { urls: string[] }

export default function ImageStrip({ pn, rev = '', mode = 'preview' }:{ pn:string; rev?: string; mode?: 'preview'|'drawing' }) {
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

  if (!rows.length) return null
  return (
    <div style={{display:'flex',gap:12,flexWrap:'wrap',marginBottom:16}}>
      {rows.map((row, i) => <FallbackImg key={i} urls={row.urls} />)}
    </div>
  )
}

function FallbackImg({ urls }:{ urls:string[] }) {
  const [idx, setIdx] = useState(0)
  return (
    <img
      src={urls[idx]}
      onError={()=> idx < urls.length-1 && setIdx(idx+1)}
      style={{ maxHeight:160, maxWidth:240, objectFit:'contain', border:'1px solid rgba(0,0,0,.08)', borderRadius:8, padding:6, background:'white' }}
      alt=""
    />
  )
}

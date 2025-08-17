import { useEffect, useState } from "react"

type Img = { urls: string[]; best: string; revision: string }

function ImgWithFallback({ urls, alt }: { urls: string[]; alt: string }) {
  const [idx, setIdx] = useState(0)
  if (!urls.length) return null
  const src = urls[idx]
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      style={{width:"100%", height: 100, objectFit:"cover", borderRadius: 8, border:"1px solid rgba(0,0,0,.1)"}}
      onError={() => { if (idx < urls.length - 1) setIdx(idx + 1) }}
    />
  )
}

export default function ImageStrip({ pn, rev }: { pn: string; rev?: string }) {
  const [imgs, setImgs] = useState<Img[]>([])
  useEffect(() => {
    (async () => {
      const qs = new URLSearchParams({ pn, ...(rev ? { rev } : {}) }).toString()
      const r = await fetch(`/api/part_images?${qs}`)
      const j = await r.json()
      setImgs(j || [])
    })()
  }, [pn, rev])

  if (!imgs.length) return null
  return (
    <div className="mb-3">
      <div className="mb-1 small text-muted">Imágenes ({imgs[0]?.revision || ""})</div>
      <div style={{display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(120px,1fr))", gap: "8px"}}>
        {imgs.map((it, i) => (
          <a key={i} href={it.best} target="_blank" rel="noreferrer">
            <ImgWithFallback urls={it.urls} alt={`${pn} ${it.revision}`} />
          </a>
        ))}
      </div>
    </div>
  )
}

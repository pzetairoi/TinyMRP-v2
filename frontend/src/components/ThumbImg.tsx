import { useState } from "react"

export default function ThumbImg({
  urls = [],
  maxH = 40,
  maxW = 64,
  alt = "",
}: { urls?: string[]; maxH?: number; maxW?: number; alt?: string }) {
  const [i, setI] = useState(0)
  const src = urls[i]
  const onErr = () => { if (i < urls.length - 1) setI(i + 1) }
  const style = {
    maxHeight: maxH,
    maxWidth: maxW,
    objectFit: "contain" as const,
    border: "1px solid rgba(0,0,0,.08)",
    borderRadius: 8,
    padding: 4,
    background: "white",
  }
  if (!src) return <div style={{ width: maxW, height: maxH, background: "#f2f2f2", borderRadius: 8 }} />
  return <img src={src} onError={onErr} alt={alt} style={style} />
}

import { useState } from "react"

export default function ThumbImg({
  urls = [],
  maxH = 40,
  maxW = 64,
  alt = "",
}: { urls?: string[]; maxH?: number; maxW?: number; alt?: string }) {
  const [i, setI] = useState(0)
  const fallback = "/branding/logo"
  const src = urls.length && i < urls.length ? urls[i] : fallback
  const onErr = () => {
    if (urls.length && i < urls.length - 1) {
      setI(i + 1)
    } else if (src !== fallback) {
      setI(urls.length)
    }
  }
  const style = {
    maxHeight: maxH,
    maxWidth: maxW,
    objectFit: "contain" as const,
    border: "1px solid rgba(0,0,0,.08)",
    borderRadius: 8,
    padding: 4,
    background: "white",
  }
  return <img src={src} onError={onErr} alt={alt} style={style} />
}

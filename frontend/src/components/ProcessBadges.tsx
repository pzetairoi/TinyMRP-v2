// frontend/src/components/ProcessBadges.tsx
export default function ProcessBadges({ processes }: { processes?: string[] }) {
  const P: Record<string, { color: string; icon: string; label: string }> = {
    folding: { color: "rgb(0,102,0)", icon: "/static/images/folding.svg", label: "folding" },
    lasercut: { color: "rgb(0,176,80)", icon: "/static/images/lasercut.svg", label: "lasercut" },
    welding: { color: "rgb(255,192,0)", icon: "/static/images/welding.svg", label: "welding" },
  }
  const list = (processes || []).map((p) => String(p || "").toLowerCase()).filter(Boolean)

  if (!list.length) return <span className="text-muted">n/a</span>

  return (
    <div className="d-flex flex-wrap gap-2">
      {list.map((p, i) => {
        const meta = P[p] || { color: "rgba(0,0,0,.1)", icon: "", label: p }
        return (
          <span
            key={`${p}-${i}`}
            className="badge d-inline-flex align-items-center gap-1"
            style={{ backgroundColor: meta.color }}
            title={meta.label}
          >
            {meta.icon ? <img src={meta.icon} alt="" style={{ width: 16, height: 16 }} /> : null}
            <span style={{ color: "#000", fontWeight: 600 }}>{meta.label}</span>
          </span>
        )
      })}
    </div>
  )
}

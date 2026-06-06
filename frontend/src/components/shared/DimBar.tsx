interface DimBarProps {
  label: string
  value: number
  max: number
  color?: string
}

export function DimBar({ label, value, max, color = "var(--primary)" }: DimBarProps) {
  const pct = Math.max(0, Math.min(1, value / max)) * 100

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontSize: 12.5, color: "var(--fg-2, var(--muted-foreground))" }}>{label}</span>
        <span style={{ fontFamily: "var(--font-geist-mono)", fontSize: 12, color: "var(--muted-foreground)" }}>
          <b style={{ color: "var(--foreground)" }}>{value}</b> / {max}
        </span>
      </div>
      <div style={{ height: 7, borderRadius: 99, background: "var(--track)", overflow: "hidden" }}>
        <div style={{
          width: `${pct}%`, height: "100%", borderRadius: 99,
          background: color,
          boxShadow: `0 0 8px color-mix(in oklab, ${color} 50%, transparent)`,
          transition: "width .4s ease",
        }} />
      </div>
    </div>
  )
}

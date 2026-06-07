interface RadialDimProps {
  label: string
  value: number
  max: number
  color: string
  size?: number
}

export function RadialDim({ label, value, max, color, size = 92 }: RadialDimProps) {
  const r = (size - 9) / 2
  const C = 2 * Math.PI * r
  const pct = value / max

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
      <div style={{ position: "relative", width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--track)" strokeWidth={9} />
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none" stroke={color} strokeWidth={9} strokeLinecap="round"
            strokeDasharray={`${C * pct} ${C}`}
            style={{ filter: `drop-shadow(0 0 5px color-mix(in oklab, ${color} 55%, transparent))` }}
          />
        </svg>
        <div style={{
          position: "absolute", inset: 0,
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        }}>
          <span style={{ fontFamily: "var(--font-geist-mono)", fontSize: 19, fontWeight: 700 }}>{value}</span>
          <span style={{ fontSize: 9.5, color: "var(--muted-foreground)" }}>/ {max}</span>
        </div>
      </div>
      <span style={{ fontSize: 11.5, color: "var(--muted-foreground)", textAlign: "center", maxWidth: 110 }}>
        {label}
      </span>
    </div>
  )
}

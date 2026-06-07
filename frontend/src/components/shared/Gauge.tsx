import type { MigrationDecision } from "@/lib/types"

const BAND_COLORS: Record<MigrationDecision, string> = {
  QUICK_WIN:      "var(--c-green)",
  STRATEGIC:      "var(--c-blue)",
  HOLD:           "var(--c-amber)",
  DO_NOT_MIGRATE: "var(--c-red)",
}

interface GaugeProps {
  value: number
  max?: number
  size?: number
  band?: MigrationDecision
  label?: string
  thick?: number
}

export function Gauge({ value, max = 100, size = 156, band, label = "Migration score", thick = 11 }: GaugeProps) {
  const r = (size - thick) / 2
  const C = 2 * Math.PI * r
  const pct = Math.max(0, Math.min(1, value / max))
  const color = band ? BAND_COLORS[band] : "var(--primary)"
  const arc = C * 0.75   // 270° arc
  const gap = C - arc

  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(135deg)" }}>
        {/* Track */}
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke="var(--track)" strokeWidth={thick}
          strokeLinecap="round"
          strokeDasharray={`${arc} ${gap}`}
        />
        {/* Value */}
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke={color} strokeWidth={thick}
          strokeLinecap="round"
          strokeDasharray={`${arc * pct} ${C - arc * pct}`}
          style={{
            filter: `drop-shadow(0 0 6px color-mix(in oklab, ${color} 55%, transparent))`,
            transition: "stroke-dasharray .6s cubic-bezier(.4,1,.4,1)",
          }}
        />
      </svg>
      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      }}>
        <div style={{
          fontFamily: "var(--font-geist-mono)", fontSize: size * 0.31,
          fontWeight: 700, lineHeight: 1, color: "var(--foreground)",
        }}>{value}</div>
        <div style={{ fontSize: 10.5, color: "var(--muted-foreground)", marginTop: 4, letterSpacing: "0.3px" }}>
          / {max}
        </div>
        <div style={{
          fontSize: 10, color: "var(--muted-foreground)", marginTop: 7,
          textTransform: "uppercase", letterSpacing: "0.6px",
        }}>{label}</div>
      </div>
    </div>
  )
}

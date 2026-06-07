import type { MigrationDecision } from "@/lib/types"

export const BAND_META: Record<MigrationDecision, { label: string; short: string; color: string }> = {
  QUICK_WIN:      { label: "Quick Win",      short: "QW",  color: "var(--c-green)" },
  STRATEGIC:      { label: "Strategic",      short: "ST",  color: "var(--c-blue)"  },
  HOLD:           { label: "Hold",           short: "HD",  color: "var(--c-amber)" },
  DO_NOT_MIGRATE: { label: "Do Not Migrate", short: "DNM", color: "var(--c-red)"   },
}

interface PriorityBadgeProps {
  band: MigrationDecision
  solid?: boolean
  style?: React.CSSProperties
}

export function PriorityBadge({ band, solid, style }: PriorityBadgeProps) {
  const meta = BAND_META[band]
  if (!meta) return null
  const { color, label } = meta
  return (
    <span style={{
      display: "inline-flex", alignItems: "center",
      fontSize: 11, fontWeight: 600, lineHeight: 1, letterSpacing: "0.1px",
      padding: "4px 8px", borderRadius: 6,
      color: solid ? "#0b0b12" : color,
      background: solid ? color : `color-mix(in oklab, ${color} 14%, transparent)`,
      border: `1px solid color-mix(in oklab, ${color} ${solid ? 0 : 32}%, transparent)`,
      ...style,
    }}>
      {label}
    </span>
  )
}

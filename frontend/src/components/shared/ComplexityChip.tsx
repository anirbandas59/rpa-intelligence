import type { Band } from "@/lib/types"

const CLS_COLORS: Record<Band, string> = {
  XS: "var(--c-green)",
  S:  "var(--c-blue)",
  M:  "var(--c-yellow)",
  L:  "var(--c-amber)",
  XL: "var(--c-red)",
}

interface ComplexityChipProps {
  cls: Band
  size?: number
}

export function ComplexityChip({ cls, size = 30 }: ComplexityChipProps) {
  const color = CLS_COLORS[cls]
  return (
    <span style={{
      width: size, height: size,
      borderRadius: 8, flexShrink: 0,
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      fontFamily: "var(--font-geist-mono)",
      fontSize: size * 0.42,
      fontWeight: 700,
      color: color,
      background: `color-mix(in oklab, ${color} 16%, transparent)`,
      border: `1px solid color-mix(in oklab, ${color} 38%, transparent)`,
    }}>
      {cls}
    </span>
  )
}

export { CLS_COLORS }

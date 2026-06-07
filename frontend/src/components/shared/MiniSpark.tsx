interface MiniSparkProps {
  values: number[]
  color?: string
  w?: number
  h?: number
}

export function MiniSpark({ values, color = "var(--primary)", w = 64, h = 20 }: MiniSparkProps) {
  const max = Math.max(...values, 1)
  const step = w / values.length
  return (
    <svg width={w} height={h} style={{ display: "block" }}>
      {values.map((v, i) => (
        <rect
          key={i}
          x={i * step + 1}
          y={h - (v / max) * h}
          width={step - 2}
          height={(v / max) * h}
          rx={1}
          fill={color}
          opacity={0.45 + 0.55 * (v / max)}
        />
      ))}
    </svg>
  )
}

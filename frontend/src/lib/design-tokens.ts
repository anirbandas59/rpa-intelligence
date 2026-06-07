/**
 * Design tokens extracted from exploration files (backend/data/samples/web/shell.jsx)
 *
 * Pattern: Use these constants for inline styles when Tailwind classes don't provide
 * the precision needed (sub-pixel fonts, specific gaps). For layouts and responsive
 * design, prefer Tailwind utilities.
 */

// Typography - precise font sizes from explorations
export const typography = {
  // Section labels (uppercase headers)
  sectionLabel: {
    fontSize: 10.5,
    fontWeight: 700,
    letterSpacing: 1.4,
    textTransform: 'uppercase' as const,
  },

  // Body text
  bodyDefault: {
    fontSize: 12.8,
    lineHeight: 1.6,
  },
  bodyMuted: {
    fontSize: 11.5,
  },
  bodySmall: {
    fontSize: 11,
  },

  // Mono (metrics, scores, code)
  mono: {
    fontSize: 11.5,
  },
  monoLarge: {
    fontSize: 20,
    fontWeight: 700,
  },

  // Headers
  h1: {
    fontSize: 26,
    fontWeight: 700,
    letterSpacing: -0.5,
  },
  h2: {
    fontSize: 19,
    fontWeight: 700,
  },
  h3: {
    fontSize: 13.5,
    fontWeight: 600,
  },

  // UI elements
  button: {
    fontSize: 13,
    fontWeight: 600,
  },
  buttonSm: {
    fontSize: 12.5,
    fontWeight: 600,
  },
  buttonLg: {
    fontSize: 14,
    fontWeight: 600,
  },
  pill: {
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: 0.1,
  },
} as const

// Spacing - precise pixel values from explorations
export const spacing = {
  // Card padding
  cardDefault: 18,
  cardCompact: 13,
  cardLarge: 22,

  // Internal gaps
  gapTight: 12,
  gapDefault: 18,
  gapLoose: 22,
  gapXl: 28,

  // Border radius
  cardRadius: 14,
  cardRadiusSmall: 13,
  buttonRadius: 9,
  pillRadius: 6,
  chipRadius: 8,
  inputRadius: 7,

  // Component heights
  buttonDefault: 36,
  buttonSm: 30,
  buttonLg: 42,
} as const

// Layout patterns from explorations
export const layouts = {
  // Common grid templates
  scorecard: '340px 1fr',
  timeline: '1.3fr 1fr',
  portfolio: '2.1fr repeat(4, 1fr) 1fr 1.1fr',
  stageCards: 'repeat(4, 1fr)',
  phaseCards: 'repeat(6, 1fr)',
} as const

// Helper to create grid column styles
export function gridCols(template: string) {
  return {
    display: 'grid',
    gridTemplateColumns: template,
  } as const
}

// Helper to create flex row/column
export function flexRow(gap: number = spacing.gapDefault) {
  return {
    display: 'flex',
    alignItems: 'center',
    gap,
  } as const
}

export function flexCol(gap: number = spacing.gapDefault) {
  return {
    display: 'flex',
    flexDirection: 'column' as const,
    gap,
  } as const
}

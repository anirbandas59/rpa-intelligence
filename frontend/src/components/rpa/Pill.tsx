/**
 * Pill component - Badge/chip for status, tags, and labels
 * Source: backend/data/samples/web/shell.jsx line 71
 *
 * Flexible badge component with color theming and solid/outline variants.
 */

import React from 'react'
import { spacing, typography } from '@/lib/design-tokens'

export interface PillProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Theme color (CSS variable or hex) */
  color?: string
  /** Solid background variant (default: outline with transparent bg) */
  solid?: boolean
  /** Use monospace font */
  mono?: boolean
  /** Children content */
  children?: React.ReactNode
}

export function Pill({
  color = 'var(--muted-fg)',
  solid = false,
  mono = false,
  children,
  style,
  ...props
}: PillProps) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        fontSize: typography.pill.fontSize,
        fontWeight: typography.pill.fontWeight,
        lineHeight: 1,
        letterSpacing: mono ? 0.3 : typography.pill.letterSpacing,
        fontFamily: mono ? 'var(--mono)' : 'inherit',
        padding: '4px 8px',
        borderRadius: spacing.pillRadius,
        color: solid ? '#0b0b12' : color,
        background: solid
          ? color
          : `color-mix(in oklab, ${color} 14%, transparent)`,
        border: `1px solid color-mix(in oklab, ${color} ${solid ? 0 : 32}%, transparent)`,
        ...style,
      }}
      {...props}
    >
      {children}
    </span>
  )
}

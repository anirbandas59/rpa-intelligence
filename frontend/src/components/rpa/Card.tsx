/**
 * Card component - Exploration design system surface container
 * Source: backend/data/samples/web/shell.jsx line 237
 *
 * Replaces shadcn Card for exploration-aligned styling.
 * Uses precise spacing from design tokens + optional hover interaction.
 */

import React from 'react'
import { spacing } from '@/lib/design-tokens'
import { cn } from '@/lib/utils'

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Padding in pixels (default: 18 from exploration) */
  pad?: number
  /** Enable hover interaction (lift + border highlight) */
  hover?: boolean
  /** Children content */
  children?: React.ReactNode
}

export function Card({
  pad = spacing.cardDefault,
  hover = false,
  children,
  className,
  style,
  ...props
}: CardProps) {
  return (
    <div
      className={cn(hover && 'rpa-card-hover', className)}
      style={{
        borderRadius: spacing.cardRadius,
        border: '1px solid var(--border)',
        background: 'var(--surface)',
        padding: pad,
        ...style,
      }}
      {...props}
    >
      {children}
    </div>
  )
}

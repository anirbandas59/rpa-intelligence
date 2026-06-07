/**
 * SectionLabel component - Uppercase section headers
 * Source: backend/data/samples/web/shell.jsx line 231
 *
 * Consistent header styling for card sections and UI groupings.
 * Fixed typography from exploration design system.
 */

import React from 'react'
import { typography } from '@/lib/design-tokens'

export interface SectionLabelProps
  extends React.HTMLAttributes<HTMLDivElement> {
  /** Children content */
  children?: React.ReactNode
}

export function SectionLabel({
  children,
  style,
  ...props
}: SectionLabelProps) {
  return (
    <div
      style={{
        fontSize: typography.sectionLabel.fontSize,
        fontWeight: typography.sectionLabel.fontWeight,
        letterSpacing: typography.sectionLabel.letterSpacing,
        textTransform: typography.sectionLabel.textTransform,
        color: 'var(--muted-foreground)',
        ...style,
      }}
      {...props}
    >
      {children}
    </div>
  )
}

/**
 * FieldRow component - Input field display with source badge
 * Source: backend/data/samples/web/stage1.jsx line 15
 *
 * Shows label/value pairs with optional source indicator and mono font.
 * Used in Stage 1 inputs card and similar data displays.
 */

import React from 'react'
import { InputSourceBadge } from '@/components/shared/InputSourceBadge'
import type { InputSource } from '@/lib/types'

export interface FieldRowProps {
  /** Field label */
  label: string
  /** Field value */
  value: string | number | React.ReactNode
  /** Optional source indicator */
  source?: InputSource
  /** Use monospace font for value */
  mono?: boolean
}

export function FieldRow({ label, value, source, mono = false }: FieldRowProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '9px 0',
        borderBottom: '1px solid var(--border)',
      }}
    >
      <span style={{ fontSize: 12.5, color: 'var(--muted-fg)' }}>{label}</span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span
          style={{
            fontSize: 12.5,
            fontWeight: 500,
            fontFamily: mono ? 'var(--mono)' : 'inherit',
          }}
        >
          {value}
        </span>
        {source && <InputSourceBadge source={source} />}
      </span>
    </div>
  )
}

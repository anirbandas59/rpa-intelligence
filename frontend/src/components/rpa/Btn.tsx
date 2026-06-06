/**
 * Btn component - Exploration design system button
 * Source: backend/data/samples/web/shell.jsx line 203
 *
 * Replaces shadcn Button with exploration styling and variants.
 * Supports icon placement, size variants, and hover interactions.
 */

'use client'

import React from 'react'
import { spacing, typography } from '@/lib/design-tokens'
import { Icon, IconProps } from './Icon'

type ButtonVariant = 'default' | 'ghost' | 'outline' | 'subtle'
type ButtonSize = 'sm' | 'md' | 'lg'

const VARIANT_STYLES: Record<
  ButtonVariant,
  { bg: string; fg: string; bd: string; glow?: boolean }
> = {
  default: {
    bg: 'var(--primary)',
    fg: '#0a0a12',
    bd: 'transparent',
    glow: true,
  },
  ghost: { bg: 'transparent', fg: 'var(--fg-2)', bd: 'transparent' },
  outline: { bg: 'transparent', fg: 'var(--fg)', bd: 'var(--border)' },
  subtle: { bg: 'var(--surface-2)', fg: 'var(--fg)', bd: 'var(--border)' },
}

const SIZE_STYLES: Record<
  ButtonSize,
  { h: number; px: number; fs: number }
> = {
  sm: { h: spacing.buttonSm, px: 11, fs: typography.buttonSm.fontSize },
  md: { h: spacing.buttonDefault, px: 14, fs: typography.button.fontSize },
  lg: { h: spacing.buttonLg, px: 18, fs: typography.buttonLg.fontSize },
}

export interface BtnProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Button variant style */
  variant?: ButtonVariant
  /** Button size */
  size?: ButtonSize
  /** Icon name to display on the left */
  icon?: IconProps['name']
  /** Icon name to display on the right */
  iconR?: IconProps['name']
  /** Children content */
  children?: React.ReactNode
}

export function Btn({
  variant = 'default',
  size = 'md',
  icon,
  iconR,
  children,
  disabled,
  style,
  ...props
}: BtnProps) {
  const v = VARIANT_STYLES[variant]
  const sz = SIZE_STYLES[size]

  return (
    <button
      disabled={disabled}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 7,
        height: sz.h,
        padding: `0 ${sz.px}px`,
        fontSize: sz.fs,
        fontWeight: typography.button.fontWeight,
        fontFamily: 'inherit',
        borderRadius: spacing.buttonRadius,
        cursor: disabled ? 'not-allowed' : 'pointer',
        color: v.fg,
        background: v.bg,
        border: `1px solid ${v.bd}`,
        opacity: disabled ? 0.5 : 1,
        whiteSpace: 'nowrap',
        boxShadow: v.glow
          ? '0 0 0 1px color-mix(in oklab, var(--primary) 40%, transparent), 0 6px 20px color-mix(in oklab, var(--primary) 28%, transparent)'
          : 'none',
        transition: 'filter 0.15s, background 0.15s',
        ...style,
      }}
      onMouseEnter={(e) => {
        if (!disabled) e.currentTarget.style.filter = 'brightness(1.1)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.filter = 'none'
      }}
      {...props}
    >
      {icon && <Icon name={icon} size={sz.fs + 2} />}
      {children}
      {iconR && <Icon name={iconR} size={sz.fs + 2} />}
    </button>
  )
}

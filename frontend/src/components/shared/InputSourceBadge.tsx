/**
 * InputSourceBadge - displays the source of an input field with icon
 * Shows ai_extracted, manual, corrected, from_sN, or imported
 */

import { Pill } from "@/components/rpa"
import { Icon, type IconName } from "@/components/shared/icons"
import type { InputSource } from "@/lib/types"

interface InputSourceBadgeProps {
  source: InputSource
  className?: string
}

const SOURCE_CONFIG: Record<
  InputSource,
  { icon: IconName; label: string; color: string }
> = {
  ai_extracted: {
    icon: "bot",
    label: "AI",
    color: "var(--primary)",
  },
  manual: {
    icon: "edit",
    label: "Manual",
    color: "var(--fg)",
  },
  corrected: {
    icon: "check",
    label: "Corrected",
    color: "var(--c-green)",
  },
  from_s1: {
    icon: "link",
    label: "From S1",
    color: "var(--c-teal)",
  },
  from_s2: {
    icon: "link",
    label: "From S2",
    color: "var(--c-teal)",
  },
  from_s3: {
    icon: "link",
    label: "From S3",
    color: "var(--c-teal)",
  },
  imported: {
    icon: "upload",
    label: "Imported",
    color: "var(--c-blue)",
  },
}

export function InputSourceBadge({ source, className }: InputSourceBadgeProps) {
  const config = SOURCE_CONFIG[source] || {
    icon: "edit" as IconName,
    label: source,
    color: "var(--muted-fg)",
  }

  return (
    <Pill color={config.color} mono style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
      <Icon name={config.icon} size={10} />
      {config.label}
    </Pill>
  )
}

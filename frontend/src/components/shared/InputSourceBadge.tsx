/**
 * InputSourceBadge - displays the source of an input field
 * Shows ai_extracted, manual, corrected, from_sN, or imported
 */

import { Badge } from "@/components/ui/badge"
import type { InputSource } from "@/lib/types"

interface InputSourceBadgeProps {
  source: InputSource
  className?: string
}

const SOURCE_CONFIG: Record<
  InputSource,
  { label: string; variant: "default" | "secondary" | "outline" | "destructive" }
> = {
  ai_extracted: {
    label: "AI",
    variant: "default",
  },
  manual: {
    label: "Manual",
    variant: "secondary",
  },
  corrected: {
    label: "Corrected",
    variant: "outline",
  },
  from_s1: {
    label: "From S1",
    variant: "outline",
  },
  from_s2: {
    label: "From S2",
    variant: "outline",
  },
  from_s3: {
    label: "From S3",
    variant: "outline",
  },
  imported: {
    label: "Imported",
    variant: "secondary",
  },
}

export function InputSourceBadge({ source, className }: InputSourceBadgeProps) {
  const config = SOURCE_CONFIG[source] || { label: source, variant: "default" as const }

  return (
    <Badge variant={config.variant} className={className}>
      {config.label}
    </Badge>
  )
}

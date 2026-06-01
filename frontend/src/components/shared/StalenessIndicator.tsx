/**
 * StalenessIndicator - shows when inputs have changed and a re-run is needed
 * Displays an amber pill with optional banner
 */

import { AlertTriangle } from "lucide-react"

interface StalenessIndicatorProps {
  isStale: boolean
  stageName?: string
  className?: string
  inline?: boolean
}

export function StalenessIndicator({
  isStale,
  stageName = "stage",
  className = "",
  inline = false,
}: StalenessIndicatorProps) {
  if (!isStale) return null

  if (inline) {
    return (
      <div
        className={`inline-flex items-center gap-1.5 rounded-full bg-amber-100 dark:bg-amber-900/30 px-3 py-1 text-xs font-medium text-amber-800 dark:text-amber-300 ${className}`}
      >
        <AlertTriangle className="h-3 w-3" />
        <span>Inputs changed — re-run to update</span>
      </div>
    )
  }

  return (
    <div
      className={`border border-amber-500/30 bg-amber-500/10 text-amber-400 rounded-lg p-3 flex items-center gap-2 ${className}`}
    >
      <AlertTriangle className="h-4 w-4 shrink-0" />
      <span className="text-sm">
        Inputs for {stageName} have changed. Re-run the {stageName} to see updated results.
      </span>
    </div>
  )
}

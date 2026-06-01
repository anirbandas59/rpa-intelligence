"use client"

/**
 * AutonomousRunButton - split button for manual or orchestrator-driven runs
 * Shows AgentActivityFeed inline when orchestrator is active
 */

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { AgentActivityFeed } from "./AgentActivityFeed"
import { Play, Bot, ChevronDown } from "lucide-react"
import { apiPost } from "@/lib/api"
import { cn } from "@/lib/utils"

interface AutonomousRunButtonProps {
  useCaseId: string
  onManualRun?: () => void
  onOrchestratorStarted?: (sessionId: string) => void
  isRunning?: boolean
}

export function AutonomousRunButton({
  useCaseId,
  onManualRun,
  onOrchestratorStarted,
  isRunning = false,
}: AutonomousRunButtonProps) {
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleManualRun = () => {
    setDropdownOpen(false)
    onManualRun?.()
  }

  const handleOrchestratorRun = async () => {
    setDropdownOpen(false)
    setError(null)
    try {
      const result = await apiPost<{ session_id: string }>(
        `/api/v1/use-cases/${useCaseId}/orchestrate`,
        {}
      )
      setSessionId(result.session_id)
      onOrchestratorStarted?.(result.session_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start orchestrator")
    }
  }

  return (
    <div className="space-y-3">
      <div className="relative flex items-stretch">
        {/* Primary run button */}
        <Button
          onClick={handleManualRun}
          disabled={isRunning}
          className="rounded-r-none border-r border-primary-foreground/20"
        >
          <Play className="mr-2 h-4 w-4" />
          Run
        </Button>

        {/* Dropdown toggle */}
        <Button
          variant="default"
          size="icon"
          disabled={isRunning}
          className="rounded-l-none px-2 h-auto"
          onClick={() => setDropdownOpen((o) => !o)}
        >
          <ChevronDown className={cn("h-4 w-4 transition-transform", dropdownOpen && "rotate-180")} />
        </Button>

        {/* Dropdown menu */}
        {dropdownOpen && (
          <>
            {/* Backdrop */}
            <div
              className="fixed inset-0 z-10"
              onClick={() => setDropdownOpen(false)}
            />
            <div className="absolute top-full left-0 mt-1 z-20 glass-card rounded-lg border border-border/50 shadow-xl min-w-52 overflow-hidden">
              <button
                className="w-full flex items-center gap-2 px-3 py-2.5 text-sm hover:bg-white/5 transition-colors text-left"
                onClick={handleManualRun}
              >
                <Play className="h-4 w-4 text-primary" />
                <div>
                  <div className="font-medium">Run</div>
                  <div className="text-xs text-muted-foreground">Manual single-stage run</div>
                </div>
              </button>
              <div className="border-t border-border/50" />
              <button
                className="w-full flex items-center gap-2 px-3 py-2.5 text-sm hover:bg-white/5 transition-colors text-left"
                onClick={handleOrchestratorRun}
              >
                <Bot className="h-4 w-4 text-violet-400" />
                <div>
                  <div className="font-medium">Run Autonomously</div>
                  <div className="text-xs text-muted-foreground">AI orchestrator, all stages</div>
                </div>
              </button>
            </div>
          </>
        )}
      </div>

      {error && (
        <div className="text-destructive text-xs">{error}</div>
      )}

      {sessionId && (
        <AgentActivityFeed useCaseId={useCaseId} sessionId={sessionId} />
      )}
    </div>
  )
}

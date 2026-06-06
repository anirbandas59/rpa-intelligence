/**
 * RunHistoryDrawer - slide-in sheet showing all runs for a stage
 * Per-run expand shows inputs_snapshot + result
 */

"use client"

import { useState } from "react"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { History, ChevronDown, ChevronRight } from "lucide-react"
import type { StageRun, StageId } from "@/lib/types"

interface RunHistoryDrawerProps {
  runs: StageRun[]
  stage: StageId
  stageName: string
  trigger?: React.ReactNode
}

export function RunHistoryDrawer({ runs, stage, stageName, trigger }: RunHistoryDrawerProps) {
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null)

  const toggleExpand = (runId: string) => {
    setExpandedRunId(expandedRunId === runId ? null : runId)
  }

  return (
    <Sheet>
      <SheetTrigger
        render={
          (trigger as React.ReactElement | undefined) ?? (
            <Button variant="outline" size="sm">
              <History className="mr-2 h-4 w-4" />
              Run History ({runs.length})
            </Button>
          )
        }
      />
      <SheetContent className="w-full sm:max-w-2xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle>
            {stageName} Run History
            <Badge variant="outline" className="ml-2">
              {stage.toUpperCase()}
            </Badge>
          </SheetTitle>
          <SheetDescription>
            {runs.length} run{runs.length !== 1 ? "s" : ""} recorded
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-3">
          {runs.length === 0 && (
            <p className="text-center text-sm text-muted-foreground py-8">No runs yet</p>
          )}

          {runs.map((run) => (
            <div
              key={run.id}
              className="rounded-lg border bg-card p-4 space-y-3 hover:bg-accent/50 transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm">Run #{run.run_number}</span>
                    <Badge
                      variant={
                        run.status === "complete"
                          ? "default"
                          : run.status === "failed"
                            ? "destructive"
                            : "secondary"
                      }
                    >
                      {run.status}
                    </Badge>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {new Date(run.created_at).toLocaleString()}
                  </div>
                  {run.model_used && (
                    <div className="text-xs text-muted-foreground">Model: {run.model_used}</div>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => toggleExpand(run.id)}
                  className="h-8 w-8 p-0"
                >
                  {expandedRunId === run.id ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </Button>
              </div>

              {expandedRunId === run.id && (
                <div className="space-y-3 pt-3 border-t">
                  {run.error_message && (
                    <div className="rounded bg-destructive/10 p-3 text-sm text-destructive">
                      <strong>Error:</strong> {run.error_message}
                    </div>
                  )}

                  <div>
                    <h4 className="text-sm font-medium mb-2">Inputs Snapshot</h4>
                    <pre className="bg-muted/50 rounded-md p-3 text-xs font-mono overflow-auto max-h-64 text-muted-foreground">
                      {JSON.stringify(run.inputs_snapshot, null, 2)}
                    </pre>
                  </div>

                  {run.status === "complete" && (
                    <div>
                      <h4 className="text-sm font-medium mb-2">Result</h4>
                      <pre className="bg-muted/50 rounded-md p-3 text-xs font-mono overflow-auto max-h-64 text-muted-foreground">
                        {JSON.stringify(run.result, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  )
}

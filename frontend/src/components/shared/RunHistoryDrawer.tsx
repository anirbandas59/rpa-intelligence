/**
 * RunHistoryDrawer - slide-in sheet showing all runs for a stage
 * Per-run expand shows inputs_snapshot + result
 */

"use client";

import { useState, useEffect } from "react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { History, ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import type { StageRun, StageId } from "@/lib/types";
import { apiGet } from "@/lib/api";

interface RunHistoryDrawerProps {
  runs: StageRun[];
  stage: StageId;
  stageName: string;
  useCaseId?: string;
  trigger?: React.ReactNode;
  currentRunId?: string;
  selectedRunId?: string;
  onSelectRun?: (runId: string) => void;
}

export function RunHistoryDrawer({
  runs,
  stage,
  stageName,
  useCaseId,
  trigger,
  currentRunId,
  selectedRunId,
  onSelectRun,
}: RunHistoryDrawerProps) {
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const [loadedRuns, setLoadedRuns] = useState<Record<string, StageRun>>({});
  const [loadingRunId, setLoadingRunId] = useState<string | null>(null);

  const toggleExpand = async (runId: string) => {
    const isCollapsing = expandedRunId === runId;
    setExpandedRunId(isCollapsing ? null : runId);

    // If expanding and we don't have full data yet, fetch it (only if useCaseId is provided)
    if (!isCollapsing && !loadedRuns[runId] && useCaseId) {
      setLoadingRunId(runId);
      try {
        const fullRun = await apiGet<StageRun>(
          `/api/v1/use-cases/${useCaseId}/${stage}/runs/${runId}`,
        );
        setLoadedRuns((prev) => ({ ...prev, [runId]: fullRun }));
      } catch (err) {
        console.error("Failed to load run details:", err);
      } finally {
        setLoadingRunId(null);
      }
    }
  };

  const handleRunClick = (runId: string) => {
    if (onSelectRun) {
      onSelectRun(runId);
    }
  };

  return (
    <Sheet>
      {trigger ? (
        <SheetTrigger render={trigger as React.ReactElement}>
          <History className="mr-2 h-4 w-4" />
          Run History ({runs.length})
        </SheetTrigger>
      ) : (
        <SheetTrigger render={<Button variant="outline" size="sm" />}>
          <History className="mr-2 h-4 w-4" />
          Run History ({runs.length})
        </SheetTrigger>
      )}
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
            <p className="text-center text-sm text-muted-foreground py-8">
              No runs yet
            </p>
          )}

          {runs.map((run) => {
            const isSelected = selectedRunId === run.id;
            const isCurrent = currentRunId === run.id;
            return (
              <div
                key={run.id}
                className="rounded-lg border m-4 p-4 space-y-3 transition-colors cursor-pointer"
                style={{
                  background: isSelected
                    ? "color-mix(in oklab, var(--primary) 8%, var(--card))"
                    : isCurrent
                      ? "color-mix(in oklab, var(--c-green) 6%, var(--card))"
                      : "var(--card)",
                }}
                onClick={() => handleRunClick(run.id)}
              >
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm">
                        Run #{run.run_number}
                      </span>
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
                      {isCurrent && (
                        <Badge
                          variant="outline"
                          style={{
                            color: "var(--c-green)",
                            borderColor: "var(--c-green)",
                          }}
                        >
                          Current
                        </Badge>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {new Date(run.created_at).toLocaleString()}
                    </div>
                    {run.model_used && (
                      <div className="text-xs text-muted-foreground">
                        Model: {run.model_used}
                      </div>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleExpand(run.id);
                    }}
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
                    {loadingRunId === run.id ? (
                      <div className="flex items-center justify-center py-8 text-muted-foreground">
                        <Loader2 className="h-5 w-5 animate-spin mr-2" />
                        <span className="text-sm">Loading run details...</span>
                      </div>
                    ) : (
                      <>
                        {(loadedRuns[run.id]?.error_message ||
                          run.error_message) && (
                          <div className="rounded bg-destructive/10 p-3 text-sm text-destructive">
                            <strong>Error:</strong>{" "}
                            {loadedRuns[run.id]?.error_message ||
                              run.error_message}
                          </div>
                        )}

                        <div>
                          <h4 className="text-sm font-medium mb-2">
                            Inputs Snapshot
                          </h4>
                          <pre className="bg-muted/50 rounded-md p-3 text-xs font-mono overflow-auto max-h-64 text-muted-foreground">
                            {loadedRuns[run.id]?.inputs_snapshot
                              ? JSON.stringify(
                                  loadedRuns[run.id].inputs_snapshot,
                                  null,
                                  2,
                                )
                              : run.inputs_snapshot
                                ? JSON.stringify(run.inputs_snapshot, null, 2)
                                : "No inputs snapshot available"}
                          </pre>
                        </div>

                        {run.status === "complete" && (
                          <div>
                            <h4 className="text-sm font-medium mb-2">Result</h4>
                            <pre className="bg-muted/50 rounded-md p-3 text-xs font-mono overflow-auto max-h-64 text-muted-foreground">
                              {loadedRuns[run.id]?.result
                                ? JSON.stringify(
                                    loadedRuns[run.id].result,
                                    null,
                                    2,
                                  )
                                : run.result
                                  ? JSON.stringify(run.result, null, 2)
                                  : "No result data available"}
                            </pre>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </SheetContent>
    </Sheet>
  );
}

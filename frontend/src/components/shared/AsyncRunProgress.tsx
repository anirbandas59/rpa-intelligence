/**
 * AsyncRunProgress - polls readiness endpoint while status=running
 * Shows progress bar and status text until complete/failed
 */

"use client"

import { useEffect, useState } from "react"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Loader2, CheckCircle2, XCircle } from "lucide-react"
import { toast } from "sonner"
import { apiGet } from "@/lib/api"
import type { ReadinessResponse, ReadinessStatus, StageId, S3ReadinessDetail } from "@/lib/types"

function getStageStatus(readiness: ReadinessResponse, stage: StageId): ReadinessStatus {
  const val = readiness[stage]
  if (stage === "s3") return (val as S3ReadinessDetail)?.phase_calculator ?? "not_ready"
  return val as ReadinessStatus
}

interface AsyncRunProgressProps {
  useCaseId: string
  stage: StageId
  onComplete?: () => void
  onError?: (error: string) => void
}

export function AsyncRunProgress({
  useCaseId,
  stage,
  onComplete,
  onError,
}: AsyncRunProgressProps) {
  const [status, setStatus] = useState<"running" | "complete" | "failed">("running")
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [latestRunId, setLatestRunId] = useState<string | null>(null)

  useEffect(() => {
    let interval: NodeJS.Timeout
    let progressInterval: NodeJS.Timeout
    let pollCount = 0

    // Poll readiness every 2 seconds
    const poll = async () => {
      try {
        const readiness = await apiGet<ReadinessResponse>(
          `/api/v1/use-cases/${useCaseId}/readiness`
        )
        const stageStatus = getStageStatus(readiness, stage)
        pollCount++

        if (stageStatus === "complete") {
          setStatus("complete")
          setProgress(100)
          clearInterval(interval)
          clearInterval(progressInterval)
          toast.success("Run complete")
          onComplete?.()
        } else if (stageStatus === "failed") {
          // Fetch actual error message from the failed run
          try {
            const useCase = await apiGet<any>(`/api/v1/use-cases/${useCaseId}`)
            const runId = useCase[`${stage}_latest_run_id`]
            if (runId) {
              const run = await apiGet<any>(`/api/v1/use-cases/${useCaseId}/${stage}/runs/${runId}`)
              const errorMsg = run.error_message || "Assessment failed during processing"
              setError(errorMsg)
              toast.error(`Run failed: ${errorMsg}`)
              onError?.(errorMsg)
            } else {
              setError("Assessment failed during processing")
              toast.error("Run failed: Assessment failed during processing")
              onError?.("Assessment failed during processing")
            }
          } catch (fetchErr) {
            const msg = "Assessment failed during processing"
            setError(msg)
            toast.error(`Run failed: ${msg}`)
            onError?.(msg)
          }
          setStatus("failed")
          clearInterval(interval)
          clearInterval(progressInterval)
        } else if (stageStatus === "not_ready") {
          // Run lost (no run record found)
          const msg = "Run status lost - please try again"
          setStatus("failed")
          setError(msg)
          clearInterval(interval)
          clearInterval(progressInterval)
          toast.error(`Run failed: ${msg}`)
          onError?.(msg)
        } else if (stageStatus === "stale" || stageStatus === "ready") {
          // Allow transient "ready" status for first few polls (race condition)
          // Only error if stuck in this state for >10 seconds (5 polls)
          if (pollCount > 5) {
            const msg = "Run status changed unexpectedly - may need to refresh"
            setStatus("failed")
            setError(msg)
            clearInterval(interval)
            clearInterval(progressInterval)
            toast.error(`Run failed: ${msg}`)
            onError?.(msg)
          }
          // Otherwise, keep polling - might be race condition during StageRun creation
        }
        // "running" status - keep polling
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to check status"
        setStatus("failed")
        setError(msg)
        clearInterval(interval)
        clearInterval(progressInterval)
        toast.error(`Run failed: ${msg}`)
        onError?.(msg)
      }
    }

    // Start polling
    interval = setInterval(poll, 2000)

    // Simulate progress for UX (actual progress unknown)
    let currentProgress = 0
    progressInterval = setInterval(() => {
      currentProgress = Math.min(currentProgress + 1, 90)
      setProgress(currentProgress)
    }, 1000)

    // Initial poll
    poll()

    return () => {
      clearInterval(interval)
      clearInterval(progressInterval)
    }
  }, [useCaseId, stage, onComplete, onError])

  if (status === "complete") {
    return (
      <Alert className="border-green-500/50 bg-green-50 dark:bg-green-900/20">
        <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
        <AlertTitle className="text-green-800 dark:text-green-200">Run Complete</AlertTitle>
        <AlertDescription className="text-green-700 dark:text-green-300">
          Stage processing finished successfully.
        </AlertDescription>
      </Alert>
    )
  }

  if (status === "failed") {
    return (
      <Alert className="border-red-500/50 bg-red-50 dark:bg-red-900/20">
        <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
        <AlertTitle className="text-red-800 dark:text-red-200">Run Failed</AlertTitle>
        <AlertDescription className="text-red-700 dark:text-red-300">
          {error || "An error occurred during processing."}
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        <span className="text-sm font-medium text-primary">
          Processing... This may take a minute
        </span>
      </div>
      {progress === 0 ? (
        <Skeleton className="h-2 w-full rounded-full" />
      ) : (
        <Progress value={progress} className="h-2" />
      )}
    </div>
  )
}

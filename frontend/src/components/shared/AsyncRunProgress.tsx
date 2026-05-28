/**
 * AsyncRunProgress - polls readiness endpoint while status=running
 * Shows progress bar and status text until complete/failed
 */

"use client"

import { useEffect, useState } from "react"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Loader2, CheckCircle2, XCircle } from "lucide-react"
import { apiGet } from "@/lib/api"
import type { ReadinessResponse, StageId } from "@/lib/types"

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

  useEffect(() => {
    let interval: NodeJS.Timeout
    let progressInterval: NodeJS.Timeout

    // Poll readiness every 2 seconds
    const poll = async () => {
      try {
        const readiness = await apiGet<ReadinessResponse>(
          `/api/v1/use-cases/${useCaseId}/readiness`
        )
        const stageStatus = readiness[stage]

        if (stageStatus === "complete") {
          setStatus("complete")
          setProgress(100)
          clearInterval(interval)
          clearInterval(progressInterval)
          onComplete?.()
        } else if (stageStatus === "stale" || stageStatus === "ready") {
          // Something went wrong - stage should be running
          setStatus("failed")
          setError("Run status changed unexpectedly")
          clearInterval(interval)
          clearInterval(progressInterval)
          onError?.("Run status changed unexpectedly")
        }
      } catch (err) {
        setStatus("failed")
        setError(err instanceof Error ? err.message : "Failed to check status")
        clearInterval(interval)
        clearInterval(progressInterval)
        onError?.(err instanceof Error ? err.message : "Failed to check status")
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
        <Loader2 className="h-4 w-4 animate-spin text-purple-600 dark:text-purple-400" />
        <span className="text-sm font-medium text-purple-700 dark:text-purple-300">
          Processing... This may take a minute
        </span>
      </div>
      <Progress value={progress} className="h-2" />
    </div>
  )
}

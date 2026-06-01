"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { StalenessIndicator } from "@/components/shared/StalenessIndicator"
import { AsyncRunProgress } from "@/components/shared/AsyncRunProgress"
import { RunHistoryDrawer } from "@/components/shared/RunHistoryDrawer"
import { ArrowLeft, Play, Download, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { apiGet, apiPost, apiPatch, isAuthenticated } from "@/lib/api"
import type { UseCase, StageRun, S4Result, SprintPlan, ReadinessResponse, Band } from "@/lib/types"

const SIZE_BADGE_COLORS: Record<Band, string> = {
  XS: "bg-green-500/20 text-green-400 border-green-500/30",
  S: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  M: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  L: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  XL: "bg-red-500/20 text-red-400 border-red-500/30",
}

export default function Stage4Page() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.id as string
  const ucId = params.ucId as string

  const [useCase, setUseCase] = useState<UseCase | null>(null)
  const [sprintCount, setSprintCount] = useState<number>(0)
  const [sprintLength, setSprintLength] = useState<number>(2)
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null)
  const [runs, setRuns] = useState<StageRun[]>([])
  const [latestResult, setLatestResult] = useState<S4Result | null>(null)
  const [loading, setLoading] = useState(true)
  const [runningStage, setRunningStage] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/auth/login")
      return
    }

    const fetchData = async () => {
      try {
        const [ucData, readinessData, runsData] = await Promise.all([
          apiGet<UseCase>(`/api/v1/use-cases/${ucId}`),
          apiGet<ReadinessResponse>(`/api/v1/use-cases/${ucId}/readiness`),
          apiGet<StageRun[]>(`/api/v1/use-cases/${ucId}/s4/runs`),
        ])

        setUseCase(ucData)
        setReadiness(readinessData)
        setRuns(runsData)

        if (ucData.s4_inputs?.sprint_count) setSprintCount(ucData.s4_inputs.sprint_count as number)
        if (ucData.s4_inputs?.sprint_length_weeks) setSprintLength(ucData.s4_inputs.sprint_length_weeks as number)

        if (ucData.s4_latest_run_id && runsData.length > 0) {
          const latestRun = runsData.find((r) => r.id === ucData.s4_latest_run_id)
          if (latestRun?.status === "complete") {
            setLatestResult(latestRun.result as unknown as S4Result)
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load data")
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [ucId, router])

  const handleLoadFromS2 = async () => {
    try {
      await apiPost(`/api/v1/use-cases/${ucId}/s4/load-from-s2`, {})
      toast.success("Loaded process documents from Stage 2")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load from S2")
    }
  }

  const handleLoadFromS3 = async () => {
    try {
      await apiPost(`/api/v1/use-cases/${ucId}/s4/load-from-s3`, {})
      window.location.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load from S3")
    }
  }

  const handleRunStage = async () => {
    setRunningStage(true)
    setError("")

    try {
      await apiPatch(`/api/v1/use-cases/${ucId}/s4/inputs`, {
        sprint_count: sprintCount,
        sprint_length_weeks: sprintLength,
      })
      await apiPost(`/api/v1/use-cases/${ucId}/s4/runs`, {})
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run stage")
      setRunningStage(false)
    }
  }

  const handleRunComplete = () => {
    setRunningStage(false)
    window.location.reload()
  }

  const handleExport = async () => {
    if (!latestResult) return
    toast.success("Downloading...")

    try {
      const runId = useCase?.s4_latest_run_id
      if (!runId) return

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/use-cases/${ucId}/s4/runs/${runId}/export`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("token")}`,
          },
        }
      )

      if (!response.ok) throw new Error("Export failed")

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `${useCase?.name || "sprint-tracker"}.xlsx`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed")
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  if (!useCase) {
    return (
      <div className="min-h-screen bg-background p-8">
        <Alert variant="destructive">
          <AlertDescription>Use case not found</AlertDescription>
        </Alert>
      </div>
    )
  }

  const isStale = readiness?.s4 === "stale"
  const isRunning = readiness?.s4 === "running" || runningStage
  const canRun = sprintCount > 0

  // Group features by sprint
  const sprintGroups = latestResult?.sprint_plan.reduce<Record<number, SprintPlan[]>>(
    (acc, sp) => {
      if (!acc[sp.sprint_number]) acc[sp.sprint_number] = []
      acc[sp.sprint_number].push(sp)
      return acc
    },
    {}
  ) || {}

  const sprintNumbers = Object.keys(sprintGroups)
    .map(Number)
    .sort((a, b) => a - b)

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border/50 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="container flex h-14 items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href={`/projects/${projectId}`}>
              <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground -ml-2">
                <ArrowLeft className="mr-1.5 h-4 w-4" />
                Back
              </Button>
            </Link>
            <div className="h-4 w-px bg-border/50" />
            <div>
              <p className="text-sm font-semibold">{useCase.name}</p>
              <p className="text-xs text-muted-foreground">Stage 4 — Sprint Tracker</p>
            </div>
          </div>
          <RunHistoryDrawer runs={runs} stage="s4" stageName="Stage 4 - Sprint Tracker" />
        </div>
      </header>

      <div className="container max-w-6xl py-8 space-y-6">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {isStale && <StalenessIndicator isStale={true} stageName="Stage 4" />}

        {isRunning && (
          <AsyncRunProgress
            useCaseId={ucId}
            stage="s4"
            onComplete={handleRunComplete}
            onError={(err) => setError(err)}
          />
        )}

        {/* Configuration card */}
        <Card className="glass-card border-border/50">
          <CardHeader>
            <CardTitle>Sprint Configuration</CardTitle>
            <CardDescription>Set sprint parameters and load data from previous stages</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="sprint-count">Number of Sprints</Label>
                <Input
                  id="sprint-count"
                  type="number"
                  min="1"
                  value={sprintCount || ""}
                  onChange={(e) => setSprintCount(parseInt(e.target.value) || 0)}
                  disabled={isRunning}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="sprint-length">Sprint Length (weeks)</Label>
                <Input
                  id="sprint-length"
                  type="number"
                  min="1"
                  value={sprintLength}
                  onChange={(e) => setSprintLength(parseInt(e.target.value) || 2)}
                  disabled={isRunning}
                />
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                onClick={handleRunStage}
                disabled={!canRun || isRunning}
                className={canRun && !isRunning ? "glow-primary" : ""}
              >
                <Play className="mr-2 h-4 w-4" />
                {isRunning ? "Running..." : "Decompose & Assign Sprints"}
              </Button>
              <Button variant="outline" onClick={handleLoadFromS2} disabled={isRunning}>
                Load from S2
              </Button>
              <Button variant="outline" onClick={handleLoadFromS3} disabled={isRunning}>
                Load from S3
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Sprint board */}
        {latestResult && sprintNumbers.length > 0 && (
          <Card className="glass-card border-border/50">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Feature Sprint Board</CardTitle>
                  <CardDescription>
                    {latestResult.features.length} features across {sprintNumbers.length} sprints
                  </CardDescription>
                </div>
                <Button onClick={handleExport} variant="outline" size="sm">
                  <Download className="mr-2 h-4 w-4" />
                  Export to Excel
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {/* Board grid */}
              <div
                className="grid gap-3"
                style={{
                  gridTemplateColumns: `repeat(${sprintNumbers.length}, minmax(0, 1fr))`,
                }}
              >
                {/* Column headers */}
                {sprintNumbers.map((sprintNum) => (
                  <div key={`header-${sprintNum}`} className="text-center">
                    <div className="inline-flex items-center justify-center rounded-lg bg-primary/10 border border-primary/20 px-3 py-1.5 text-xs font-semibold text-primary">
                      Sprint {sprintNum}
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-1">
                      {sprintGroups[sprintNum]?.length || 0} feature{sprintGroups[sprintNum]?.length !== 1 ? "s" : ""}
                    </div>
                  </div>
                ))}

                {/* Feature columns */}
                {sprintNumbers.map((sprintNum) => (
                  <div key={`col-${sprintNum}`} className="space-y-2">
                    {(sprintGroups[sprintNum] || []).map((sp: SprintPlan, idx: number) => (
                      <div
                        key={idx}
                        className="glass-card rounded-lg p-3 border border-border/50 hover:border-primary/30 transition-colors"
                      >
                        <div className="text-sm font-semibold mb-1.5 leading-snug">
                          {sp.feature.name}
                        </div>
                        {sp.feature.description && (
                          <div className="text-xs text-muted-foreground line-clamp-2 mb-2">
                            {sp.feature.description}
                          </div>
                        )}
                        <div className="flex items-center flex-wrap gap-1.5">
                          <span
                            className={`inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-semibold ${SIZE_BADGE_COLORS[sp.feature.size]}`}
                          >
                            {sp.feature.size}
                          </span>
                          {sp.feature.dependencies.length > 0 &&
                            sp.feature.dependencies.map((dep, dIdx) => (
                              <span
                                key={dIdx}
                                className="inline-flex items-center rounded-md bg-muted/50 border border-border/40 px-1.5 py-0.5 text-[10px] text-muted-foreground"
                              >
                                {dep}
                              </span>
                            ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

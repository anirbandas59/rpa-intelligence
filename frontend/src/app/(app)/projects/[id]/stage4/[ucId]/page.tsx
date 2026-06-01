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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { StalenessIndicator } from "@/components/shared/StalenessIndicator"
import { AsyncRunProgress } from "@/components/shared/AsyncRunProgress"
import { RunHistoryDrawer } from "@/components/shared/RunHistoryDrawer"
import { ArrowLeft, Play, Download, Loader2 } from "lucide-react"
import { apiGet, apiPost, apiPatch, isAuthenticated } from "@/lib/api"
import type { UseCase, StageRun, S4Result, Feature, SprintPlan, ReadinessResponse } from "@/lib/types"

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

        // Load inputs
        if (ucData.s4_inputs?.sprint_count) setSprintCount(ucData.s4_inputs.sprint_count as number)
        if (ucData.s4_inputs?.sprint_length_weeks) setSprintLength(ucData.s4_inputs.sprint_length_weeks as number)

        // Load latest result
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
      alert("Loaded process documents from Stage 2")
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
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  if (!useCase) {
    return (
      <div className="min-h-screen bg-muted/50 p-8">
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
  const sprintGroups = latestResult?.sprint_plan.reduce((acc, sp: SprintPlan) => {
    if (!acc[sp.sprint_number]) acc[sp.sprint_number] = []
    acc[sp.sprint_number].push(sp)
    return acc
  }, {} as Record<number, SprintPlan[]>) || {}

  return (
    <div className="min-h-screen bg-muted/50">
      <div className="border-b bg-background">
        <div className="container flex h-16 items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href={`/projects/${projectId}`}>
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
            </Link>
            <div className="h-6 w-px bg-border" />
            <div>
              <h1 className="text-sm font-semibold">{useCase.name}</h1>
              <p className="text-xs text-muted-foreground">Stage 4: Sprint Tracker</p>
            </div>
          </div>
          <RunHistoryDrawer runs={runs} stage="s4" stageName="Stage 4 - Sprint Tracker" />
        </div>
      </div>

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

        <Card>
          <CardHeader>
            <CardTitle>Sprint Configuration</CardTitle>
            <CardDescription>
              Set sprint parameters and load data from previous stages
            </CardDescription>
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

            <div className="flex gap-2">
              <Button onClick={handleRunStage} disabled={!canRun || isRunning}>
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

        {latestResult && (
          <>
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Feature Sprint Plan</CardTitle>
                  <Button onClick={handleExport}>
                    <Download className="mr-2 h-4 w-4" />
                    Export to Excel
                  </Button>
                </div>
                <CardDescription>
                  {latestResult.features.length} features decomposed into {sprintCount} sprints
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  {Object.entries(sprintGroups)
                    .sort(([a], [b]) => parseInt(a) - parseInt(b))
                    .map(([sprintNum, features]) => (
                      <div key={sprintNum} className="space-y-2">
                        <h3 className="font-semibold flex items-center gap-2">
                          <Badge>Sprint {sprintNum}</Badge>
                          <span className="text-sm text-muted-foreground">
                            {features.length} feature{features.length !== 1 ? "s" : ""}
                          </span>
                        </h3>
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Feature</TableHead>
                              <TableHead>Description</TableHead>
                              <TableHead className="w-24">Size</TableHead>
                              <TableHead>Dependencies</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {features.map((sp: SprintPlan, idx: number) => (
                              <TableRow key={idx}>
                                <TableCell className="font-medium">{sp.feature.name}</TableCell>
                                <TableCell className="text-sm text-muted-foreground">
                                  {sp.feature.description}
                                </TableCell>
                                <TableCell>
                                  <Badge variant="outline">{sp.feature.size}</Badge>
                                </TableCell>
                                <TableCell className="text-sm">
                                  {sp.feature.dependencies.length > 0 ? (
                                    sp.feature.dependencies.join(", ")
                                  ) : (
                                    <span className="text-muted-foreground">None</span>
                                  )}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  )
}

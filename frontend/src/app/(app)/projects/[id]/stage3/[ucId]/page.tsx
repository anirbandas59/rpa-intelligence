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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { StalenessIndicator } from "@/components/shared/StalenessIndicator"
import { RunHistoryDrawer } from "@/components/shared/RunHistoryDrawer"
import { ArrowLeft, Play, Download, Plus, Minus, RefreshCw, Loader2 } from "lucide-react"
import { apiGet, apiPost, apiPatch, isAuthenticated } from "@/lib/api"
import type { UseCase, StageRun, Phase, S3Result, ReadinessResponse, ComplexityClass } from "@/lib/types"

// Phase color mapping for Gantt bars
const PHASE_COLORS: Record<string, string> = {
  "Define": "bg-blue-500/60",
  "Design": "bg-indigo-500/60",
  "Build": "bg-primary/70",
  "Build + Unit Testing": "bg-primary/70",
  "SIT": "bg-amber-500/60",
  "UAT": "bg-green-500/60",
  "Deployment": "bg-teal-500/60",
}

function getPhaseColor(phaseName: string): string {
  // Try exact match first
  if (PHASE_COLORS[phaseName]) return PHASE_COLORS[phaseName]
  // Partial match
  for (const [key, color] of Object.entries(PHASE_COLORS)) {
    if (phaseName.toLowerCase().includes(key.toLowerCase())) return color
  }
  return "bg-muted-foreground/40"
}

export default function Stage3Page() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.id as string
  const ucId = params.ucId as string

  const [useCase, setUseCase] = useState<UseCase | null>(null)
  const [effortWeeks, setEffortWeeks] = useState<number>(0)
  const [startDate, setStartDate] = useState<string>("")
  const [complexityClass, setComplexityClass] = useState<ComplexityClass>("M")
  const [phaseDeltas, setPhaseDeltas] = useState<Record<string, number>>({})
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null)
  const [runs, setRuns] = useState<StageRun[]>([])
  const [latestResult, setLatestResult] = useState<S3Result | null>(null)
  const [loading, setLoading] = useState(true)
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
          apiGet<StageRun[]>(`/api/v1/use-cases/${ucId}/s3/runs`),
        ])

        setUseCase(ucData)
        setReadiness(readinessData)
        setRuns(runsData)

        if (ucData.s3_inputs?.effort_weeks) setEffortWeeks(ucData.s3_inputs.effort_weeks as number)
        if (ucData.s3_inputs?.start_date) setStartDate(ucData.s3_inputs.start_date as string)
        if (ucData.s3_inputs?.complexity_class) setComplexityClass(ucData.s3_inputs.complexity_class as ComplexityClass)
        if (ucData.s3_inputs?.phase_deltas) setPhaseDeltas(ucData.s3_inputs.phase_deltas as Record<string, number>)

        if (ucData.s3_latest_run_id && runsData.length > 0) {
          const latestRun = runsData.find((r) => r.id === ucData.s3_latest_run_id)
          if (latestRun?.status === "complete") {
            setLatestResult(latestRun.result as unknown as S3Result)
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
      await apiPost(`/api/v1/use-cases/${ucId}/s3/load-from-s2`, {})
      window.location.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load from S2")
    }
  }

  const handleRunStage = async () => {
    setError("")
    try {
      await apiPatch(`/api/v1/use-cases/${ucId}/s3/inputs`, {
        effort_weeks: effortWeeks,
        start_date: startDate,
        complexity_class: complexityClass,
      })
      await apiPost(`/api/v1/use-cases/${ucId}/s3/runs`, {})
      window.location.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run stage")
    }
  }

  const handlePhaseDelta = async (phaseName: string, delta: number) => {
    const newDeltas = { ...phaseDeltas, [phaseName]: (phaseDeltas[phaseName] || 0) + delta }
    setPhaseDeltas(newDeltas)

    try {
      await apiPatch(`/api/v1/use-cases/${ucId}/s3/phase-delta`, { [phaseName]: newDeltas[phaseName] })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update delta")
    }
  }

  const handleResetDeltas = async () => {
    try {
      await apiPost(`/api/v1/use-cases/${ucId}/s3/reset-deltas`, {})
      setPhaseDeltas({})
      window.location.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reset deltas")
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

  const isStale = readiness?.s3 === "stale"
  const canRun = effortWeeks > 0 && startDate !== ""

  // Total weeks for Gantt proportions
  const totalWeeks = latestResult?.phases.reduce(
    (sum, p) => sum + p.weeks + (phaseDeltas[p.name] || 0),
    0
  ) || 1

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
              <p className="text-xs text-muted-foreground">Stage 3 — Delivery Timeline</p>
            </div>
          </div>
          <RunHistoryDrawer runs={runs} stage="s3" stageName="Stage 3 - Timeline" />
        </div>
      </header>

      <div className="container max-w-5xl py-8 space-y-6">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {isStale && <StalenessIndicator isStale={true} stageName="Stage 3" />}

        {/* Configuration card */}
        <Card className="glass-card border-border/50">
          <CardHeader>
            <CardTitle>Timeline Configuration</CardTitle>
            <CardDescription>Set effort estimate, start date, and complexity class</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="effort">Build Effort (weeks)</Label>
                <Input
                  id="effort"
                  type="number"
                  min="1"
                  value={effortWeeks || ""}
                  onChange={(e) => setEffortWeeks(parseInt(e.target.value) || 0)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="start-date">Start Date</Label>
                <Input
                  id="start-date"
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Complexity Class</Label>
                <Select
                  value={complexityClass}
                  onValueChange={(val) => setComplexityClass(val as ComplexityClass)}
                >
                  <SelectTrigger className="w-full h-10">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(["XS", "S", "M", "L", "XL"] as ComplexityClass[]).map((c) => (
                      <SelectItem key={c} value={c}>{c}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex gap-2">
              <Button onClick={handleRunStage} disabled={!canRun} className={canRun ? "glow-primary" : ""}>
                <Play className="mr-2 h-4 w-4" />
                Calculate Timeline
              </Button>
              <Button variant="outline" onClick={handleLoadFromS2}>
                <Download className="mr-2 h-4 w-4" />
                Load from Stage 2
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Gantt visualization */}
        {latestResult && (
          <>
            <Card className="glass-card border-border/50">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Delivery Phases</CardTitle>
                    <CardDescription>
                      Total duration: <strong>{totalWeeks} weeks</strong>
                    </CardDescription>
                  </div>
                  {Object.keys(phaseDeltas).length > 0 && (
                    <Button variant="outline" size="sm" onClick={handleResetDeltas}>
                      <RefreshCw className="mr-2 h-3.5 w-3.5" />
                      Reset Deltas
                    </Button>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {latestResult.phases.map((phase: Phase, idx: number) => {
                    const delta = phaseDeltas[phase.name] || 0
                    const adjustedWeeks = phase.weeks + delta
                    const barWidth = Math.max(2, (adjustedWeeks / totalWeeks) * 100)
                    const phaseColor = getPhaseColor(phase.name)

                    return (
                      <div key={idx} className="space-y-1.5">
                        {/* Row header */}
                        <div className="flex items-center justify-between gap-4">
                          <span className="text-sm font-semibold w-48 shrink-0">{phase.name}</span>
                          <span className="text-xs text-muted-foreground">
                            {new Date(phase.start_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                            {" – "}
                            {new Date(phase.end_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                          </span>
                          <div className="flex items-center gap-1.5 shrink-0">
                            <Badge
                              variant={delta !== 0 ? "default" : "outline"}
                              className="text-xs min-w-16 justify-center"
                            >
                              {adjustedWeeks}w{delta !== 0 && ` (${delta > 0 ? "+" : ""}${delta})`}
                            </Badge>
                            <div className="flex gap-1">
                              <Button
                                variant="outline"
                                size="sm"
                                className="h-7 w-7 p-0"
                                onClick={() => handlePhaseDelta(phase.name, -1)}
                                disabled={adjustedWeeks <= 1}
                              >
                                <Minus className="h-3 w-3" />
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                className="h-7 w-7 p-0"
                                onClick={() => handlePhaseDelta(phase.name, 1)}
                              >
                                <Plus className="h-3 w-3" />
                              </Button>
                            </div>
                          </div>
                        </div>

                        {/* Gantt bar */}
                        <div className="h-6 w-full bg-muted/20 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-300 ${phaseColor}`}
                            style={{ width: `${barWidth}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </CardContent>
            </Card>

            {latestResult.narrative && (
              <Card className="glass-card border-border/50">
                <CardHeader>
                  <CardTitle>Delivery Narrative</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm leading-relaxed text-muted-foreground">{latestResult.narrative}</p>
                </CardContent>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  )
}

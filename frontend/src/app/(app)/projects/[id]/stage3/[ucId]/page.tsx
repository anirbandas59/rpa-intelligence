"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { StalenessIndicator } from "@/components/shared/StalenessIndicator"
import { RunHistoryDrawer } from "@/components/shared/RunHistoryDrawer"
import { Icon } from "@/components/shared/icons"
import { ArrowLeft, Play, Download, Plus, Minus, RefreshCw, Loader2, Copy } from "lucide-react"
import { toast } from "sonner"
import { apiGet, apiGetRuns, apiPost, apiPatch, isAuthenticated } from "@/lib/api"
import type { UseCase, StageRun, Phase, S3Result, ReadinessResponse, S3ReadinessDetail, ComplexityClass } from "@/lib/types"

const PHASE_CSS: Record<string, string> = {
  "Define":                "var(--c-blue)",
  "Design":                "var(--c-violet)",
  "Build":                 "var(--primary)",
  "Build + Unit Testing":  "var(--primary)",
  "SIT":                   "var(--c-amber)",
  "UAT":                   "var(--c-green)",
  "Deployment":            "var(--c-teal)",
}

function phaseColor(name: string): string {
  if (PHASE_CSS[name]) return PHASE_CSS[name]
  for (const [k, v] of Object.entries(PHASE_CSS)) {
    if (name.toLowerCase().includes(k.toLowerCase())) return v
  }
  return "var(--muted-foreground)"
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
}
function fmtShort(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" })
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
    if (!isAuthenticated()) { router.push("/auth/login"); return }

    const fetchData = async () => {
      try {
        const [ucData, readinessData, runsData] = await Promise.all([
          apiGet<UseCase>(`/api/v1/use-cases/${ucId}`),
          apiGet<ReadinessResponse>(`/api/v1/use-cases/${ucId}/readiness`),
          apiGetRuns<StageRun>(`/api/v1/stage3/${ucId}/s3/runs`),
        ])
        setUseCase(ucData)
        setReadiness(readinessData)
        setRuns(runsData)

        if (ucData.s3_inputs?.effort_weeks)    setEffortWeeks(ucData.s3_inputs.effort_weeks as number)
        if (ucData.s3_inputs?.start_date)      setStartDate(ucData.s3_inputs.start_date as string)
        if (ucData.s3_inputs?.complexity_class) setComplexityClass(ucData.s3_inputs.complexity_class as ComplexityClass)
        if (ucData.s3_inputs?.phase_deltas)    setPhaseDeltas(ucData.s3_inputs.phase_deltas as Record<string, number>)

        if (ucData.s3_latest_run_id) {
          const latestRun = runsData.find((r) => r.id === ucData.s3_latest_run_id)
          if (latestRun?.status === "complete") {
            // List endpoint returns summary only — fetch full result from single-run endpoint
            const fullRun = await apiGet<{ result: S3Result }>(`/api/v1/stage3/${ucId}/s3/runs/${ucData.s3_latest_run_id}`)
            setLatestResult(fullRun.result)
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
      await apiPost(`/api/v1/stage3/${ucId}/s3/load-from-s2`, {})
      window.location.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load from S2")
    }
  }

  const handleRunStage = async () => {
    setError("")
    try {
      await apiPatch(`/api/v1/stage3/${ucId}/s3/inputs`, {
        effort_weeks: effortWeeks, start_date: startDate, complexity_class: complexityClass,
      })
      await apiPost(`/api/v1/stage3/${ucId}/s3/runs`, {})
      window.location.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run stage")
    }
  }

  const handlePhaseDelta = async (phaseName: string, delta: number) => {
    const newDeltas = { ...phaseDeltas, [phaseName]: (phaseDeltas[phaseName] || 0) + delta }
    setPhaseDeltas(newDeltas)
    try {
      await apiPatch(`/api/v1/stage3/${ucId}/s3/phase-delta`, { [phaseName]: newDeltas[phaseName] })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update delta")
    }
  }

  const handleResetDeltas = async () => {
    try {
      await apiPost(`/api/v1/stage3/${ucId}/s3/reset-deltas`, {})
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
        <Alert variant="destructive"><AlertDescription>Use case not found</AlertDescription></Alert>
      </div>
    )
  }

  const s3Status = typeof readiness?.s3 === "object"
    ? (readiness.s3 as S3ReadinessDetail).phase_calculator
    : (readiness?.s3 as string | undefined)
  const isStale = s3Status === "stale"
  const canRun = effortWeeks > 0 && startDate !== ""
  const totalWeeks = latestResult?.phases.reduce(
    (sum, p) => sum + p.weeks + (phaseDeltas[p.name] || 0), 0
  ) || 1

  /* Gantt layout — each column = 1 week */
  const COL_W = (100 / totalWeeks)

  /* Cumulative offsets for Gantt */
  const ganttPhases = latestResult?.phases.map((p, i) => {
    const prevWeeks = (latestResult?.phases ?? [])
      .slice(0, i)
      .reduce((s, pp) => s + pp.weeks + (phaseDeltas[pp.name] || 0), 0)
    const w = p.weeks + (phaseDeltas[p.name] || 0)
    return { ...p, offset: prevWeeks, adjWeeks: w }
  }) ?? []

  /* Stats for hero strip */
  const buildPhase = latestResult?.phases.find((p) =>
    p.name.toLowerCase().includes("build")
  )
  const firstPhase = latestResult?.phases[0]
  const lastPhase  = latestResult?.phases[latestResult.phases.length - 1]

  return (
    <div className="min-h-screen bg-background">
      {/* ── Header ── */}
      <header className="border-b border-border/50 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="container flex h-14 items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href={`/projects/${projectId}`}>
              <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground -ml-2">
                <ArrowLeft className="mr-1.5 h-4 w-4" />Back
              </Button>
            </Link>
            <div className="h-4 w-px bg-border/50" />
            <div>
              <p className="text-sm font-semibold">{useCase.name}</p>
              <p className="text-xs text-muted-foreground">Stage 3 — Delivery Timeline</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {latestResult && (
              <span style={{
                display: "inline-flex", alignItems: "center", gap: 5, height: 30, padding: "0 10px",
                borderRadius: 6, fontSize: 11.5, fontWeight: 600,
                color: "var(--c-green)",
                background: "color-mix(in oklab, var(--c-green) 12%, transparent)",
                border: "1px solid color-mix(in oklab, var(--c-green) 28%, transparent)",
              }}>
                <Icon name="check" size={12} /> Complete · {totalWeeks}w total
              </span>
            )}
            {Object.keys(phaseDeltas).length > 0 && (
              <Button variant="outline" size="sm" onClick={handleResetDeltas}>
                <RefreshCw className="mr-1.5 h-3.5 w-3.5" />Reset
              </Button>
            )}
            <RunHistoryDrawer runs={runs} stage="s3" stageName="Stage 3 - Timeline" />
          </div>
        </div>
      </header>

      <div className="container max-w-5xl py-6 space-y-6">
        {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        {isStale && <StalenessIndicator isStale stageName="Stage 3" />}

        {/* ── Config card ── */}
        <div style={{ borderRadius: 14, border: "1px solid var(--border)", background: "var(--card)", padding: 20 }}>
          <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: "1.4px", textTransform: "uppercase", color: "var(--muted-foreground)", marginBottom: 16 }}>
            Timeline configuration
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 16 }}>
            <div>
              <Label style={{ fontSize: 12, marginBottom: 6, display: "block" }}>Build effort (weeks)</Label>
              <Input
                type="number" min="1"
                value={effortWeeks || ""}
                onChange={(e) => setEffortWeeks(parseInt(e.target.value) || 0)}
              />
            </div>
            <div>
              <Label style={{ fontSize: 12, marginBottom: 6, display: "block" }}>Start date</Label>
              <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div>
              <Label style={{ fontSize: 12, marginBottom: 6, display: "block" }}>Complexity class</Label>
              <Select value={complexityClass} onValueChange={(v) => setComplexityClass(v as ComplexityClass)}>
                <SelectTrigger className="w-full h-10"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(["XS", "S", "M", "L", "XL"] as ComplexityClass[]).map((c) => (
                    <SelectItem key={c} value={c}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Button onClick={handleRunStage} disabled={!canRun}>
              <Play className="mr-2 h-4 w-4" />Calculate Timeline
            </Button>
            <Button variant="outline" onClick={handleLoadFromS2}>
              <Download className="mr-2 h-4 w-4" />Load from Stage 2
            </Button>
          </div>
        </div>

        {latestResult && (
          <>
            {/* ── Hero stats strip ── */}
            {firstPhase && lastPhase && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14 }}>
                {[
                  { label: "Start date",      value: fmtDate(firstPhase.start_date), color: "var(--c-blue)"   },
                  { label: "Build effort",    value: `${buildPhase ? buildPhase.weeks + (phaseDeltas[buildPhase.name] || 0) : "—"} wks`, color: "var(--primary)" },
                  { label: "Total duration",  value: `${totalWeeks} weeks`,           color: "var(--c-teal)"  },
                  { label: "Go-live",         value: fmtDate(lastPhase.end_date),     color: "var(--c-green)" },
                ].map(({ label, value, color }) => (
                  <div key={label} style={{
                    borderRadius: 12, border: "1px solid var(--border)", background: "var(--card)",
                    padding: "14px 16px",
                    borderTop: `3px solid ${color}`,
                  }}>
                    <div style={{ fontSize: 10.5, color: "var(--muted-foreground)", marginBottom: 5 }}>{label}</div>
                    <div style={{ fontFamily: "var(--font-geist-mono)", fontSize: 14, fontWeight: 700, color }}>{value}</div>
                  </div>
                ))}
              </div>
            )}

            {/* ── Gantt chart ── */}
            <div style={{ borderRadius: 14, border: "1px solid var(--border)", background: "var(--card)", padding: 20, overflow: "hidden" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
                <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: "1.4px", textTransform: "uppercase", color: "var(--muted-foreground)" }}>
                  Phase timeline — {totalWeeks} weeks
                </div>
                <span style={{ fontSize: 11, fontFamily: "var(--font-geist-mono)", color: "var(--muted-foreground)" }}>
                  {complexityClass} · pure Python
                </span>
              </div>

              {/* Week axis */}
              <div style={{ display: "flex", marginLeft: 172, marginBottom: 8, position: "relative" }}>
                {Array.from({ length: totalWeeks }, (_, i) => (
                  <div key={i} style={{
                    flex: 1, textAlign: "center",
                    fontSize: 9, color: "var(--muted-foreground)", opacity: 0.6,
                    fontFamily: "var(--font-geist-mono)",
                  }}>
                    {i + 1}
                  </div>
                ))}
              </div>

              {/* Phase rows */}
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {ganttPhases.map((phase, idx) => {
                  const delta = phaseDeltas[phase.name] || 0
                  const color = phaseColor(phase.name)
                  return (
                    <div key={idx} style={{ display: "flex", alignItems: "center", gap: 0 }}>
                      {/* Label */}
                      <div style={{
                        width: 168, flexShrink: 0, paddingRight: 14,
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                        gap: 6,
                      }}>
                        <span style={{ fontSize: 12, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {phase.name}
                        </span>
                        <div style={{ display: "flex", gap: 3, flexShrink: 0 }}>
                          <button
                            onClick={() => handlePhaseDelta(phase.name, -1)}
                            disabled={phase.adjWeeks <= 1}
                            style={{
                              width: 20, height: 20, borderRadius: 5, border: "1px solid var(--border)",
                              background: "var(--muted)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
                            }}
                          >
                            <Minus style={{ width: 10, height: 10 }} />
                          </button>
                          <button
                            onClick={() => handlePhaseDelta(phase.name, 1)}
                            style={{
                              width: 20, height: 20, borderRadius: 5, border: "1px solid var(--border)",
                              background: "var(--muted)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
                            }}
                          >
                            <Plus style={{ width: 10, height: 10 }} />
                          </button>
                        </div>
                      </div>

                      {/* Bar container */}
                      <div style={{ flex: 1, position: "relative", height: 28 }}>
                        {/* Track */}
                        <div style={{
                          position: "absolute", inset: 0,
                          borderRadius: 6, background: "var(--track)",
                        }} />
                        {/* Bar */}
                        <div style={{
                          position: "absolute",
                          left: `${phase.offset * COL_W}%`,
                          width: `${phase.adjWeeks * COL_W}%`,
                          top: 0, bottom: 0,
                          borderRadius: 6,
                          background: `color-mix(in oklab, ${color} 45%, transparent)`,
                          border: `1px solid color-mix(in oklab, ${color} 65%, transparent)`,
                          display: "flex", alignItems: "center", justifyContent: "center",
                          transition: "all 0.25s",
                          overflow: "hidden",
                        }}>
                          {delta !== 0 && (
                            <span style={{
                              position: "absolute", right: 5, top: -1,
                              fontSize: 9, fontWeight: 700, padding: "1px 4px", borderRadius: 4,
                              background: color, color: "#0b0b12",
                            }}>
                              {delta > 0 ? `+${delta}` : delta}w
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Week count */}
                      <div style={{
                        width: 52, textAlign: "right", paddingLeft: 10,
                        fontSize: 11.5, fontFamily: "var(--font-geist-mono)", color: "var(--muted-foreground)",
                      }}>
                        {phase.adjWeeks}w
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* ── Phase cards grid ── */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
              {latestResult.phases.map((phase, idx) => {
                const delta = phaseDeltas[phase.name] || 0
                const color = phaseColor(phase.name)
                const adjWeeks = phase.weeks + delta
                return (
                  <div key={idx} style={{
                    borderRadius: 12, border: "1px solid var(--border)", background: "var(--card)",
                    padding: "14px 16px",
                    borderTop: `3px solid ${color}`,
                  }}>
                    <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 8 }}>{phase.name}</div>
                    <div style={{ fontFamily: "var(--font-geist-mono)", fontSize: 20, fontWeight: 700, color, marginBottom: 4 }}>
                      {adjWeeks}w
                    </div>
                    <div style={{ fontSize: 11, color: "var(--muted-foreground)" }}>
                      {fmtShort(phase.start_date)} → {fmtShort(phase.end_date)}
                    </div>
                    {delta !== 0 && (
                      <span style={{
                        display: "inline-flex", alignItems: "center", marginTop: 8, fontSize: 10, fontWeight: 600,
                        padding: "2px 7px", borderRadius: 5,
                        color: delta > 0 ? "var(--c-amber)" : "var(--c-green)",
                        background: delta > 0
                          ? "color-mix(in oklab, var(--c-amber) 14%, transparent)"
                          : "color-mix(in oklab, var(--c-green) 14%, transparent)",
                      }}>
                        {delta > 0 ? `+${delta}` : delta}w adjusted
                      </span>
                    )}
                  </div>
                )
              })}
            </div>

            {/* ── Narrative card ── */}
            {latestResult.narrative && (
              <div style={{
                borderRadius: 14, padding: 22,
                background: "color-mix(in oklab, var(--c-violet) 9%, var(--card))",
                border: "1px solid color-mix(in oklab, var(--c-violet) 28%, transparent)",
              }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{
                      width: 28, height: 28, borderRadius: 7, display: "flex", alignItems: "center", justifyContent: "center",
                      background: "color-mix(in oklab, var(--c-violet) 22%, transparent)", color: "var(--c-violet)",
                    }}>
                      <Icon name="spark" size={14} />
                    </span>
                    <span style={{ fontSize: 13, fontWeight: 700 }}>Delivery narrative</span>
                    <span style={{
                      padding: "3px 7px", borderRadius: 5, fontSize: 10, fontWeight: 600,
                      color: "var(--c-violet)",
                      background: "color-mix(in oklab, var(--c-violet) 15%, transparent)",
                    }}>Sonnet 4.5 · background</span>
                  </div>
                  <Button
                    variant="ghost" size="sm"
                    onClick={() => {
                      navigator.clipboard.writeText(latestResult.narrative || "")
                      toast.success("Copied")
                    }}
                  >
                    <Copy className="h-3.5 w-3.5 mr-1.5" />Copy
                  </Button>
                </div>
                <p style={{ fontSize: 13, lineHeight: 1.65, color: "var(--muted-foreground)", margin: 0 }}>
                  {latestResult.narrative}
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { StalenessIndicator } from "@/components/shared/StalenessIndicator"
import { RunHistoryDrawer } from "@/components/shared/RunHistoryDrawer"
import { Card, Btn, SectionLabel, Pill } from "@/components/rpa"
import { Icon } from "@/components/shared/icons"
import { ArrowLeft, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { spacing } from "@/lib/design-tokens"
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
          apiGetRuns<StageRun>(`/api/v1/use-cases/${ucId}/s3/runs`),
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
            const fullRun = await apiGet<{ result: S3Result }>(`/api/v1/use-cases/${ucId}/s3/runs/${ucData.s3_latest_run_id}`)
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
        effort_weeks: effortWeeks, start_date: startDate, complexity_class: complexityClass,
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
        <div className="flex h-14 items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <Link href={`/projects/${projectId}`}>
              <Btn variant="ghost" size="sm" style={{ marginLeft: -8 }}>
                <ArrowLeft className="mr-1.5 h-4 w-4" />Back
              </Btn>
            </Link>
            <div className="h-4 w-px bg-border/50" />
            <div>
              <p className="text-sm font-semibold">{useCase.name}</p>
              <p className="text-xs text-muted-foreground">Stage 3 — Delivery Timeline</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {latestResult && (
              <Pill color="var(--c-green)">
                <Icon name="check" size={11} /> Complete · {totalWeeks}w total
              </Pill>
            )}
            {Object.keys(phaseDeltas).length > 0 && (
              <Btn variant="outline" size="sm" onClick={handleResetDeltas} icon="refresh">
                Reset
              </Btn>
            )}
            <RunHistoryDrawer runs={runs} stage="s3" stageName="Stage 3 - Timeline" />
          </div>
        </div>
      </header>

      <div style={{ height: "calc(100vh - 56px)", overflow: "hidden", padding: "24px 28px", display: "flex", flexDirection: "column", gap: spacing.gapDefault }}>
        {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        {isStale && <StalenessIndicator isStale stageName="Stage 3" />}

        {/* ── Config card ── */}
        <Card>
          <SectionLabel style={{ marginBottom: 14 }}>Timeline configuration</SectionLabel>
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
          <div style={{ display: "flex", gap: spacing.gapTight }}>
            <Btn onClick={handleRunStage} disabled={!canRun} icon="play" style={{ flex: 1 }}>
              Calculate Timeline
            </Btn>
            <Btn variant="outline" onClick={handleLoadFromS2} icon="download" style={{ flex: 1 }}>
              Load from Stage 2
            </Btn>
          </div>
        </Card>

        {latestResult && (
          <>
            {/* ── Hero stats strip ── */}
            {firstPhase && lastPhase && (
              <div style={{ display: "flex", gap: 14 }}>
                {([
                  { label: "Start",           value: fmtDate(firstPhase.start_date), icon: "calendar" as const, color: "var(--c-blue)"   },
                  { label: "Build effort",    value: `${buildPhase ? buildPhase.weeks + (phaseDeltas[buildPhase.name] || 0) : "—"} wks`, icon: "clock" as const, color: "var(--primary)" },
                  { label: "Total duration",  value: `${totalWeeks} weeks`,           icon: "target" as const, color: "var(--c-teal)"  },
                  { label: "Go-live",         value: fmtDate(lastPhase.end_date),     icon: "check" as const, color: "var(--c-green)" },
                ] as const).map(({ label, value, icon, color }) => (
                  <Card key={label} pad={15} style={{ flex: 1, display: "flex", alignItems: "center", gap: 12 }}>
                    <span style={{
                      width: 34, height: 34, borderRadius: 9,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      background: "var(--surface-2)",
                      color: label === "Go-live" ? "var(--c-green)" : "var(--primary)",
                    }}>
                      <Icon name={icon} size={17} />
                    </span>
                    <div>
                      <div style={{ fontSize: 10.5, color: "var(--muted-fg)" }}>{label}</div>
                      <div style={{
                        fontSize: 15, fontWeight: 700,
                        fontFamily: label === "Build effort" || label === "Total duration" ? "var(--mono)" : "inherit",
                      }}>
                        {value}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}

            {/* ── Gantt chart ── */}
            <Card style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                <SectionLabel>Delivery Gantt · adjust phases with +/- buttons</SectionLabel>
                <div style={{ display: "flex", gap: 14, fontSize: 11, color: "var(--muted-fg)" }}>
                  <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                    <span style={{ width: 18, height: 8, borderRadius: 2, background: "var(--primary)" }} /> Sprint window
                  </span>
                  <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                    <Icon name="edit" size={11} style={{ color: "var(--c-amber)" }} /> Manual delta
                  </span>
                </div>
              </div>

              {/* Week axis */}
              <div style={{ display: "flex", paddingLeft: 168, marginBottom: 6 }}>
                {Array.from({ length: totalWeeks }, (_, i) => (
                  <div key={i} style={{
                    width: `${COL_W}%`, fontSize: 9.5, color: "var(--muted-fg)",
                    textAlign: "center", fontFamily: "var(--mono)",
                  }}>
                    W{i + 1}
                  </div>
                ))}
              </div>

              {/* Phase rows with gridlines */}
              <div style={{ position: "relative", flex: 1 }}>
                {/* Gridlines */}
                <div style={{
                  position: "absolute", left: 168, right: 0, top: 0, bottom: 0,
                  display: "flex", pointerEvents: "none",
                }}>
                  {Array.from({ length: totalWeeks + 1 }).map((_, i) => (
                    <div key={i} style={{
                      width: `${COL_W}%`,
                      borderLeft: "1px solid color-mix(in oklab, var(--border) 55%, transparent)",
                    }} />
                  ))}
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 9, position: "relative" }}>
                  {ganttPhases.map((phase, idx) => {
                    const delta = phaseDeltas[phase.name] || 0
                    const color = phaseColor(phase.name)
                    const kindLabels: Record<string, string> = {
                      "Define": "Fixed buffer",
                      "Design": "Complexity-adjusted",
                      "Build": "Variable · from S2",
                      "Build + Unit Testing": "Variable · from S2",
                      "SIT": "Fixed buffer",
                      "UAT": "Complexity-adjusted",
                      "Deployment": "Fixed buffer",
                    }
                    return (
                      <div key={idx} style={{ display: "flex", alignItems: "center", height: 40 }}>
                        {/* Label column */}
                        <div style={{ width: 168, paddingRight: 14, flexShrink: 0 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 12.5, fontWeight: 600 }}>
                            <span style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
                            {phase.name}
                          </div>
                          <div style={{ fontSize: 10, color: "var(--muted-fg)", marginLeft: 15 }}>
                            {kindLabels[phase.name] || "Phase"}
                          </div>
                        </div>

                        {/* Gantt track */}
                        <div style={{ flex: 1, position: "relative", height: 26 }}>
                          <div style={{
                            position: "absolute",
                            left: `${phase.offset * COL_W}%`,
                            width: `${phase.adjWeeks * COL_W}%`,
                            height: "100%",
                            borderRadius: 7,
                            background: `linear-gradient(90deg, ${color}, color-mix(in oklab, ${color} 78%, black))`,
                            boxShadow: `0 2px 10px color-mix(in oklab, ${color} 35%, transparent)`,
                            display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 8px",
                            border: delta ? "1.5px dashed color-mix(in oklab, var(--c-amber) 80%, white)" : "none",
                          }}>
                            <button
                              onClick={() => handlePhaseDelta(phase.name, -1)}
                              disabled={phase.adjWeeks <= 1}
                              style={{
                                width: 4, height: "60%", borderRadius: 2,
                                background: "rgba(255,255,255,.5)", cursor: "ew-resize",
                                border: "none", padding: 0,
                              }}
                            />
                            <span style={{ fontSize: 10.5, fontWeight: 700, color: "#0b0b12", fontFamily: "var(--mono)" }}>
                              {phase.adjWeeks}w
                            </span>
                            <button
                              onClick={() => handlePhaseDelta(phase.name, 1)}
                              style={{
                                width: 4, height: "60%", borderRadius: 2,
                                background: "rgba(255,255,255,.5)", cursor: "ew-resize",
                                border: "none", padding: 0,
                              }}
                            />
                          </div>
                          {delta !== 0 && (
                            <div style={{
                              position: "absolute",
                              left: `calc(${(phase.offset + phase.adjWeeks) * COL_W}% - 4px)`,
                              top: -16,
                              fontSize: 9.5, color: "var(--c-amber)", fontWeight: 700,
                              fontFamily: "var(--mono)", whiteSpace: "nowrap",
                              transform: "translateX(-100%)",
                            }}>
                              {delta > 0 ? `+${delta}` : delta}w delta
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </Card>

            {/* ── Phase cards grid ── */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 12 }}>
              {latestResult.phases.map((phase, idx) => {
                const delta = phaseDeltas[phase.name] || 0
                const color = phaseColor(phase.name)
                const adjWeeks = phase.weeks + delta
                return (
                  <Card key={idx} pad={13} hover style={{ borderTop: `2px solid ${color}` }}>
                    <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>{phase.name}</div>
                    <div style={{
                      fontFamily: "var(--mono)", fontSize: 20, fontWeight: 700, color,
                    }}>
                      {adjWeeks}<span style={{ fontSize: 11, color: "var(--muted-fg)" }}>wk</span>
                    </div>
                    <div style={{ fontSize: 10.5, color: "var(--muted-fg)", marginTop: 8 }}>
                      {fmtShort(phase.start_date)} – {fmtShort(phase.end_date)}
                    </div>
                    {delta !== 0 && (
                      <div style={{ marginTop: 6 }}>
                        <Pill color="var(--c-amber)" style={{ fontSize: 9 }}>
                          edited {delta > 0 ? `+${delta}` : delta}w
                        </Pill>
                      </div>
                    )}
                  </Card>
                )
              })}
            </div>

            {/* ── Narrative card ── */}
            {latestResult.narrative && (
              <Card style={{
                display: "flex", flexDirection: "column", gap: 12,
                background: "linear-gradient(160deg, color-mix(in oklab, var(--c-violet) 8%, var(--surface)), var(--surface) 70%)",
              }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                    <span style={{
                      width: 30, height: 30, borderRadius: 8,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      background: "color-mix(in oklab, var(--c-violet) 18%, transparent)",
                      color: "var(--c-violet)",
                    }}>
                      <Icon name="spark" size={16} />
                    </span>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>Client-ready summary</span>
                  </div>
                  <Btn
                    variant="ghost" size="sm"
                    onClick={() => {
                      navigator.clipboard.writeText(latestResult.narrative || "")
                      toast.success("Copied")
                    }}
                    icon="copy"
                  >
                    Copy
                  </Btn>
                </div>
                <p style={{ fontSize: 12.8, lineHeight: 1.65, color: "var(--fg-2)", margin: 0 }}>
                  {latestResult.narrative}
                </p>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  )
}

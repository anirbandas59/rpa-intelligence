"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { StalenessIndicator } from "@/components/shared/StalenessIndicator"
import { AsyncRunProgress } from "@/components/shared/AsyncRunProgress"
import { RunHistoryDrawer } from "@/components/shared/RunHistoryDrawer"
import { CLS_COLORS } from "@/components/shared/ComplexityChip"
import { Card, Btn, SectionLabel, Pill } from "@/components/rpa"
import { Icon } from "@/components/shared/icons"
import { ArrowLeft, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { spacing } from "@/lib/design-tokens"
import { apiGet, apiGetRuns, apiPost, apiPatch, isAuthenticated } from "@/lib/api"
import type { UseCase, StageRun, S4Result, SprintPlan, ReadinessResponse, Band } from "@/lib/types"

// Story points mapping (from exploration stage4.jsx line 6)
const SIZE_POINTS: Record<Band, number> = {
  XS: 1,
  S: 2,
  M: 3,
  L: 5,
  XL: 8,
}

/* FeatureCard */
interface FeatureCardProps {
  sp: SprintPlan
  compact?: boolean
}

function FeatureCard({ sp, compact }: FeatureCardProps) {
  const { feature } = sp
  const color = CLS_COLORS[feature.size] || "var(--primary)"
  return (
    <div className="rpa-card-hover" style={{
      borderRadius: 10, border: "1px solid var(--border)",
      background: "var(--surface-2)",
      padding: compact ? "9px 11px" : "11px 13px",
      borderLeft: `3px solid ${color}`,
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
        <span style={{ fontSize: 12.5, fontWeight: 600, lineHeight: 1.3 }}>{feature.name}</span>
        <span style={{
          flexShrink: 0, fontFamily: "var(--mono)", fontSize: 10, fontWeight: 700,
          color, background: `color-mix(in oklab, ${color} 15%, transparent)`,
          border: `1px solid color-mix(in oklab, ${color} 32%, transparent)`,
          borderRadius: 5, padding: "2px 6px",
        }}>
          {feature.size}
        </span>
      </div>
      {!compact && feature.description && (
        <div style={{ fontSize: 11, color: "var(--muted-fg)", marginTop: 5, lineHeight: 1.4 }}>
          {feature.description}
        </div>
      )}
      {feature.dependencies.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 5, marginTop: 7, fontSize: 10, color: "var(--muted-fg)" }}>
          <Icon name="link" size={10} /> depends on {feature.dependencies[0].split(" ").slice(0, 2).join(" ")}…
        </div>
      )}
    </div>
  )
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
  const [activeTab, setActiveTab] = useState<"board" | "features">("board")

  useEffect(() => {
    if (!isAuthenticated()) { router.push("/auth/login"); return }

    const fetchData = async () => {
      try {
        const [ucData, readinessData, runsData] = await Promise.all([
          apiGet<UseCase>(`/api/v1/use-cases/${ucId}`),
          apiGet<ReadinessResponse>(`/api/v1/use-cases/${ucId}/readiness`),
          apiGetRuns<StageRun>(`/api/v1/stage4/${ucId}/s4/runs`),
        ])
        setUseCase(ucData)
        setReadiness(readinessData)
        setRuns(runsData)

        if (ucData.s4_inputs?.sprint_count)        setSprintCount(ucData.s4_inputs.sprint_count as number)
        if (ucData.s4_inputs?.sprint_length_weeks) setSprintLength(ucData.s4_inputs.sprint_length_weeks as number)

        if (ucData.s4_latest_run_id) {
          const latestRun = runsData.find((r) => r.id === ucData.s4_latest_run_id)
          if (latestRun?.status === "complete") {
            // List endpoint returns summary only — fetch full result from single-run endpoint
            const fullRun = await apiGet<{ result: S4Result }>(`/api/v1/stage4/${ucId}/s4/runs/${ucData.s4_latest_run_id}`)
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
      await apiPost(`/api/v1/stage4/${ucId}/s4/load-from-s2`, {})
      toast.success("Loaded process documents from Stage 2")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load from S2")
    }
  }

  const handleLoadFromS3 = async () => {
    try {
      await apiPost(`/api/v1/stage4/${ucId}/s4/load-from-s3`, {})
      window.location.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load from S3")
    }
  }

  const handleRunStage = async () => {
    setRunningStage(true)
    setError("")
    try {
      await apiPatch(`/api/v1/stage4/${ucId}/s4/inputs`, {
        sprint_count: sprintCount, sprint_length_weeks: sprintLength,
      })
      await apiPost(`/api/v1/stage4/${ucId}/s4/runs`, {})
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
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/stage4/${ucId}/s4/runs/${runId}/export`,
        { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } }
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
      toast.success("Downloading…")
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
        <Alert variant="destructive"><AlertDescription>Use case not found</AlertDescription></Alert>
      </div>
    )
  }

  const isStale = readiness?.s4 === "stale"
  const isRunning = readiness?.s4 === "running" || runningStage
  const canRun = sprintCount > 0

  const sprintGroups = latestResult?.sprint_plan.reduce<Record<number, SprintPlan[]>>(
    (acc, sp) => { if (!acc[sp.sprint_number]) acc[sp.sprint_number] = []; acc[sp.sprint_number].push(sp); return acc },
    {}
  ) || {}
  const sprintNumbers = Object.keys(sprintGroups).map(Number).sort((a, b) => a - b)

  /* Pts per sprint (count features as capacity proxy) */
  const maxFeaturesInSprint = Math.max(...sprintNumbers.map((n) => sprintGroups[n].length), 1)

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
              <p className="text-xs text-muted-foreground">Stage 4 — Sprint Tracker</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {latestResult && (
              <>
                <Pill color="var(--c-green)">
                  <Icon name="check" size={11} /> {latestResult.features.length} features · {sprintNumbers.length} sprints
                </Pill>
                <Btn variant="outline" size="sm" onClick={handleExport} icon="download">
                  Export XLSX
                </Btn>
              </>
            )}
            <RunHistoryDrawer runs={runs} stage="s4" stageName="Stage 4 - Sprint Tracker" />
            <Btn size="sm" onClick={handleRunStage} disabled={!canRun || isRunning} icon="play">
              {isRunning ? "Running…" : "Decompose & Assign"}
            </Btn>
          </div>
        </div>
      </header>

      <div style={{ height: "calc(100vh - 56px)", overflow: "hidden", padding: "24px 28px", display: "flex", flexDirection: "column", gap: spacing.gapDefault }}>
        {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        {isStale && <StalenessIndicator isStale stageName="Stage 4" />}
        {isRunning && (
          <AsyncRunProgress useCaseId={ucId} stage="s4" onComplete={handleRunComplete} onError={(e) => setError(e)} />
        )}

        {/* ── Config card ── */}
        <Card>
          <SectionLabel style={{ marginBottom: 14 }}>Sprint configuration</SectionLabel>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
            <div>
              <Label style={{ fontSize: 12, marginBottom: 6, display: "block" }}>Number of sprints</Label>
              <Input type="number" min="1" value={sprintCount || ""} onChange={(e) => setSprintCount(parseInt(e.target.value) || 0)} disabled={isRunning} />
            </div>
            <div>
              <Label style={{ fontSize: 12, marginBottom: 6, display: "block" }}>Sprint length (weeks)</Label>
              <Input type="number" min="1" value={sprintLength} onChange={(e) => setSprintLength(parseInt(e.target.value) || 2)} disabled={isRunning} />
            </div>
          </div>
          <div style={{ display: "flex", gap: spacing.gapTight }}>
            <Btn onClick={handleRunStage} disabled={!canRun || isRunning} icon="play" style={{ flex: 1 }}>
              {isRunning ? "Running…" : "Decompose & Assign"}
            </Btn>
            <Btn variant="outline" onClick={handleLoadFromS2} disabled={isRunning} icon="link" style={{ flex: 1 }}>
              Load from S2
            </Btn>
            <Btn variant="outline" onClick={handleLoadFromS3} disabled={isRunning} icon="link" style={{ flex: 1 }}>
              Load from S3
            </Btn>
          </div>
        </Card>

        {/* ── Sprint board ── */}
        {latestResult && sprintNumbers.length > 0 && (
          <>
            {/* Header with view toggle */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <h2 style={{ fontSize: 19, fontWeight: 700, margin: 0 }}>
                  {activeTab === "board" ? "Sprint plan" : "Decomposed features"}
                </h2>
                <p style={{ fontSize: 12.5, color: "var(--muted-fg)", margin: "4px 0 0" }}>
                  {activeTab === "board"
                    ? `${latestResult.features.length} features · ${sprintNumbers.length} sprints × ${sprintLength} weeks · bin-packed by size after Sonnet decomposition`
                    : "Sonnet read the S2 documents and split the process into deliverables."}
                </p>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                {/* View toggle */}
                <div style={{ display: "flex", gap: 1, borderRadius: 9, border: "1px solid var(--border)", padding: 3 }}>
                  {(["board", "features"] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      style={{
                        padding: "5px 14px", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer",
                        background: activeTab === tab ? "color-mix(in oklab, var(--primary) 16%, transparent)" : "transparent",
                        color: activeTab === tab ? "var(--primary)" : "var(--muted-fg)",
                        border: "none",
                        fontFamily: "inherit",
                        transition: "all 0.12s",
                      }}
                    >
                      {tab === "board" ? "Sprint board" : "Feature table"}
                    </button>
                  ))}
                </div>
                {activeTab === "board" && (
                  <>
                    <span style={{ fontSize: 12, color: "var(--muted-fg)" }}>Sprint length</span>
                    <Pill color="var(--primary)" style={{ height: 28 }}>{sprintLength} weeks</Pill>
                  </>
                )}
              </div>
            </div>

            {/* Sprint swimlanes */}
            {activeTab === "board" && (
              <div style={{ flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: `repeat(${Math.min(sprintNumbers.length, 4)}, 1fr)`, gap: 14 }}>
                {sprintNumbers.map((sprintNum) => {
                  const items = sprintGroups[sprintNum] || []
                  const fillPct = (items.length / maxFeaturesInSprint) * 100
                  return (
                    <div key={sprintNum} style={{ display: "flex", flexDirection: "column", gap: 11, minHeight: 0 }}>
                      <Card pad={13} style={{ flexShrink: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 9 }}>
                          <span style={{ fontSize: 13, fontWeight: 700 }}>Sprint {sprintNum}</span>
                          <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--muted-fg)" }}>
                            {items.length} features
                          </span>
                        </div>
                        <div style={{ height: 6, borderRadius: 99, background: "var(--track)", overflow: "hidden" }}>
                          <div style={{
                            width: `${fillPct}%`, height: "100%", borderRadius: 99,
                            background: fillPct > 85 ? "var(--c-amber)" : "var(--primary)",
                          }} />
                        </div>
                      </Card>
                      <div style={{
                        flex: 1, display: "flex", flexDirection: "column", gap: 9, padding: 4, borderRadius: 12,
                        background: "color-mix(in oklab, var(--surface) 50%, transparent)",
                        border: "1px dashed var(--border)",
                      }}>
                        {items.map((sp) => (
                          <FeatureCard key={sp.feature.name} sp={sp} />
                        ))}
                        {items.length < 2 && (
                          <div style={{
                            flex: 1, minHeight: 40, borderRadius: 9, border: "1px dashed var(--border)",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            fontSize: 11, color: "var(--muted-fg)",
                          }}>
                            <Icon name="plus" size={13} style={{ marginRight: 5 }} /> capacity free
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {/* Feature table */}
            {activeTab === "features" && (
              <Card pad={0} style={{ flex: 1, minHeight: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}>
                {/* Table header */}
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "2.2fr 0.6fr 0.5fr 0.7fr 0.6fr 0.7fr",
                  padding: "10px 16px",
                  borderBottom: "1px solid var(--border)",
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: 0.5,
                  color: "var(--muted-fg)",
                  textTransform: "uppercase",
                }}>
                  <span>Feature</span>
                  <span style={{ textAlign: "center" }}>Size</span>
                  <span style={{ textAlign: "center" }}>Pts</span>
                  <span style={{ textAlign: "center" }}>Deps</span>
                  <span style={{ textAlign: "center" }}>Status</span>
                  <span style={{ textAlign: "right" }}>Sprint</span>
                </div>

                {/* Table rows */}
                <div style={{ flex: 1, overflow: "auto" }}>
                  {latestResult.sprint_plan.map((sp, idx) => {
                    const points = SIZE_POINTS[sp.feature.size] || 0
                    const color = CLS_COLORS[sp.feature.size] || "var(--primary)"
                    return (
                      <div
                        key={idx}
                        className="rpa-card-hover"
                        style={{
                          display: "grid",
                          gridTemplateColumns: "2.2fr 0.6fr 0.5fr 0.7fr 0.6fr 0.7fr",
                          padding: "12px 16px",
                          alignItems: "center",
                          borderBottom: idx < latestResult.sprint_plan.length - 1 ? "1px solid var(--border)" : "none",
                        }}
                      >
                        {/* Feature name + description */}
                        <div style={{ minWidth: 0, paddingRight: 8 }}>
                          <div style={{ fontSize: 12.5, fontWeight: 600 }}>{sp.feature.name}</div>
                          {sp.feature.description && (
                            <div style={{
                              fontSize: 10.5,
                              color: "var(--muted-fg)",
                              whiteSpace: "nowrap",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                            }}>
                              {sp.feature.description}
                            </div>
                          )}
                        </div>

                        {/* Size chip */}
                        <span style={{ textAlign: "center", display: "flex", justifyContent: "center" }}>
                          <span style={{
                            fontFamily: "var(--mono)",
                            fontSize: 11,
                            fontWeight: 700,
                            color,
                            background: `color-mix(in oklab, ${color} 14%, transparent)`,
                            borderRadius: 5,
                            padding: "2px 7px",
                          }}>
                            {sp.feature.size}
                          </span>
                        </span>

                        {/* Story points */}
                        <span style={{
                          textAlign: "center",
                          fontFamily: "var(--mono)",
                          fontSize: 12,
                          color: "var(--fg-2)",
                        }}>
                          {points}
                        </span>

                        {/* Dependencies */}
                        <span style={{ textAlign: "center", fontSize: 11.5, color: "var(--muted-fg)" }}>
                          {sp.feature.dependencies.length || "—"}
                        </span>

                        {/* Status (placeholder - from tracker export) */}
                        <span style={{ textAlign: "center" }}>
                          <span style={{
                            fontSize: 9.5,
                            fontWeight: 600,
                            padding: "3px 7px",
                            borderRadius: 5,
                            color: "var(--muted-fg)",
                            background: "var(--surface-2)",
                            border: "1px solid var(--border)",
                          }}>
                            Planned
                          </span>
                        </span>

                        {/* Sprint */}
                        <span style={{
                          textAlign: "right",
                          fontFamily: "var(--mono)",
                          fontSize: 12,
                          fontWeight: 700,
                          color: "var(--primary)",
                        }}>
                          S{sp.sprint_number}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </Card>
            )}

            {/* Size legend */}
            <Card style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <SectionLabel>Feature size</SectionLabel>
              <div style={{ display: "flex", gap: 13 }}>
                {(["XS", "S", "M", "L", "XL"] as Band[]).map((b) => (
                  <span key={b} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11.5, color: "var(--fg-2)" }}>
                    <span style={{ width: 9, height: 9, borderRadius: 2, background: CLS_COLORS[b] }} />
                    {b} = {b === "XS" ? "1wk" : b === "S" ? "2–4wk" : b === "M" ? "5wk" : b === "L" ? "6wk" : "8wk"}
                  </span>
                ))}
              </div>
              <span style={{ flex: 1 }} />
              <span style={{ fontSize: 11, color: "var(--muted-fg)", display: "flex", alignItems: "center", gap: 6 }}>
                <Icon name="refresh" size={12} /> Change sprint length → re-run redistributes features · each run versioned
              </span>
            </Card>
          </>
        )}
      </div>
    </div>
  )
}

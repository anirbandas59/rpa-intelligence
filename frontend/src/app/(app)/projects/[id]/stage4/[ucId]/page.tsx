"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { StalenessIndicator } from "@/components/shared/StalenessIndicator"
import { AsyncRunProgress } from "@/components/shared/AsyncRunProgress"
import { RunHistoryDrawer } from "@/components/shared/RunHistoryDrawer"
import { ComplexityChip, CLS_COLORS } from "@/components/shared/ComplexityChip"
import { Icon } from "@/components/shared/icons"
import { ArrowLeft, Play, Download, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { apiGet, apiGetRuns, apiPost, apiPatch, isAuthenticated } from "@/lib/api"
import type { UseCase, StageRun, S4Result, SprintPlan, ReadinessResponse, Band } from "@/lib/types"

/* FeatureCard */
interface FeatureCardProps {
  sp: SprintPlan
  compact?: boolean
}

function FeatureCard({ sp, compact }: FeatureCardProps) {
  const { feature } = sp
  const color = CLS_COLORS[feature.size] || "var(--primary)"
  return (
    <div style={{
      borderRadius: 10, border: "1px solid var(--border)",
      background: "var(--card)",
      padding: compact ? "10px 12px" : "13px 14px",
      borderLeft: `3px solid ${color}`,
      transition: "border-color 0.12s",
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, marginBottom: 6 }}>
        <span style={{ fontSize: compact ? 11.5 : 12.5, fontWeight: 700, lineHeight: 1.3 }}>{feature.name}</span>
        <ComplexityChip cls={feature.size} size={22} />
      </div>
      {!compact && feature.description && (
        <p style={{ fontSize: 11.5, color: "var(--muted-foreground)", lineHeight: 1.5, margin: "0 0 8px" }}>
          {feature.description}
        </p>
      )}
      {feature.dependencies.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          <Icon name="link" size={11} style={{ color: "var(--muted-foreground)", marginTop: 1.5, flexShrink: 0 }} />
          {feature.dependencies.map((dep, i) => (
            <span key={i} style={{
              fontSize: 10, padding: "2px 6px", borderRadius: 5,
              background: "var(--muted)", border: "1px solid var(--border)",
              color: "var(--muted-foreground)",
            }}>{dep}</span>
          ))}
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
              <p className="text-xs text-muted-foreground">Stage 4 — Sprint Tracker</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {latestResult && (
              <>
                <span style={{
                  display: "inline-flex", alignItems: "center", gap: 5, height: 30, padding: "0 10px",
                  borderRadius: 6, fontSize: 11.5, fontWeight: 600,
                  color: "var(--c-green)",
                  background: "color-mix(in oklab, var(--c-green) 12%, transparent)",
                  border: "1px solid color-mix(in oklab, var(--c-green) 28%, transparent)",
                }}>
                  <Icon name="check" size={12} /> {latestResult.features.length} features · {sprintNumbers.length} sprints
                </span>
                <Button variant="outline" size="sm" onClick={handleExport}>
                  <Download className="mr-1.5 h-3.5 w-3.5" />Export XLSX
                </Button>
              </>
            )}
            <RunHistoryDrawer runs={runs} stage="s4" stageName="Stage 4 - Sprint Tracker" />
            <Button size="sm" onClick={handleRunStage} disabled={!canRun || isRunning}>
              <Play className="mr-1.5 h-3.5 w-3.5" />
              {isRunning ? "Running…" : "Decompose & Assign"}
            </Button>
          </div>
        </div>
      </header>

      <div className="container max-w-6xl py-6 space-y-6">
        {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        {isStale && <StalenessIndicator isStale stageName="Stage 4" />}
        {isRunning && (
          <AsyncRunProgress useCaseId={ucId} stage="s4" onComplete={handleRunComplete} onError={(e) => setError(e)} />
        )}

        {/* ── Config card ── */}
        <div style={{ borderRadius: 14, border: "1px solid var(--border)", background: "var(--card)", padding: 20 }}>
          <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: "1.4px", textTransform: "uppercase", color: "var(--muted-foreground)", marginBottom: 16 }}>
            Sprint configuration
          </div>
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
          <div style={{ display: "flex", gap: 8 }}>
            <Button onClick={handleRunStage} disabled={!canRun || isRunning}>
              <Play className="mr-2 h-4 w-4" />
              {isRunning ? "Running…" : "Decompose & Assign Sprints"}
            </Button>
            <Button variant="outline" onClick={handleLoadFromS2} disabled={isRunning}>
              <Icon name="link" size={13} style={{ marginRight: 6 }} />Load from S2
            </Button>
            <Button variant="outline" onClick={handleLoadFromS3} disabled={isRunning}>
              <Icon name="link" size={13} style={{ marginRight: 6 }} />Load from S3
            </Button>
          </div>
        </div>

        {/* ── Sprint board ── */}
        {latestResult && sprintNumbers.length > 0 && (
          <>
            {/* View tabs */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", gap: 1, borderRadius: 9, border: "1px solid var(--border)", padding: 3 }}>
                {(["board", "features"] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    style={{
                      padding: "5px 14px", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer",
                      background: activeTab === tab ? "color-mix(in oklab, var(--primary) 16%, transparent)" : "transparent",
                      color: activeTab === tab ? "var(--primary)" : "var(--muted-foreground)",
                      border: "none",
                      transition: "all 0.12s",
                    }}
                  >
                    {tab === "board" ? "Sprint board" : "Feature list"}
                  </button>
                ))}
              </div>
              <div style={{ fontSize: 12, color: "var(--muted-foreground)" }}>
                {latestResult.features.length} features · {sprintLength}w sprints · Sonnet 4.5
              </div>
            </div>

            {/* Board view */}
            {activeTab === "board" && (
              <div style={{ display: "grid", gap: 14, gridTemplateColumns: `repeat(${Math.min(sprintNumbers.length, 4)}, 1fr)` }}>
                {sprintNumbers.map((sprintNum) => {
                  const items = sprintGroups[sprintNum] || []
                  const fillPct = (items.length / maxFeaturesInSprint) * 100
                  return (
                    <div key={sprintNum}>
                      {/* Sprint header */}
                      <div style={{
                        borderRadius: 12, border: "1px solid var(--border)", background: "var(--card)",
                        padding: "12px 14px", marginBottom: 10,
                      }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                          <span style={{
                            fontSize: 11, fontWeight: 700, padding: "3px 9px", borderRadius: 6,
                            color: "var(--primary)",
                            background: "color-mix(in oklab, var(--primary) 14%, transparent)",
                            border: "1px solid color-mix(in oklab, var(--primary) 28%, transparent)",
                          }}>
                            Sprint {sprintNum}
                          </span>
                          <span style={{ fontSize: 11, color: "var(--muted-foreground)" }}>
                            {items.length} feature{items.length !== 1 ? "s" : ""}
                          </span>
                        </div>
                        {/* Capacity bar */}
                        <div style={{ height: 5, borderRadius: 99, background: "var(--track)", overflow: "hidden" }}>
                          <div style={{
                            width: `${fillPct}%`, height: "100%",
                            background: fillPct > 80 ? "var(--c-amber)" : "var(--primary)",
                            borderRadius: 99, transition: "width 0.3s",
                          }} />
                        </div>
                      </div>

                      {/* Feature cards */}
                      <div style={{
                        padding: "6px 0", borderRadius: 12,
                        border: "1px dashed color-mix(in oklab, var(--border) 60%, transparent)",
                        display: "flex", flexDirection: "column", gap: 6, minHeight: 60,
                      }}>
                        {items.map((sp, idx) => (
                          <div key={idx} style={{ padding: "0 6px" }}>
                            <FeatureCard sp={sp} />
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {/* Feature list view */}
            {activeTab === "features" && (
              <div style={{ borderRadius: 14, border: "1px solid var(--border)", background: "var(--card)", overflow: "hidden" }}>
                {/* Table header */}
                <div style={{
                  display: "grid", gridTemplateColumns: "2fr 1fr 1fr 80px",
                  padding: "10px 18px", fontSize: 10, fontWeight: 700,
                  letterSpacing: 0.5, textTransform: "uppercase",
                  color: "var(--muted-foreground)", borderBottom: "1px solid var(--border)",
                }}>
                  <span>Feature</span>
                  <span>Size</span>
                  <span>Dependencies</span>
                  <span style={{ textAlign: "right" }}>Sprint</span>
                </div>
                {latestResult.sprint_plan.map((sp, idx) => (
                  <div key={idx} style={{
                    display: "grid", gridTemplateColumns: "2fr 1fr 1fr 80px",
                    padding: "11px 18px", alignItems: "center",
                    borderBottom: idx < latestResult.sprint_plan.length - 1 ? "1px solid var(--border)" : "none",
                  }}>
                    <div>
                      <div style={{ fontSize: 12.5, fontWeight: 600 }}>{sp.feature.name}</div>
                      {sp.feature.description && (
                        <div style={{ fontSize: 11, color: "var(--muted-foreground)", marginTop: 2 }}>
                          {sp.feature.description}
                        </div>
                      )}
                    </div>
                    <ComplexityChip cls={sp.feature.size} size={26} />
                    <div style={{ fontSize: 11, color: "var(--muted-foreground)" }}>
                      {sp.feature.dependencies.length > 0
                        ? sp.feature.dependencies.join(", ")
                        : "—"}
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <span style={{
                        fontSize: 11, fontWeight: 700, padding: "3px 8px", borderRadius: 6,
                        color: "var(--primary)",
                        background: "color-mix(in oklab, var(--primary) 13%, transparent)",
                      }}>
                        S{sp.sprint_number}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Size legend */}
            <div style={{ display: "flex", alignItems: "center", gap: 16, paddingTop: 4 }}>
              <span style={{ fontSize: 11, color: "var(--muted-foreground)" }}>Size legend:</span>
              {(["XS", "S", "M", "L", "XL"] as Band[]).map((b) => (
                <div key={b} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--muted-foreground)" }}>
                  <ComplexityChip cls={b} size={18} />
                  {b === "XS" ? "1w" : b === "S" ? "2–4w" : b === "M" ? "5w" : b === "L" ? "6w" : "8w"}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

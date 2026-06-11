"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { StalenessIndicator } from "@/components/shared/StalenessIndicator"
import { AsyncRunProgress } from "@/components/shared/AsyncRunProgress"
import { StageHeader } from "@/components/shared/StageHeader"
import { CLS_COLORS } from "@/components/shared/ComplexityChip"
import { Card, Btn, SectionLabel, Pill } from "@/components/rpa"
import { Icon } from "@/components/shared/icons"
import { Loader2, CheckCircle, AlertCircle } from "lucide-react"
import { toast } from "sonner"
import { spacing } from "@/lib/design-tokens"
import { apiGet, apiGetRuns, apiPost, apiPatch, isAuthenticated } from "@/lib/api"
import type { UseCase, StageRun, S4Result, SequencedRow, ReadinessResponse } from "@/lib/types"

/* FeatureCard */
interface FeatureCardProps {
  row: SequencedRow
  compact?: boolean
}

function FeatureCard({ row, compact }: FeatureCardProps) {
  // Estimate priority color
  const priorityColors: Record<string, string> = {
    high: "var(--c-red)",
    medium: "var(--c-amber)",
    low: "var(--c-green)",
  }
  const color = priorityColors[row.priority?.toLowerCase() || "medium"] || "var(--primary)"

  return (
    <div className="rpa-card-hover" style={{
      borderRadius: 10, border: "1px solid var(--border)",
      background: "var(--surface-2)",
      padding: compact ? "9px 11px" : "11px 13px",
      borderLeft: `3px solid ${color}`,
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
        <span style={{ fontSize: 12.5, fontWeight: 600, lineHeight: 1.3 }}>{row.feature}</span>
        <span style={{
          flexShrink: 0, fontFamily: "var(--mono)", fontSize: 10, fontWeight: 700,
          color, background: `color-mix(in oklab, ${color} 15%, transparent)`,
          border: `1px solid color-mix(in oklab, ${color} 32%, transparent)`,
          borderRadius: 5, padding: "2px 6px",
        }}>
          {row.hours}h
        </span>
      </div>
      {!compact && (
        <div style={{ fontSize: 11, color: "var(--muted-fg)", marginTop: 5, lineHeight: 1.4 }}>
          {row.start_date} to {row.end_date}
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
  const [projectUseCases, setProjectUseCases] = useState<UseCase[]>([])

  // Auto-run state (when navigating from S3 with ?autoRun=true)
  const searchParams = useSearchParams()
  const shouldAutoRun = searchParams?.get('autoRun') === 'true'
  const [s3DataLoaded, setS3DataLoaded] = useState(false)
  const [s4RunTriggered, setS4RunTriggered] = useState(false)
  const [isAutoRunning, setIsAutoRunning] = useState(false)
  const [autoRunError, setAutoRunError] = useState<string | null>(null)

  useEffect(() => {
    if (!isAuthenticated()) { router.push("/auth/login"); return }

    const fetchData = async () => {
      try {
        const [ucData, readinessData, runsData, useCasesData] =
          await Promise.all([
            apiGet<UseCase>(`/api/v1/use-cases/${ucId}`),
            apiGet<ReadinessResponse>(`/api/v1/use-cases/${ucId}/readiness`),
            apiGetRuns<StageRun>(`/api/v1/use-cases/${ucId}/s4/runs`),
            apiGet<UseCase[]>(`/api/v1/projects/${projectId}/use-cases`).catch(
              () => [] as UseCase[],
            ),
          ])
        setUseCase(ucData)
        setReadiness(readinessData)
        setRuns(runsData)
        setProjectUseCases(useCasesData)

        if (ucData.s4_inputs?.sprint_count)        setSprintCount(ucData.s4_inputs.sprint_count as number)
        if (ucData.s4_inputs?.sprint_length_weeks) setSprintLength(ucData.s4_inputs.sprint_length_weeks as number)

        if (ucData.s4_latest_run_id) {
          const latestRun = runsData.find((r) => r.id === ucData.s4_latest_run_id)
          if (latestRun?.status === "complete") {
            // List endpoint returns summary only — fetch full result from single-run endpoint
            const fullRun = await apiGet<{ result: S4Result }>(`/api/v1/use-cases/${ucId}/s4/runs/${ucData.s4_latest_run_id}`)
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

  // Auto-load S3 data when navigating from S3
  useEffect(() => {
    if (!shouldAutoRun || s3DataLoaded || loading) return

    async function autoLoadFromS3() {
      try {
        console.log('[S4] Auto-loading data from S3...')
        await apiPost(`/api/v1/use-cases/${ucId}/s4/load-from-s3`, {})
        console.log('[S4] S3 data loaded successfully')
        setS3DataLoaded(true)
      } catch (error) {
        console.error('[S4] Auto-load failed:', error)
        setAutoRunError(error instanceof Error ? error.message : 'Failed to load S3 data')
      }
    }

    autoLoadFromS3()
  }, [ucId, shouldAutoRun, s3DataLoaded, loading])

  // Auto-trigger S4 run after S3 data loaded
  useEffect(() => {
    if (!s3DataLoaded || !shouldAutoRun || s4RunTriggered || isAutoRunning) return

    async function autoTriggerS4Run() {
      try {
        console.log('[S4] Auto-triggering S4 run...')
        setIsAutoRunning(true)
        setS4RunTriggered(true)
        setRunningStage(true)

        await apiPost(`/api/v1/use-cases/${ucId}/s4/runs`, {})
        console.log('[S4] Run triggered successfully')

        // Polling will be handled by AsyncRunProgress component
      } catch (error) {
        console.error('[S4] Auto-run failed:', error)
        setAutoRunError(error instanceof Error ? error.message : 'Failed to trigger S4 run')
        setIsAutoRunning(false)
        setRunningStage(false)
      }
    }

    autoTriggerS4Run()
  }, [s3DataLoaded, shouldAutoRun, s4RunTriggered, isAutoRunning, ucId])

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
        sprint_count: sprintCount, sprint_length_weeks: sprintLength,
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

  const sprintGroups = latestResult?.sequenced_rows.reduce<Record<number, SequencedRow[]>>(
    (acc, row) => {
      if (!acc[row.sprint_number]) acc[row.sprint_number] = []
      acc[row.sprint_number].push(row)
      return acc
    },
    {}
  ) || {}
  const sprintNumbers = Object.keys(sprintGroups).map(Number).sort((a, b) => a - b)

  /* Max rows per sprint (capacity proxy) */
  const maxFeaturesInSprint = Math.max(...sprintNumbers.map((n) => sprintGroups[n].length), 1)

  return (
    <div className="min-h-screen bg-background">
      <StageHeader
        projectId={projectId}
        stageNumber={4}
        stageName="Sprint Tracker"
        stageId="s4"
        ucId={ucId}
        useCase={useCase}
        useCases={[...projectUseCases].sort((a, b) => a.name.localeCompare(b.name))}
        runs={runs}
        currentRunId={useCase?.s4_latest_run_id}
        isComplete={!!latestResult}
        actions={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {latestResult && (
              <>
                <Pill color="var(--c-green)">
                  <Icon name="check" size={11} /> {latestResult.wbs_rows.length} tasks · {sprintNumbers.length} sprints
                </Pill>
                <Btn variant="outline" size="sm" onClick={handleExport} icon="download">
                  Export XLSX
                </Btn>
              </>
            )}
            <Btn size="sm" onClick={handleRunStage} disabled={!canRun || isRunning} icon="play">
              {isRunning ? "Running…" : "Decompose & Assign"}
            </Btn>
          </div>
        }
      />

      <div style={{ height: "calc(100vh - 56px)", overflow: "hidden", padding: "24px 28px", display: "flex", flexDirection: "column", gap: spacing.gapDefault }}>
        {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        {isStale && <StalenessIndicator isStale stageName="Stage 4" />}

        {/* Auto-run Loading State */}
        {shouldAutoRun && isAutoRunning && (
          <Card style={{ padding: "24px" }}>
            <div style={{ display: "flex", alignItems: "start", gap: "16px" }}>
              <Loader2 style={{ height: "24px", width: "24px", flexShrink: 0, marginTop: "4px" }} className="animate-spin text-primary" />
              <div style={{ flex: 1 }}>
                <h3 style={{ fontWeight: 600, fontSize: "18px", marginBottom: "4px" }}>
                  Generating Sprint Plan...
                </h3>
                <p style={{ fontSize: "14px", color: "var(--muted-fg)", marginBottom: "16px" }}>
                  Analyzing tasks and assigning to sprints. This may take 30-60 seconds.
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px" }}>
                    <CheckCircle style={{ height: "16px", width: "16px", color: "var(--c-green)" }} />
                    <span>Loaded S3 timeline data</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px" }}>
                    <Loader2 style={{ height: "16px", width: "16px" }} className="animate-spin" />
                    <span>Grouping tasks into work breakdown structure...</span>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        )}

        {/* Auto-run Error State */}
        {shouldAutoRun && autoRunError && (
          <Alert variant="destructive">
            <AlertCircle style={{ height: "16px", width: "16px" }} />
            <AlertTitle>Auto-run Failed</AlertTitle>
            <AlertDescription>
              {autoRunError}
              <div style={{ display: "flex", gap: "8px", marginTop: "12px" }}>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setAutoRunError(null)
                    setS4RunTriggered(false)
                    setS3DataLoaded(false)
                  }}
                >
                  Retry Auto-run
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    router.replace(`/projects/${projectId}/stage4/${ucId}`)
                  }}
                >
                  Switch to Manual Mode
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        )}

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
                    ? `${latestResult.wbs_rows.length} tasks · ${sprintNumbers.length} sprints × ${sprintLength} weeks · assigned by date from timeline`
                    : "AI groups Stage 3 tasks into WBS rows and assigns to sprints."}
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
                            {items.length} tasks
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
                        {items.map((row, idx) => (
                          <FeatureCard key={`${row.feature}-${idx}`} row={row} />
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
                  <span>Task</span>
                  <span style={{ textAlign: "center" }}>Priority</span>
                  <span style={{ textAlign: "center" }}>Hours</span>
                  <span style={{ textAlign: "center" }}>Start</span>
                  <span style={{ textAlign: "center" }}>Status</span>
                  <span style={{ textAlign: "right" }}>Sprint</span>
                </div>

                {/* Table rows */}
                <div style={{ flex: 1, overflow: "auto" }}>
                  {latestResult.sequenced_rows.map((row, idx) => {
                    const priorityColors: Record<string, string> = {
                      high: "var(--c-red)",
                      medium: "var(--c-amber)",
                      low: "var(--c-green)",
                    }
                    const color = priorityColors[row.priority?.toLowerCase() || "medium"] || "var(--primary)"
                    return (
                      <div
                        key={idx}
                        className="rpa-card-hover"
                        style={{
                          display: "grid",
                          gridTemplateColumns: "2.2fr 0.6fr 0.5fr 0.7fr 0.6fr 0.7fr",
                          padding: "12px 16px",
                          alignItems: "center",
                          borderBottom: idx < latestResult.sequenced_rows.length - 1 ? "1px solid var(--border)" : "none",
                        }}
                      >
                        {/* Task name */}
                        <div style={{ minWidth: 0, paddingRight: 8 }}>
                          <div style={{ fontSize: 12.5, fontWeight: 600 }}>{row.feature}</div>
                          <div style={{
                            fontSize: 10.5,
                            color: "var(--muted-fg)",
                            marginTop: 2
                          }}>
                            {row.start_date} to {row.end_date}
                          </div>
                        </div>

                        {/* Priority */}
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
                            {row.priority}
                          </span>
                        </span>

                        {/* Hours */}
                        <span style={{
                          textAlign: "center",
                          fontFamily: "var(--mono)",
                          fontSize: 12,
                          color: "var(--fg-2)",
                        }}>
                          {row.hours}h
                        </span>

                        {/* Start Date */}
                        <span style={{ textAlign: "center", fontSize: 11.5, color: "var(--muted-fg)" }}>
                          {row.start_date || "—"}
                        </span>

                        {/* Status (placeholder) */}
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
                          S{row.sprint_number}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </Card>
            )}

            {/* Priority legend */}
            <Card style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <SectionLabel>Task Priority</SectionLabel>
              <div style={{ display: "flex", gap: 13 }}>
                {[
                  { label: "High", color: "var(--c-red)" },
                  { label: "Medium", color: "var(--c-amber)" },
                  { label: "Low", color: "var(--c-green)" }
                ].map((p) => (
                  <span key={p.label} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11.5, color: "var(--fg-2)" }}>
                    <span style={{ width: 9, height: 9, borderRadius: 2, background: p.color }} />
                    {p.label}
                  </span>
                ))}
              </div>
              <span style={{ flex: 1 }} />
              <span style={{ fontSize: 11, color: "var(--muted-fg)", display: "flex", alignItems: "center", gap: 6 }}>
                <Icon name="refresh" size={12} /> Change sprint config → re-run assigns tasks to sprints · each run versioned
              </span>
            </Card>
          </>
        )}
      </div>
    </div>
  )
}

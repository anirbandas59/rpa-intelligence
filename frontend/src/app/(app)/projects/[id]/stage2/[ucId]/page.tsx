"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Input } from "@/components/ui/input"
import { InputSourceBadge } from "@/components/shared/InputSourceBadge"
import { Card, Btn, SectionLabel, Pill } from "@/components/rpa"
import { spacing } from "@/lib/design-tokens"
import { StalenessIndicator } from "@/components/shared/StalenessIndicator"
import { AsyncRunProgress } from "@/components/shared/AsyncRunProgress"
import { RunHistoryDrawer } from "@/components/shared/RunHistoryDrawer"
import { ComplexityChip, CLS_COLORS } from "@/components/shared/ComplexityChip"
import { Icon } from "@/components/shared/icons"
import { ArrowLeft, Upload, Play, Loader2 } from "lucide-react"
import { apiGet, apiGetRuns, apiPost, apiPatch, apiPostFormData, isAuthenticated } from "@/lib/api"
import { scoreComplexity, getComplexityColor, hasAllBands, WEIGHTS } from "@/lib/scoring"
import type { UseCase, StageRun, Band, AttributeBands, ReadinessResponse, S2Result, InputSource } from "@/lib/types"

const BANDS: Band[] = ["XS", "S", "M", "L", "XL"]
const ATTRS: Array<{ key: keyof AttributeBands; label: string }> = [
  { key: "activities",     label: "Activities" },
  { key: "business_rules", label: "Business Rules" },
  { key: "layouts",        label: "Layouts" },
  { key: "interfaces",     label: "Interfaces" },
  { key: "technology",     label: "Technology" },
]

/* Score ladder — 5 segments: XS S M L XL */
const LADDER_RANGES = [
  { band: "XS" as Band, max: 6,  label: "XS" },
  { band: "S"  as Band, max: 8,  label: "S"  },
  { band: "M"  as Band, max: 15, label: "M"  },
  { band: "L"  as Band, max: 22, label: "L"  },
  { band: "XL" as Band, max: 28, label: "XL" },
]

export default function Stage2Page() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.id as string
  const ucId = params.ucId as string

  const [useCase, setUseCase] = useState<UseCase | null>(null)
  const [bands, setBands] = useState<Partial<AttributeBands>>({})
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null)
  const [runs, setRuns] = useState<StageRun[]>([])
  const [latestResult, setLatestResult] = useState<S2Result | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploadingFile, setUploadingFile] = useState(false)
  const [runningStage, setRunningStage] = useState(false)
  const [error, setError] = useState("")

  const liveScore = hasAllBands(bands as AttributeBands)
    ? scoreComplexity(bands as AttributeBands)
    : null

  useEffect(() => {
    if (!isAuthenticated()) { router.push("/auth/login"); return }

    const fetchData = async () => {
      try {
        const [ucData, readinessData, runsData] = await Promise.all([
          apiGet<UseCase>(`/api/v1/use-cases/${ucId}`),
          apiGet<ReadinessResponse>(`/api/v1/use-cases/${ucId}/readiness`),
          apiGetRuns<StageRun>(`/api/v1/use-cases/${ucId}/s2/runs`),
        ])
        setUseCase(ucData)
        setReadiness(readinessData)
        setRuns(runsData)

        if (ucData.s2_inputs?.bands) setBands(ucData.s2_inputs.bands as Partial<AttributeBands>)

        if (ucData.s2_latest_run_id && runsData.length > 0) {
          const latestRun = runsData.find((r) => r.id === ucData.s2_latest_run_id)
          if (latestRun?.status === "complete") {
            setLatestResult(latestRun.result as unknown as S2Result)
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

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadingFile(true)
    setError("")
    try {
      const formData = new FormData()
      formData.append("file", file)
      await apiPostFormData(`/api/v1/use-cases/${ucId}/s2/documents`, formData)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setUploadingFile(false)
    }
  }

  const handleBandChange = async (attribute: keyof AttributeBands, value: Band) => {
    const newBands = { ...bands, [attribute]: value }
    setBands(newBands)
    try {
      await apiPatch(`/api/v1/use-cases/${ucId}/s2/inputs`, {
        bands: { [attribute]: value, [`${attribute}_source`]: "corrected" },
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update input")
    }
  }

  const handleRunStage = async () => {
    setRunningStage(true)
    setError("")
    try {
      await apiPost(`/api/v1/use-cases/${ucId}/s2/runs`, {})
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run")
      setRunningStage(false)
    }
  }

  const handleRunComplete = () => {
    setRunningStage(false)
    window.location.reload()
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

  const isStale = readiness?.s2 === "stale"
  const isRunning = readiness?.s2 === "running" || runningStage

  const displayScore = liveScore
    ? { ...liveScore, sprint_min: liveScore.sprints, sprint_max: liveScore.sprints }
    : latestResult
      ? {
          total_score:      latestResult.total_score,
          complexity_class: latestResult.complexity_class,
          effort_min_weeks: latestResult.effort_min_weeks,
          effort_max_weeks: latestResult.effort_max_weeks,
          sprint_min:       latestResult.sprint_min,
          sprint_max:       latestResult.sprint_max,
        }
      : null

  return (
    <div className="min-h-screen bg-background">
      {/* ── Header ── */}
      <header className="border-b border-border/50 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex h-14 items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <Link href={`/projects/${projectId}`}>
              <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground -ml-2">
                <ArrowLeft className="mr-1.5 h-4 w-4" />Back
              </Button>
            </Link>
            <div className="h-4 w-px bg-border/50" />
            <div>
              <p className="text-sm font-semibold">{useCase.name}</p>
              <p className="text-xs text-muted-foreground">Stage 2 — Complexity Analysis</p>
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
                <Icon name="check" size={12} /> Complete · run #{runs.length}
              </span>
            )}
            <RunHistoryDrawer runs={runs} stage="s2" stageName="Stage 2 - Complexity" />
            <Button size="sm" onClick={handleRunStage} disabled={isRunning || !hasAllBands(bands as AttributeBands)}>
              <Play className="mr-1.5 h-3.5 w-3.5" />
              {isRunning ? "Running…" : "Run Analysis"}
            </Button>
          </div>
        </div>
      </header>

      <div className="py-6 px-7 space-y-6">
        {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        {isStale && <StalenessIndicator isStale stageName="Stage 2" />}
        {isRunning && (
          <AsyncRunProgress useCaseId={ucId} stage="s2" onComplete={handleRunComplete} onError={(e) => setError(e)} />
        )}

        {/* Main grid: band picker + result panel */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 22 }}>
          {/* ── Left: band picker ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            {/* Doc upload */}
            <div style={{ borderRadius: 14, border: "1px solid var(--border)", background: "var(--card)", padding: 18 }}>
              <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: "1.4px", textTransform: "uppercase", color: "var(--muted-foreground)", marginBottom: 14 }}>
                Input method
              </div>
              <Label
                htmlFor="file-upload"
                style={{
                  display: "flex", height: 80, cursor: "pointer", alignItems: "center", justifyContent: "center",
                  borderRadius: 10, border: "2px dashed", borderColor: "color-mix(in oklab, var(--primary) 25%, transparent)",
                  background: "color-mix(in oklab, var(--primary) 5%, transparent)",
                  transition: "border-color 0.15s",
                  gap: 10,
                }}
              >
                <Upload style={{ height: 18, width: 18, color: "var(--primary)", opacity: 0.7 }} />
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 12.5, fontWeight: 500, color: "var(--muted-foreground)" }}>
                    {uploadingFile ? "Uploading…" : "Upload Process Document (PDF / DOCX)"}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--muted-foreground)", opacity: 0.6, marginTop: 2 }}>
                    AI extracts band values automatically
                  </div>
                </div>
                <Input
                  id="file-upload" type="file" accept=".pdf,.docx"
                  className="hidden" onChange={handleFileUpload}
                  disabled={uploadingFile || isRunning}
                />
              </Label>
            </div>

            {/* 5×5 band grid */}
            <Card pad={0} style={{ overflow: "hidden" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: spacing.cardDefault, paddingBottom: 0, marginBottom: 18 }}>
                <SectionLabel>Complexity bands</SectionLabel>
                <span style={{ fontSize: 11, color: "var(--muted-fg)", fontFamily: "var(--mono)" }}>weight · 0 → 28 pts</span>
              </div>

              {/* Header row - matching exploration stage2.jsx line 113 */}
              <div style={{
                display: "grid",
                gridTemplateColumns: "1.5fr repeat(5, 1fr) 0.7fr",
                alignItems: "center",
                padding: "12px 18px",
                borderBottom: "1px solid var(--border)",
              }}>
                <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 0.5, color: "var(--muted-fg)", textTransform: "uppercase" }}>Attribute</span>
                {BANDS.map((b) => (
                  <span key={b} style={{ textAlign: "center", fontFamily: "var(--mono)", fontSize: 12, fontWeight: 700, color: CLS_COLORS[b] }}>
                    {b}
                  </span>
                ))}
                <span style={{ textAlign: "right", fontSize: 10.5, fontWeight: 700, color: "var(--muted-fg)" }}>WT</span>
              </div>

              {/* Attribute rows - matching exploration stage2.jsx line 119 */}
              {ATTRS.map(({ key, label }, idx) => {
                const active = bands[key]
                const source = useCase.s2_inputs?.[`${key}_source`] as InputSource | undefined
                return (
                  <div key={key} style={{
                    display: "grid",
                    gridTemplateColumns: "1.5fr repeat(5, 1fr) 0.7fr",
                    alignItems: "center",
                    padding: "12px 18px",
                    borderBottom: idx < ATTRS.length - 1 ? "1px solid var(--border)" : "none",
                  }}>
                    <span style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 500 }}>
                      {label} {active && source && <InputSourceBadge source={source} />}
                    </span>
                    {BANDS.map((b) => {
                      const weight = WEIGHTS[key]?.[b] ?? 0
                      const isActive = active === b
                      const color = CLS_COLORS[b]
                      return (
                        <div key={b} style={{ display: "flex", justifyContent: "center" }}>
                          <button
                            onClick={() => handleBandChange(key, b)}
                            disabled={isRunning}
                            style={{
                              width: 42,
                              height: 34,
                              borderRadius: 8,
                              cursor: "pointer",
                              fontFamily: "var(--mono)",
                              fontSize: 12,
                              fontWeight: 700,
                              color: isActive ? "#0b0b12" : "var(--muted-fg)",
                              background: isActive ? color : "var(--surface-2)",
                              border: `1px solid ${isActive ? color : "var(--border)"}`,
                              boxShadow: isActive ? `0 0 12px color-mix(in oklab, ${color} 45%, transparent)` : "none",
                              transition: "all .14s",
                            }}
                          >
                            {weight}
                          </button>
                        </div>
                      )
                    })}
                    <span style={{ textAlign: "right", fontFamily: "var(--mono)", fontSize: 14, fontWeight: 700, color: "var(--fg)" }}>
                      {active ? WEIGHTS[key]?.[active] ?? 0 : "—"}
                    </span>
                  </div>
                )
              })}
            </Card>
          </div>

          {/* ── Right: result panel ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {displayScore ? (
              <>
                {/* Complexity class card - matching exploration S2Result (stage2.jsx line 47) */}
                <Card style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 12,
                  paddingTop: 24,
                  background: `linear-gradient(160deg, color-mix(in oklab, ${CLS_COLORS[displayScore.complexity_class as Band]} 12%, var(--surface)), var(--surface) 75%)`,
                }}>
                  <SectionLabel>Complexity class</SectionLabel>
                  <ComplexityChip cls={displayScore.complexity_class as Band} size={76} />
                  <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                    <span style={{ fontFamily: "var(--mono)", fontSize: 30, fontWeight: 700 }}>
                      {displayScore.total_score}
                    </span>
                    <span style={{ fontSize: 13, color: "var(--muted-fg)" }}>/ 28 pts</span>
                  </div>
                  {/* Score scale ladder - matching exploration stage2.jsx line 56 */}
                  <div style={{ width: "100%", marginTop: 4 }}>
                    <div style={{ display: "flex", height: 8, borderRadius: 99, overflow: "hidden", gap: 2 }}>
                      {BANDS.map((k) => (
                        <div
                          key={k}
                          style={{
                            flex: k === displayScore.complexity_class ? 1.6 : 1,
                            background: k === displayScore.complexity_class ? CLS_COLORS[k] : "var(--track)",
                            transition: "flex .3s, background .3s",
                          }}
                        />
                      ))}
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 9.5, color: "var(--muted-fg)", fontFamily: "var(--mono)" }}>
                      {BANDS.map((k) => (
                        <span
                          key={k}
                          style={{
                            color: k === displayScore.complexity_class ? CLS_COLORS[k] : "var(--muted-fg)",
                            fontWeight: k === displayScore.complexity_class ? 700 : 400,
                          }}
                        >
                          {k}
                        </span>
                      ))}
                    </div>
                  </div>
                </Card>

                {/* Effort estimate card - matching exploration S2Result (stage2.jsx line 68) */}
                <Card>
                  <SectionLabel style={{ marginBottom: 12 }}>Effort estimate</SectionLabel>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                    {[
                      { label: "Min weeks", value: displayScore.effort_min_weeks },
                      { label: "Max weeks", value: displayScore.effort_max_weeks },
                      { label: "Sprints", value: `${displayScore.sprint_min ?? "?"}–${displayScore.sprint_max ?? "?"}` },
                    ].map(({ label, value }) => (
                      <div key={label} style={{
                        padding: "10px 12px", borderRadius: 9,
                        background: "color-mix(in oklab, var(--primary) 6%, transparent)",
                        border: "1px solid color-mix(in oklab, var(--primary) 15%, transparent)",
                      }}>
                        <div style={{ fontSize: 10.5, color: "var(--muted-foreground)", marginBottom: 3 }}>{label}</div>
                        <div style={{ fontFamily: "var(--font-geist-mono)", fontSize: 18, fontWeight: 700 }}>
                          {value}
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </>
            ) : (
              <div style={{
                borderRadius: 14, border: "1px dashed var(--border)", padding: "40px 18px",
                display: "flex", flexDirection: "column", alignItems: "center", gap: 12,
                color: "var(--muted-foreground)", textAlign: "center",
              }}>
                <Icon name="gauge" size={32} style={{ opacity: 0.4 }} />
                <div style={{ fontSize: 12.5 }}>Set all 5 bands to see<br />live score preview</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

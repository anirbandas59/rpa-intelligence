"use client"

import { useEffect, useState, useCallback } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { AgentActivityFeed } from "@/components/shared/AgentActivityFeed"
import { EmptyState } from "@/components/shared/EmptyState"
import { Gauge } from "@/components/shared/Gauge"
import { ComplexityChip } from "@/components/shared/ComplexityChip"
import { PriorityBadge, BAND_META } from "@/components/shared/PriorityBadge"
import { MiniSpark } from "@/components/shared/MiniSpark"
import { Icon } from "@/components/shared/icons"
import { ArrowLeft, Plus, Loader2, Users } from "lucide-react"
import { toast } from "sonner"
import { apiGet, apiGetRuns, apiPost, isAuthenticated } from "@/lib/api"
import type { Project, UseCase, ReadinessResponse, ReadinessStatus, S3ReadinessDetail, MigrationDecision, Band, S1Result, S2Result, S3Result } from "@/lib/types"

function resolveStatus(r: ReadinessResponse | undefined | null, stageId: "s1" | "s2" | "s3" | "s4"): ReadinessStatus {
  if (!r) return "not_ready"
  const val = r[stageId]
  if (stageId === "s3") return (val as S3ReadinessDetail)?.phase_calculator ?? "not_ready"
  return (val as ReadinessStatus) ?? "not_ready"
}

const STATUS_CONFIG: Record<
  ReadinessStatus,
  { label: string; dotClass: string; color: string }
> = {
  not_ready: { label: "Not Ready", dotClass: "bg-muted-foreground/40",     color: "var(--muted-foreground)" },
  ready:     { label: "Ready",     dotClass: "bg-blue-400",                color: "var(--c-blue)"           },
  running:   { label: "Running",   dotClass: "bg-primary animate-pulse",   color: "var(--primary)"          },
  complete:  { label: "Complete",  dotClass: "bg-green-500",               color: "var(--c-green)"          },
  stale:     { label: "Stale",     dotClass: "bg-amber-500",               color: "var(--c-amber)"          },
}

const STAGES = [
  { id: "s1" as const, label: "Migration Assessment", short: "S1", path: "stage1" },
  { id: "s2" as const, label: "Complexity Analysis",  short: "S2", path: "stage2" },
  { id: "s3" as const, label: "Delivery Timeline",    short: "S3", path: "stage3" },
  { id: "s4" as const, label: "Sprint Tracker",       short: "S4", path: "stage4" },
]

/* Cached stage results per UC */
interface UCCache {
  s1?: S1Result
  s2?: S2Result
  s3?: S3Result
}

export default function ProjectDetailPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.id as string

  const [project, setProject] = useState<Project | null>(null)
  const [useCases, setUseCases] = useState<UseCase[]>([])
  const [readiness, setReadiness] = useState<Map<string, ReadinessResponse>>(new Map())
  const [ucCache, setUcCache] = useState<Map<string, UCCache>>(new Map())
  const [selectedUcId, setSelectedUcId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [orchestratorSession, setOrchestratorSession] = useState<string | null>(null)
  const [newUcOpen, setNewUcOpen] = useState(false)
  const [newUcName, setNewUcName] = useState("")
  const [newUcDesc, setNewUcDesc] = useState("")
  const [creatingUc, setCreatingUc] = useState(false)
  const [activeView, setActiveView] = useState<"pipeline" | "portfolio">("pipeline")

  const fetchData = useCallback(async () => {
    try {
      const [projectData, useCasesData] = await Promise.all([
        apiGet<Project>(`/api/v1/projects/${projectId}`),
        apiGet<UseCase[]>(`/api/v1/projects/${projectId}/use-cases`),
      ])
      setProject(projectData)
      setUseCases(useCasesData)
      if (useCasesData.length > 0) setSelectedUcId(useCasesData[0].id)

      const readinessMap = new Map<string, ReadinessResponse>()
      await Promise.all(
        useCasesData.map(async (uc) => {
          try {
            const r = await apiGet<ReadinessResponse>(`/api/v1/use-cases/${uc.id}/readiness`)
            readinessMap.set(uc.id, r)
          } catch { /* skip */ }
        })
      )
      setReadiness(readinessMap)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load project")
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    if (!isAuthenticated()) { router.push("/auth/login"); return }
    fetchData()
  }, [fetchData, router])

  /* Lazily resolve stage results for hero stats */
  useEffect(() => {
    if (useCases.length === 0) return
    useCases.forEach(async (uc) => {
      const cache: UCCache = {}
      try {
        if (uc.s1_latest_run_id) {
          const runs = await apiGetRuns<{ id: string; status: string; result: unknown }>(`/api/v1/stage1/${uc.id}/s1/runs`)
          const lr = runs.find((r) => r.id === uc.s1_latest_run_id && r.status === "complete")
          if (lr) cache.s1 = lr.result as S1Result
        }
        if (uc.s2_latest_run_id) {
          const runs = await apiGetRuns<{ id: string; status: string; result: unknown }>(`/api/v1/stage2/${uc.id}/s2/runs`)
          const lr = runs.find((r) => r.id === uc.s2_latest_run_id && r.status === "complete")
          if (lr) cache.s2 = lr.result as S2Result
        }
        if (uc.s3_latest_run_id) {
          // S3 list returns summary only — fetch full result directly
          const fullRun = await apiGet<{ id: string; status: string; result: S3Result }>(`/api/v1/stage3/${uc.id}/s3/runs/${uc.s3_latest_run_id}`)
          if (fullRun.status === "complete") cache.s3 = fullRun.result
        }
      } catch { /* silent */ }
      setUcCache((prev) => new Map(prev).set(uc.id, cache))
    })
  }, [useCases])

  const handleCreateUc = async () => {
    if (!newUcName.trim()) { toast.error("Name is required"); return }
    setCreatingUc(true)
    try {
      await apiPost(`/api/v1/use-cases`, { name: newUcName, description: newUcDesc, project_id: projectId })
      toast.success("Use case created")
      setNewUcOpen(false)
      setNewUcName("")
      setNewUcDesc("")
      fetchData()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create use case")
    } finally {
      setCreatingUc(false)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  if (error || !project) {
    return (
      <div className="min-h-screen bg-background">
        <div className="container py-8">
          <Alert variant="destructive"><AlertDescription>{error || "Project not found"}</AlertDescription></Alert>
          <Link href="/projects"><Button className="mt-4">Back to Projects</Button></Link>
        </div>
      </div>
    )
  }

  const selectedUc = useCases.find((uc) => uc.id === selectedUcId)
  const selectedReadiness = selectedUcId ? readiness.get(selectedUcId) : null

  /* Hero stats */
  const quickWins = useCases.filter((uc) => {
    const c = ucCache.get(uc.id)
    return c?.s1?.migration_decision === "QUICK_WIN"
  }).length
  const totalBuildWeeks = useCases.reduce((sum, uc) => {
    const phases = ucCache.get(uc.id)?.s3?.phases || []
    const buildPhase = phases.find((p) => p.name.toLowerCase().includes("build"))
    return sum + (buildPhase?.weeks || 0)
  }, 0)
  const totalFeatures = useCases.reduce((sum, uc) => {
    return sum + 0 // s4 features not cached — placeholder
  }, 0)

  return (
    <div className="min-h-screen bg-background">
      {/* ── Header ── */}
      <header className="border-b border-border/50 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="container flex h-14 items-center gap-3">
          <Link href="/projects">
            <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground -ml-2">
              <ArrowLeft className="mr-1.5 h-4 w-4" />Projects
            </Button>
          </Link>
          <div className="h-4 w-px bg-border/50" />
          <h1 className="font-semibold text-sm">{project.name}</h1>
        </div>
      </header>

      {/* ── Hero ── */}
      <div className="gradient-hero border-b border-border/50">
        <div className="container py-8">
          <h2 className="text-3xl font-bold tracking-tight gradient-text mb-1">{project.name}</h2>
          {project.description && (
            <p className="text-muted-foreground text-sm mb-6">{project.description}</p>
          )}
          {/* Stats row */}
          <div style={{ display: "flex", gap: 20 }}>
            {[
              { label: "Use cases",   value: useCases.length,  color: "var(--primary)" },
              { label: "Quick wins",  value: quickWins,         color: "var(--c-green)" },
              { label: "Build weeks", value: totalBuildWeeks || "—", color: "var(--c-teal)" },
            ].map(({ label, value, color }) => (
              <div key={label}>
                <div style={{
                  fontFamily: "var(--font-geist-mono)", fontSize: 28, fontWeight: 700, color, lineHeight: 1,
                }}>{value}</div>
                <div style={{ fontSize: 11.5, color: "var(--muted-foreground)", marginTop: 3 }}>{label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="container py-8 space-y-8">
        {/* ── Use-case selector + action row ── */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 12.5, color: "var(--muted-foreground)" }}>Use case</span>
            {useCases.length > 0 ? (
              <select
                style={{
                  background: "var(--card)", border: "1px solid color-mix(in oklab, var(--border) 70%, transparent)",
                  color: "var(--foreground)", fontSize: 13, borderRadius: 8, padding: "6px 12px",
                  outline: "none",
                }}
                value={selectedUcId || ""}
                onChange={(e) => setSelectedUcId(e.target.value)}
              >
                {useCases.map((uc) => (
                  <option key={uc.id} value={uc.id}>{uc.name}</option>
                ))}
              </select>
            ) : (
              <span style={{ fontSize: 12.5, color: "var(--muted-foreground)" }}>No use cases yet</span>
            )}
            <span style={{
              padding: "3px 9px", borderRadius: 6, fontSize: 11, fontWeight: 600,
              color: "var(--muted-foreground)", border: "1px solid var(--border)", background: "var(--muted)",
            }}>
              {useCases.length} total
            </span>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            {/* View toggle */}
            <div style={{ display: "flex", gap: 1, borderRadius: 8, border: "1px solid var(--border)", padding: 3 }}>
              {(["pipeline", "portfolio"] as const).map((v) => (
                <button
                  key={v}
                  onClick={() => setActiveView(v)}
                  style={{
                    padding: "5px 12px", borderRadius: 5, fontSize: 12, fontWeight: 600, cursor: "pointer",
                    background: activeView === v ? "color-mix(in oklab, var(--primary) 16%, transparent)" : "transparent",
                    color: activeView === v ? "var(--primary)" : "var(--muted-foreground)",
                    border: "none", transition: "all 0.12s",
                  }}
                >
                  {v === "pipeline" ? "Pipeline" : "Portfolio map"}
                </button>
              ))}
            </div>
            <Button size="sm" onClick={() => setNewUcOpen(true)}>
              <Plus className="mr-1.5 h-4 w-4" />New Use Case
            </Button>
          </div>
        </div>

        {/* ══ PIPELINE VIEW ══════════════════════════════════════════ */}
        {activeView === "pipeline" && (
          <>
            {selectedUc ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <div style={{
                  fontSize: 10, fontWeight: 700, letterSpacing: "1.8px", textTransform: "uppercase",
                  color: "var(--muted-foreground)",
                }}>
                  Assessment pipeline — {selectedUc.name}
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
                  {STAGES.map((stage, idx) => {
                    const status: ReadinessStatus = resolveStatus(selectedReadiness, stage.id)
                    const cfg = STATUS_CONFIG[status]
                    const cache = ucCache.get(selectedUcId || "")
                    const href = `/projects/${projectId}/${stage.path}/${selectedUc.id}`

                    return (
                      <div key={stage.id} style={{
                        borderRadius: 13, border: `1px solid var(--border)`, background: "var(--card)",
                        padding: 16, display: "flex", flexDirection: "column", gap: 12,
                        transition: "border-color 0.15s",
                      }}>
                        {/* Header */}
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <span style={{
                            fontSize: 10.5, fontWeight: 700, padding: "3px 8px", borderRadius: 5,
                            fontFamily: "var(--font-geist-mono)",
                            color: "var(--primary)",
                            background: "color-mix(in oklab, var(--primary) 13%, transparent)",
                            border: "1px solid color-mix(in oklab, var(--primary) 25%, transparent)",
                          }}>
                            {stage.short}
                          </span>
                          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                            <div style={{
                              width: 7, height: 7, borderRadius: 99,
                              background: cfg.color,
                              ...(status === "running" ? { animation: "rpaPulse 1.6s ease-in-out infinite" } : {}),
                            }} />
                            <span style={{ fontSize: 11, fontWeight: 600, color: cfg.color }}>{cfg.label}</span>
                          </div>
                        </div>

                        <div style={{ fontSize: 12.5, fontWeight: 700 }}>{stage.label}</div>

                        {/* Mini viz */}
                        <div style={{ minHeight: 36, display: "flex", alignItems: "center", gap: 8 }}>
                          {stage.id === "s1" && cache?.s1 && (
                            <>
                              <Gauge value={cache.s1.total_score} band={cache.s1.migration_decision} size={40} thick={5} />
                              <PriorityBadge band={cache.s1.migration_decision} />
                            </>
                          )}
                          {stage.id === "s2" && cache?.s2 && (
                            <>
                              <ComplexityChip cls={cache.s2.complexity_class as Band} size={28} />
                              <span style={{ fontSize: 12, color: "var(--muted-foreground)", fontFamily: "var(--font-geist-mono)" }}>
                                {cache.s2.effort_min_weeks === cache.s2.effort_max_weeks
                                  ? `${cache.s2.effort_min_weeks}w`
                                  : `${cache.s2.effort_min_weeks}–${cache.s2.effort_max_weeks}w`}
                              </span>
                            </>
                          )}
                          {stage.id === "s3" && cache?.s3 && (
                            <>
                              <MiniSpark
                                values={cache.s3.phases.map((p) => p.weeks)}
                                color="var(--c-teal)"
                                w={56} h={22}
                              />
                              <span style={{ fontSize: 12, color: "var(--muted-foreground)", fontFamily: "var(--font-geist-mono)" }}>
                                {cache.s3.phases.reduce((s, p) => s + p.weeks, 0)}w
                              </span>
                            </>
                          )}
                          {stage.id === "s4" && status === "complete" && (
                            <span style={{ fontSize: 12, color: "var(--c-violet)" }}>
                              Sprint plan ready
                            </span>
                          )}
                        </div>

                        {/* Open button */}
                        <Link href={href}>
                          <button style={{
                            width: "100%", height: 30, borderRadius: 7, fontSize: 12, fontWeight: 600,
                            cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                            background: status === "not_ready"
                              ? "color-mix(in oklab, var(--muted) 50%, transparent)"
                              : "color-mix(in oklab, var(--primary) 16%, transparent)",
                            color: status === "not_ready" ? "var(--muted-foreground)" : "var(--primary)",
                            border: `1px solid ${status === "not_ready" ? "var(--border)" : "color-mix(in oklab, var(--primary) 28%, transparent)"}`,
                            transition: "all 0.12s",
                          }}>
                            {status === "running" ? "View progress" : status === "not_ready" ? "Configure" : "Open"}
                            <Icon name="arrowR" size={11} />
                          </button>
                        </Link>
                      </div>
                    )
                  })}
                </div>

                {orchestratorSession && (
                  <AgentActivityFeed useCaseId={selectedUc.id} sessionId={orchestratorSession} />
                )}
              </div>
            ) : (
              <EmptyState
                icon={<Users className="h-8 w-8" />}
                title="No use cases yet"
                description="Create your first use case to start the four-stage assessment pipeline."
                action={
                  <Button size="sm" onClick={() => setNewUcOpen(true)}>
                    <Plus className="mr-1.5 h-4 w-4" />Create Use Case
                  </Button>
                }
              />
            )}
          </>
        )}

        {/* ══ PORTFOLIO MAP ══════════════════════════════════════════ */}
        {activeView === "portfolio" && (
          <div style={{ borderRadius: 14, border: "1px solid var(--border)", background: "var(--card)", overflow: "hidden" }}>
            {/* Quadrant SVG bubble chart */}
            <div style={{ padding: "18px 18px 10px", fontSize: 10.5, fontWeight: 700, letterSpacing: "1.4px", textTransform: "uppercase", color: "var(--muted-foreground)" }}>
              Priority × Complexity map
            </div>
            <div style={{ position: "relative", height: 320, margin: "0 18px 18px" }}>
              <svg width="100%" height="100%" style={{ position: "absolute", inset: 0 }}>
                {/* Quick-win zone tint */}
                <rect x="50%" y="0" width="50%" height="50%" rx={8} fill="color-mix(in oklab, var(--c-green) 8%, transparent)" />
                {/* Axis labels */}
                <text x="50%" y={14} textAnchor="middle" fontSize={9} fill="var(--muted-foreground)">← lower complexity</text>
                <text x={14} y="50%" dominantBaseline="middle" fontSize={9} fill="var(--muted-foreground)" transform={`rotate(-90, 14, 160)`}>← lower score</text>

                {useCases.map((uc) => {
                  const cache = ucCache.get(uc.id)
                  if (!cache?.s1 || !cache.s2) return null
                  const score = cache.s1.total_score
                  const complexityMap: Record<string, number> = { XS: 1, S: 2, M: 3, L: 4, XL: 5 }
                  const cxVal = complexityMap[cache.s2.complexity_class] || 3
                  const cx = (1 - (cxVal - 1) / 4) * 90 + 5   /* invert: low complexity = right */
                  const cy = (1 - score / 100) * 90 + 5
                  const color = BAND_META[cache.s1.migration_decision]?.color || "var(--primary)"
                  const r = 8 + (cache.s2.effort_max_weeks || 4) * 1.2
                  return (
                    <g key={uc.id}>
                      <circle
                        cx={`${cx}%`} cy={`${cy}%`} r={r}
                        fill={`color-mix(in oklab, ${color} 30%, transparent)`}
                        stroke={color} strokeWidth={1.5}
                      />
                      <text
                        x={`${cx}%`} y={`${cy}%`} textAnchor="middle"
                        dominantBaseline="middle" fontSize={8.5}
                        fill="var(--foreground)" fontWeight={600}
                      >
                        {uc.name.slice(0, 8)}
                      </text>
                    </g>
                  )
                })}
              </svg>
            </div>
            {/* Legend */}
            <div style={{ display: "flex", gap: 14, padding: "0 18px 16px", flexWrap: "wrap" }}>
              {(["QUICK_WIN", "STRATEGIC", "HOLD", "DO_NOT_MIGRATE"] as MigrationDecision[]).map((b) => (
                <div key={b} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
                  <div style={{ width: 10, height: 10, borderRadius: 99, background: BAND_META[b].color }} />
                  {BAND_META[b].label}
                </div>
              ))}
              <div style={{ fontSize: 10.5, color: "var(--muted-foreground)", marginLeft: 4 }}>
                Bubble size = effort weeks
              </div>
            </div>
          </div>
        )}

        {/* ── All use cases list ── */}
        {useCases.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{
              fontSize: 10, fontWeight: 700, letterSpacing: "1.8px", textTransform: "uppercase",
              color: "var(--muted-foreground)",
            }}>All use cases</div>

            {/* Table header */}
            <div style={{
              display: "grid", gridTemplateColumns: "2fr 1fr 1fr 110px 80px",
              padding: "9px 16px",
              fontSize: 10, fontWeight: 700, letterSpacing: 0.5, textTransform: "uppercase",
              color: "var(--muted-foreground)",
              borderBottom: "1px solid var(--border)",
            }}>
              <span>Name</span>
              <span>Priority</span>
              <span>Complexity</span>
              <span>Stages</span>
              <span style={{ textAlign: "right" }}>Progress</span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
              {useCases.map((uc) => {
                const ucReadiness = readiness.get(uc.id)
                const stages = STAGES.map((s) => resolveStatus(ucReadiness, s.id))
                const completedCount = stages.filter((s) => s === "complete").length
                const cache = ucCache.get(uc.id)
                const isSelected = uc.id === selectedUcId

                return (
                  <button
                    key={uc.id}
                    onClick={() => setSelectedUcId(uc.id)}
                    style={{
                      width: "100%", textAlign: "left", cursor: "pointer",
                      display: "grid", gridTemplateColumns: "2fr 1fr 1fr 110px 80px",
                      alignItems: "center",
                      padding: "12px 16px", borderRadius: 10,
                      border: "1px solid",
                      borderColor: isSelected
                        ? "color-mix(in oklab, var(--primary) 40%, transparent)"
                        : "color-mix(in oklab, var(--border) 60%, transparent)",
                      background: isSelected
                        ? "color-mix(in oklab, var(--primary) 6%, var(--card))"
                        : "var(--card)",
                      transition: "all 0.12s",
                    }}
                  >
                    <div style={{ minWidth: 0, paddingRight: 12 }}>
                      <div style={{ fontSize: 12.5, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {uc.name}
                      </div>
                      {uc.description && (
                        <div style={{ fontSize: 11, color: "var(--muted-foreground)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {uc.description}
                        </div>
                      )}
                    </div>

                    <div>
                      {cache?.s1?.migration_decision
                        ? <PriorityBadge band={cache.s1.migration_decision} />
                        : <span style={{ fontSize: 11, color: "var(--muted-foreground)" }}>—</span>}
                    </div>

                    <div>
                      {cache?.s2?.complexity_class
                        ? <ComplexityChip cls={cache.s2.complexity_class as Band} size={24} />
                        : <span style={{ fontSize: 11, color: "var(--muted-foreground)" }}>—</span>}
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                      {STAGES.map((stage) => {
                        const status: ReadinessStatus = resolveStatus(ucReadiness, stage.id)
                        const cfg = STATUS_CONFIG[status]
                        return (
                          <div
                            key={stage.id}
                            title={`${stage.short}: ${cfg.label}`}
                            style={{
                              width: 8, height: 8, borderRadius: 99,
                              background: cfg.color,
                            }}
                          />
                        )
                      })}
                    </div>

                    <div style={{ textAlign: "right" }}>
                      <span style={{
                        fontFamily: "var(--font-geist-mono)", fontSize: 12, fontWeight: 700,
                        color: completedCount === 4 ? "var(--c-green)" : "var(--muted-foreground)",
                      }}>
                        {completedCount}/4
                      </span>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* ── New Use Case Sheet ── */}
      <Sheet open={newUcOpen} onOpenChange={setNewUcOpen}>
        <SheetContent className="w-[440px]">
          <SheetHeader>
            <SheetTitle>New Use Case</SheetTitle>
          </SheetHeader>
          <p className="text-sm text-muted-foreground mt-2 mb-6">
            Add a use case to this project. You can run all four stages independently after creation.
          </p>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Name <span className="text-destructive">*</span></Label>
              <Input
                placeholder="e.g., Invoice processing automation"
                value={newUcName}
                onChange={(e) => setNewUcName(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") handleCreateUc() }}
              />
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea
                placeholder="Brief description of the RPA use case…"
                value={newUcDesc}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setNewUcDesc(e.target.value)}
                rows={3}
              />
            </div>
            <div className="flex gap-2 pt-2">
              <Button variant="outline" className="flex-1" onClick={() => setNewUcOpen(false)}>Cancel</Button>
              <Button className="flex-1" onClick={handleCreateUc} disabled={creatingUc}>
                {creatingUc ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Plus className="h-4 w-4 mr-2" />}
                Create
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}

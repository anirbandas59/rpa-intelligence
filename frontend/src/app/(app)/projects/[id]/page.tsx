"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AgentActivityFeed } from "@/components/shared/AgentActivityFeed"
import { EmptyState } from "@/components/shared/EmptyState"
import {
  ArrowLeft,
  Plus,
  Loader2,
  ChevronRight,
  CheckCircle2,
  Circle,
  AlertCircle,
  ArrowRight,
  Users,
} from "lucide-react"
import { apiGet, isAuthenticated } from "@/lib/api"
import type { Project, UseCase, ReadinessResponse, ReadinessStatus } from "@/lib/types"

const STATUS_CONFIG: Record<
  ReadinessStatus,
  { label: string; dotClass: string; textClass: string }
> = {
  not_ready: {
    label: "Not Ready",
    dotClass: "bg-muted-foreground/40",
    textClass: "text-muted-foreground/60",
  },
  ready: {
    label: "Ready",
    dotClass: "bg-blue-400",
    textClass: "text-blue-400",
  },
  running: {
    label: "Running",
    dotClass: "bg-primary animate-pulse",
    textClass: "text-primary",
  },
  complete: {
    label: "Complete",
    dotClass: "bg-green-500",
    textClass: "text-green-400",
  },
  stale: {
    label: "Stale",
    dotClass: "bg-amber-500",
    textClass: "text-amber-400",
  },
}

const STAGES = [
  {
    id: "s1" as const,
    label: "Migration Assessment",
    short: "S1",
    path: "stage1",
  },
  {
    id: "s2" as const,
    label: "Complexity Analysis",
    short: "S2",
    path: "stage2",
  },
  {
    id: "s3" as const,
    label: "Delivery Timeline",
    short: "S3",
    path: "stage3",
  },
  {
    id: "s4" as const,
    label: "Sprint Tracker",
    short: "S4",
    path: "stage4",
  },
]

interface StagePipelineNodeProps {
  stage: (typeof STAGES)[number]
  status: ReadinessStatus
  isLast: boolean
  href: string
}

function StagePipelineNode({ stage, status, isLast, href }: StagePipelineNodeProps) {
  const config = STATUS_CONFIG[status]

  return (
    <div className="flex items-center gap-3 flex-1 min-w-0">
      <div className="glass-card rounded-xl border border-border/50 hover:glow-primary hover:-translate-y-0.5 transition-all duration-200 p-4 flex-1 min-w-0">
        {/* Top row: badge + status dot */}
        <div className="flex items-center justify-between mb-3">
          <Badge
            variant="outline"
            className="text-[10px] font-mono border-primary/30 text-primary bg-primary/10 px-1.5"
          >
            {stage.short}
          </Badge>
          <div className="flex items-center gap-1.5">
            <div className={`h-2 w-2 rounded-full ${config.dotClass}`} />
            <span className={`text-xs font-medium ${config.textClass}`}>{config.label}</span>
          </div>
        </div>

        {/* Stage name */}
        <div className="text-sm font-semibold mb-4 leading-tight">{stage.label}</div>

        {/* Go button */}
        <Link href={href}>
          <Button
            variant={status === "not_ready" ? "outline" : "default"}
            size="sm"
            className="w-full text-xs h-7"
          >
            {status === "running" ? "View Progress" : status === "not_ready" ? "Configure" : "Open"}
            <ArrowRight className="ml-1.5 h-3 w-3" />
          </Button>
        </Link>
      </div>

      {!isLast && (
        <ChevronRight className="h-4 w-4 text-muted-foreground/40 shrink-0" />
      )}
    </div>
  )
}

export default function ProjectDetailPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.id as string

  const [project, setProject] = useState<Project | null>(null)
  const [useCases, setUseCases] = useState<UseCase[]>([])
  const [readiness, setReadiness] = useState<Map<string, ReadinessResponse>>(new Map())
  const [selectedUcId, setSelectedUcId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [orchestratorSession, setOrchestratorSession] = useState<string | null>(null)

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/auth/login")
      return
    }

    const fetchData = async () => {
      try {
        const [projectData, useCasesData] = await Promise.all([
          apiGet<Project>(`/api/v1/projects/${projectId}`),
          apiGet<UseCase[]>(`/api/v1/projects/${projectId}/use-cases`),
        ])
        setProject(projectData)
        setUseCases(useCasesData)

        if (useCasesData.length > 0) {
          setSelectedUcId(useCasesData[0].id)
        }

        // Fetch readiness for each use case
        const readinessMap = new Map<string, ReadinessResponse>()
        await Promise.all(
          useCasesData.map(async (uc) => {
            try {
              const r = await apiGet<ReadinessResponse>(`/api/v1/use-cases/${uc.id}/readiness`)
              readinessMap.set(uc.id, r)
            } catch {
              // skip
            }
          })
        )
        setReadiness(readinessMap)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load project")
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [projectId, router])

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
          <Alert variant="destructive">
            <AlertDescription>{error || "Project not found"}</AlertDescription>
          </Alert>
          <Link href="/projects">
            <Button className="mt-4">Back to Projects</Button>
          </Link>
        </div>
      </div>
    )
  }

  const selectedUc = useCases.find((uc) => uc.id === selectedUcId)
  const selectedReadiness = selectedUcId ? readiness.get(selectedUcId) : null

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border/50 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="container flex h-14 items-center gap-3">
          <Link href="/projects">
            <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground -ml-2">
              <ArrowLeft className="mr-1.5 h-4 w-4" />
              Projects
            </Button>
          </Link>
          <div className="h-4 w-px bg-border/50" />
          <h1 className="font-semibold text-sm">{project.name}</h1>
        </div>
      </header>

      {/* Hero */}
      <div className="gradient-hero border-b border-border/50">
        <div className="container py-10">
          <h2 className="text-3xl font-bold tracking-tight gradient-text mb-1">{project.name}</h2>
          {project.description && (
            <p className="text-muted-foreground text-sm">{project.description}</p>
          )}
        </div>
      </div>

      <div className="container py-8 space-y-8">
        {/* Use-case selector + action row */}
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">Use case:</span>
            {useCases.length > 0 ? (
              <select
                className="bg-card border border-border/50 text-foreground text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-ring/50"
                value={selectedUcId || ""}
                onChange={(e) => setSelectedUcId(e.target.value)}
              >
                {useCases.map((uc) => (
                  <option key={uc.id} value={uc.id}>
                    {uc.name}
                  </option>
                ))}
              </select>
            ) : (
              <span className="text-sm text-muted-foreground">No use cases yet</span>
            )}
            <Badge variant="outline" className="text-xs text-muted-foreground border-border/50">
              {useCases.length} total
            </Badge>
          </div>

          <Button size="sm">
            <Plus className="mr-1.5 h-4 w-4" />
            New Use Case
          </Button>
        </div>

        {/* Pipeline visualization */}
        {selectedUc ? (
          <div className="space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground/60">
              Assessment Pipeline — {selectedUc.name}
            </h3>

            <div className="flex items-stretch gap-2">
              {STAGES.map((stage, idx) => {
                const status: ReadinessStatus = selectedReadiness?.[stage.id] || "not_ready"
                return (
                  <StagePipelineNode
                    key={stage.id}
                    stage={stage}
                    status={status}
                    isLast={idx === STAGES.length - 1}
                    href={`/projects/${projectId}/${stage.path}/${selectedUc.id}`}
                  />
                )
              })}
            </div>

            {/* Orchestrator agent feed */}
            {orchestratorSession && (
              <AgentActivityFeed
                useCaseId={selectedUc.id}
                sessionId={orchestratorSession}
              />
            )}
          </div>
        ) : (
          <EmptyState
            icon={<Users className="h-8 w-8" />}
            title="No use cases yet"
            description="Create your first use case to start the four-stage assessment pipeline."
            action={
              <Button size="sm">
                <Plus className="mr-1.5 h-4 w-4" />
                Create Use Case
              </Button>
            }
          />
        )}

        {/* All use cases summary list */}
        {useCases.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground/60">
              All Use Cases
            </h3>
            <div className="grid gap-2">
              {useCases.map((uc) => {
                const ucReadiness = readiness.get(uc.id)
                const stages = STAGES.map((s) => ucReadiness?.[s.id] || "not_ready")
                const completedCount = stages.filter((s) => s === "complete").length

                return (
                  <button
                    key={uc.id}
                    onClick={() => setSelectedUcId(uc.id)}
                    className={`w-full text-left glass-card rounded-lg px-4 py-3 border transition-all ${
                      selectedUcId === uc.id
                        ? "border-primary/50 glow-primary"
                        : "border-border/50 hover:border-border"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className="min-w-0">
                        <div className="text-sm font-medium truncate">{uc.name}</div>
                        {uc.description && (
                          <div className="text-xs text-muted-foreground truncate">{uc.description}</div>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        {STAGES.map((stage) => {
                          const status: ReadinessStatus = ucReadiness?.[stage.id] || "not_ready"
                          const cfg = STATUS_CONFIG[status]
                          return (
                            <div
                              key={stage.id}
                              title={`${stage.short}: ${cfg.label}`}
                              className={`h-2 w-2 rounded-full ${cfg.dotClass}`}
                            />
                          )
                        })}
                        <span className="text-xs text-muted-foreground ml-1">
                          {completedCount}/4
                        </span>
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

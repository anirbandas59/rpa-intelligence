"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { StageCard } from "@/components/shared/StageCard"
import { ArrowLeft, Plus, Loader2 } from "lucide-react"
import { apiGet, isAuthenticated } from "@/lib/api"
import type { Project, UseCase, ReadinessResponse } from "@/lib/types"

export default function ProjectDetailPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.id as string

  const [project, setProject] = useState<Project | null>(null)
  const [useCases, setUseCases] = useState<UseCase[]>([])
  const [readiness, setReadiness] = useState<Map<string, ReadinessResponse>>(new Map())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

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

        // Fetch readiness for each use case
        const readinessMap = new Map<string, ReadinessResponse>()
        await Promise.all(
          useCasesData.map(async (uc) => {
            try {
              const r = await apiGet<ReadinessResponse>(`/api/v1/use-cases/${uc.id}/readiness`)
              readinessMap.set(uc.id, r)
            } catch {
              // If readiness fails, skip
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
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  if (error || !project) {
    return (
      <div className="min-h-screen bg-muted/50">
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

  return (
    <div className="min-h-screen bg-muted/50">
      <div className="border-b bg-background">
        <div className="container flex h-16 items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/projects">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Projects
              </Button>
            </Link>
            <div className="h-6 w-px bg-border" />
            <h1 className="text-xl font-semibold">{project.name}</h1>
          </div>
        </div>
      </div>

      <div className="container py-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold">Use Cases</h2>
            {project.description && (
              <p className="text-muted-foreground mt-1">{project.description}</p>
            )}
          </div>
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New Use Case
          </Button>
        </div>

        {useCases.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-16 text-center">
              <h3 className="text-lg font-semibold mb-2">No use cases yet</h3>
              <p className="text-muted-foreground mb-4">
                Create your first use case to start the assessment process
              </p>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Create Use Case
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-8">
            {useCases.map((uc) => {
              const ucReadiness = readiness.get(uc.id)

              return (
                <div key={uc.id} className="space-y-4">
                  <Card>
                    <CardHeader>
                      <CardTitle>{uc.name}</CardTitle>
                      {uc.description && <CardDescription>{uc.description}</CardDescription>}
                    </CardHeader>
                  </Card>

                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                    <StageCard
                      stageId="s1"
                      title="Migration Assessment"
                      description="Evaluate migration feasibility and priority"
                      status={ucReadiness?.s1 || "not_ready"}
                      href={`/projects/${projectId}/stage1/${uc.id}`}
                    />
                    <StageCard
                      stageId="s2"
                      title="Complexity Analysis"
                      description="Extract complexity attributes and calculate effort"
                      status={ucReadiness?.s2 || "not_ready"}
                      href={`/projects/${projectId}/stage2/${uc.id}`}
                    />
                    <StageCard
                      stageId="s3"
                      title="Delivery Timeline"
                      description="Generate phase-based delivery timeline"
                      status={ucReadiness?.s3 || "not_ready"}
                      href={`/projects/${projectId}/stage3/${uc.id}`}
                    />
                    <StageCard
                      stageId="s4"
                      title="Sprint Tracker"
                      description="Feature decomposition and sprint planning"
                      status={ucReadiness?.s4 || "not_ready"}
                      href={`/projects/${projectId}/stage4/${uc.id}`}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

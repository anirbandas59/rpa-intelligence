"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { EmptyState } from "@/components/shared/EmptyState"
import { Plus, FolderOpen, Loader2, LogOut, Settings, Layers } from "lucide-react"
import { apiGet, isAuthenticated, clearAuthToken } from "@/lib/api"
import type { Project } from "@/lib/types"

export default function ProjectsPage() {
  const router = useRouter()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/auth/login")
      return
    }

    const fetchProjects = async () => {
      try {
        const data = await apiGet<Project[]>("/api/v1/projects")
        setProjects(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load projects")
      } finally {
        setLoading(false)
      }
    }

    fetchProjects()
  }, [router])

  const handleLogout = () => {
    clearAuthToken()
    router.push("/auth/login")
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Top nav */}
      <header className="border-b border-border/50 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="container flex h-14 items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-7 w-7 rounded-lg bg-primary/20 flex items-center justify-center">
              <Layers className="h-4 w-4 text-primary" />
            </div>
            <span className="font-semibold text-sm tracking-tight">RPA Intelligence</span>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/settings">
              <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground">
                <Settings className="h-4 w-4 mr-1.5" />
                Settings
              </Button>
            </Link>
            <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground" onClick={handleLogout}>
              <LogOut className="h-4 w-4 mr-1.5" />
              Sign out
            </Button>
          </div>
        </div>
      </header>

      {/* Hero band */}
      <div className="gradient-hero border-b border-border/50">
        <div className="container py-12">
          <div className="flex items-end justify-between gap-4">
            <div>
              <h1 className="text-4xl font-bold tracking-tight gradient-text mb-2">
                Projects
              </h1>
              <p className="text-muted-foreground max-w-md">
                Manage your RPA migration and complexity assessment projects across all four stages.
              </p>
            </div>
            <Link href="/projects/new">
              <Button className="glow-primary">
                <Plus className="mr-2 h-4 w-4" />
                New Project
              </Button>
            </Link>
          </div>

          {/* Stats row */}
          {projects.length > 0 && (
            <div className="mt-8 flex items-center gap-6 text-sm text-muted-foreground">
              <div>
                <span className="text-2xl font-bold text-foreground">{projects.length}</span>
                <span className="ml-2">project{projects.length !== 1 ? "s" : ""}</span>
              </div>
              <div className="h-4 w-px bg-border/50" />
              <div>
                <span className="text-2xl font-bold text-foreground">
                  {projects.reduce((sum, p) => sum + (p.use_cases?.length || 0), 0)}
                </span>
                <span className="ml-2">total use cases</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="container py-8">
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {projects.length === 0 ? (
          <EmptyState
            icon={<FolderOpen className="h-8 w-8" />}
            title="No projects yet"
            description="Get started by creating your first RPA assessment project."
            action={
              <Link href="/projects/new">
                <Button className="glow-primary">
                  <Plus className="mr-2 h-4 w-4" />
                  Create Project
                </Button>
              </Link>
            }
          />
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project) => {
              const useCaseCount = project.use_cases?.length || 0
              return (
                <Link key={project.id} href={`/projects/${project.id}`}>
                  <div className="group relative glass-card rounded-xl hover:glow-primary hover:-translate-y-0.5 transition-all duration-200 cursor-pointer overflow-hidden h-full flex">
                    {/* Left accent bar */}
                    <div className="w-1 shrink-0 bg-primary/60 rounded-l-xl" />

                    <div className="flex-1 p-5">
                      {/* Header row */}
                      <div className="flex items-start justify-between mb-3">
                        <h3 className="font-semibold text-base leading-snug group-hover:text-primary transition-colors line-clamp-2 pr-2">
                          {project.name}
                        </h3>
                        <Badge
                          variant="outline"
                          className="shrink-0 text-xs border-border/50 text-muted-foreground"
                        >
                          {useCaseCount} {useCaseCount === 1 ? "case" : "cases"}
                        </Badge>
                      </div>

                      {/* Description */}
                      {project.description && (
                        <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
                          {project.description}
                        </p>
                      )}

                      {/* Footer */}
                      <div className="mt-auto pt-3 border-t border-border/30">
                        <span className="text-xs text-muted-foreground/60">
                          Created {new Date(project.created_at).toLocaleDateString("en-US", {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })}
                        </span>
                      </div>
                    </div>
                  </div>
                </Link>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { EmptyState } from "@/components/shared/EmptyState"
import { Plus, FolderOpen, Loader2, LogOut, Settings, Layers } from "lucide-react"
import { apiGet, apiPost, isAuthenticated, clearAuthToken } from "@/lib/api"
import type { Project, CreateProjectRequest } from "@/lib/types"

function NewProjectSheet({ onCreated }: { onCreated: (project: Project) => void }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const reset = () => { setName(""); setDescription(""); setError("") }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      const project = await apiPost<Project>("/api/v1/projects", {
        name,
        description: description || undefined,
      } as CreateProjectRequest)
      reset()
      setOpen(false)
      onCreated(project)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={(v) => { setOpen(v); if (!v) reset() }}>
      <SheetTrigger render={<Button className="glow-primary" />}>
        <Plus className="mr-2 h-4 w-4" />
        New Project
      </SheetTrigger>
      <SheetContent className="w-full sm:max-w-md flex flex-col">
        <SheetHeader>
          <SheetTitle>New Project</SheetTitle>
          <SheetDescription>
            Create a new RPA migration and assessment project.
          </SheetDescription>
        </SheetHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5 mt-6 flex-1">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="space-y-2">
            <Label htmlFor="new-proj-name">Project Name</Label>
            <Input
              id="new-proj-name"
              placeholder="My RPA Migration Project"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              disabled={loading}
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="new-proj-desc">Description <span className="text-muted-foreground">(optional)</span></Label>
            <Input
              id="new-proj-desc"
              placeholder="Brief description of this project"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="flex gap-3 mt-auto pt-4 border-t border-border/50">
            <Button type="submit" disabled={loading || !name.trim()} className="flex-1">
              {loading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Creating…</> : "Create Project"}
            </Button>
            <Button type="button" variant="outline" disabled={loading} onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
        </form>
      </SheetContent>
    </Sheet>
  )
}

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

  const handleProjectCreated = (project: Project) => {
    router.push(`/projects/${project.id}`)
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
        <div className="flex h-14 items-center justify-between px-6">
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
        <div className="py-12 px-7">
          <div className="flex items-end justify-between gap-4">
            <div>
              <h1 className="text-4xl font-bold tracking-tight gradient-text mb-2">
                Projects
              </h1>
              <p className="text-muted-foreground max-w-md">
                Manage your RPA migration and complexity assessment projects across all four stages.
              </p>
            </div>
            <NewProjectSheet onCreated={handleProjectCreated} />
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
      <div className="py-6 px-7">
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
            action={<NewProjectSheet onCreated={handleProjectCreated} />}
          />
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project) => {
              const useCaseCount = project.use_cases?.length || 0
              return (
                <Link key={project.id} href={`/projects/${project.id}`}>
                  <div className="group relative glass-card rounded-xl hover:glow-primary hover:-translate-y-0.5 transition-all duration-200 cursor-pointer overflow-hidden h-full flex">
                    <div className="w-1 shrink-0 bg-primary/60 rounded-l-xl" />
                    <div className="flex-1 p-5">
                      <div className="flex items-start justify-between mb-3">
                        <h3 className="font-semibold text-base leading-snug group-hover:text-primary transition-colors line-clamp-2 pr-2">
                          {project.name}
                        </h3>
                        <Badge variant="outline" className="shrink-0 text-xs border-border/50 text-muted-foreground">
                          {useCaseCount} {useCaseCount === 1 ? "case" : "cases"}
                        </Badge>
                      </div>
                      {project.description && (
                        <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
                          {project.description}
                        </p>
                      )}
                      <div className="mt-auto pt-3 border-t border-border/30">
                        <span className="text-xs text-muted-foreground/60">
                          Created {new Date(project.created_at).toLocaleDateString("en-US", {
                            month: "short", day: "numeric", year: "numeric",
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

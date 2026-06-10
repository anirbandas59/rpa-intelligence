"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTrigger,
} from "@/components/ui/sheet";
import { EmptyState } from "@/components/shared/EmptyState";
import { Btn, Icon, SectionLabel } from "@/components/rpa";
import { spacing } from "@/lib/design-tokens";
import {
  Plus,
  FolderOpen,
  Loader2,
  LogOut,
  Settings,
  Diamond,
} from "lucide-react";
import { apiGet, apiPost, isAuthenticated, clearAuthToken } from "@/lib/api";
import type { Project, CreateProjectRequest } from "@/lib/types";
import Image from "next/image";

function NewProjectSheet({
  onCreated,
}: {
  onCreated: (project: Project) => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const reset = () => {
    setName("");
    setDescription("");
    setError("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const project = await apiPost<Project>("/api/v1/projects", {
        name,
        description: description || undefined,
      } as CreateProjectRequest);
      reset();
      setOpen(false);
      onCreated(project);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Sheet
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) reset();
      }}
    >
      <SheetTrigger render={<Button className="glow-primary" />}>
        <Plus className="mr-2 h-4 w-4" />
        New Project
      </SheetTrigger>
      <SheetContent className="w-full sm:max-w-md flex flex-col">
        <SheetHeader
          style={{
            marginTop: spacing.gapDefault,
            marginBottom: spacing.gapTight,
          }}
        >
          <SectionLabel>New Project</SectionLabel>
          <p
            style={{
              fontSize: 12.8,
              color: "var(--muted-foreground)",
              marginTop: 8,
            }}
          >
            Create a new RPA migration and assessment project.
          </p>
        </SheetHeader>
        <div style={{ padding: `0 ${spacing.cardDefault}px`, flex: 1 }}>
          <form
            onSubmit={handleSubmit}
            style={{
              display: "flex",
              flexDirection: "column",
              gap: spacing.gapDefault,
              height: "100%",
            }}
          >
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
              <Label htmlFor="new-proj-desc">
                Description{" "}
                <span className="text-muted-foreground">(optional)</span>
              </Label>
              <Input
                id="new-proj-desc"
                placeholder="Brief description of this project"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={loading}
              />
            </div>

            <div
              style={{
                display: "flex",
                gap: spacing.gapTight,
                marginTop: "auto",
                paddingTop: spacing.gapDefault,
                borderTop: "1px solid var(--border)",
              }}
            >
              <Btn
                type="button"
                variant="outline"
                disabled={loading}
                onClick={() => setOpen(false)}
                style={{ flex: 1 }}
              >
                Cancel
              </Btn>
              <Btn
                type="submit"
                disabled={loading || !name.trim()}
                style={{ flex: 1 }}
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating…
                  </>
                ) : (
                  "Create Project"
                )}
              </Btn>
            </div>
          </form>
        </div>
      </SheetContent>
    </Sheet>
  );
}

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/auth/login");
      return;
    }

    const fetchProjects = async () => {
      try {
        const data = await apiGet<Project[]>("/api/v1/projects");
        setProjects(data);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load projects",
        );
      } finally {
        setLoading(false);
      }
    };

    fetchProjects();
  }, [router]);

  const handleLogout = () => {
    clearAuthToken();
    router.push("/auth/login");
  };

  const handleProjectCreated = (project: Project) => {
    router.push(`/projects/${project.id}`);
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Top nav */}
      <header className="border-b border-border/50 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex h-14 items-center justify-between px-6">
          <div className="flex items-center gap-2.5">
            <Image
              alt="VectorIQ"
              src="/logo-small.png"
              width={480}
              height={80}
              loading="eager"
              className="h-5 w-auto group-data-[collapsible=icon]:hidden"
              style={{ width: "auto" }}
            />
            {/* <div className="h-7 w-7 rounded-lg bg-primary/20 flex items-center justify-center">
              <Layers className="h-4 w-4 text-primary" />
            </div> */}
            <span className="text-c-blue font-semibold text-xs uppercase tracking-widest">
              Assess
            </span>
            <Icon
              name="diamond"
              size={15}
              fill="url(#diamond-gradient)"
              className="drop-shadow-[0_0_8px_oklch(0.66_0.20_264/0.6)]"
            />
            <span className="text-c-amber font-semibold text-xs uppercase tracking-widest">
              Estimate
            </span>
            <Icon
              name="diamond"
              size={15}
              fill="url(#diamond-gradient)"
              className="drop-shadow-[0_0_8px_oklch(0.66_0.20_264/0.6)]"
            />
            <span className="text-c-green font-semibold text-xs uppercase tracking-widest">
              Execute
            </span>
            <svg width="0" height="0" style={{ position: "absolute" }}>
              <defs>
                <linearGradient
                  id="diamond-gradient"
                  x1="0%"
                  y1="0%"
                  x2="100%"
                  y2="100%"
                >
                  <stop
                    offset="0%"
                    style={{
                      stopColor: "oklch(0.86 0.12 264)",
                      stopOpacity: 1,
                    }}
                  />
                  <stop
                    offset="100%"
                    style={{
                      stopColor: "oklch(0.74 0.20 292)",
                      stopOpacity: 1,
                    }}
                  />
                </linearGradient>
              </defs>
            </svg>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/settings">
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-foreground"
              >
                <Settings className="h-4 w-4 mr-1.5" />
                Settings
              </Button>
            </Link>
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-foreground"
              onClick={handleLogout}
            >
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
                Manage your RPA migration and complexity assessment projects
                across all four stages.
              </p>
            </div>
            <NewProjectSheet onCreated={handleProjectCreated} />
          </div>

          {/* Stats row */}
          {projects.length > 0 && (
            <div className="mt-8 flex items-center gap-6 text-sm text-muted-foreground">
              <div>
                <span className="text-2xl font-bold text-foreground">
                  {projects.length}
                </span>
                <span className="ml-2">
                  project{projects.length !== 1 ? "s" : ""}
                </span>
              </div>
              <div className="h-4 w-px bg-border/50" />
              <div>
                <span className="text-2xl font-bold text-foreground">
                  {projects.reduce(
                    (sum, p) => sum + (p.use_case_count || 0),
                    0,
                  )}
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
              const useCaseCount = project.use_case_count || 0;
              return (
                <Link key={project.id} href={`/projects/${project.id}`}>
                  <div className="group relative glass-card rounded-xl hover:glow-primary hover:-translate-y-0.5 transition-all duration-200 cursor-pointer overflow-hidden h-full flex">
                    <div className="w-1 shrink-0 bg-primary/60 rounded-l-xl" />
                    <div className="flex-1 p-5">
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
                      {project.description && (
                        <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
                          {project.description}
                        </p>
                      )}
                      <div className="mt-auto pt-3 border-t border-border/30">
                        <span className="text-xs text-muted-foreground/60">
                          Created{" "}
                          {new Date(project.created_at).toLocaleDateString(
                            "en-US",
                            {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                            },
                          )}
                        </span>
                      </div>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

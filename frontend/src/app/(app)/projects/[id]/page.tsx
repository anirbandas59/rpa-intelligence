"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Sheet, SheetContent, SheetHeader } from "@/components/ui/sheet";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Btn, SectionLabel } from "@/components/rpa";
import { spacing } from "@/lib/design-tokens";
import { EmptyState } from "@/components/shared/EmptyState";
import { ComplexityChip } from "@/components/shared/ComplexityChip";
import { PriorityBadge, BAND_META } from "@/components/shared/PriorityBadge";
import { MiniSpark } from "@/components/shared/MiniSpark";
import { Icon } from "@/components/shared/icons";
import { ArrowLeft, Plus, Loader2, Users, ChevronDown, Upload, Edit3, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiGetRuns, apiPost, apiDelete, isAuthenticated } from "@/lib/api";
import { BulkUploadModal } from "@/components/BulkUploadModal";
import type {
  Project,
  UseCase,
  ReadinessResponse,
  ReadinessStatus,
  S3ReadinessDetail,
  Band,
  S1Result,
  S2Result,
  S3Result,
} from "@/lib/types";

function resolveStatus(
  r: ReadinessResponse | undefined | null,
  stageId: "s1" | "s2" | "s3" | "s4",
): ReadinessStatus {
  if (!r) return "not_ready";
  const val = r[stageId];
  if (stageId === "s3")
    return (val as S3ReadinessDetail)?.phase_calculator ?? "not_ready";
  return (val as ReadinessStatus) ?? "not_ready";
}

const STATUS_CONFIG: Record<
  ReadinessStatus,
  { label: string; dotClass: string; color: string }
> = {
  not_ready: {
    label: "Not Ready",
    dotClass: "bg-muted-foreground/40",
    color: "var(--muted-foreground)",
  },
  ready: { label: "Ready", dotClass: "bg-blue-400", color: "var(--c-blue)" },
  running: {
    label: "Running",
    dotClass: "bg-primary animate-pulse",
    color: "var(--primary)",
  },
  complete: {
    label: "Complete",
    dotClass: "bg-green-500",
    color: "var(--c-green)",
  },
  stale: { label: "Stale", dotClass: "bg-amber-500", color: "var(--c-amber)" },
  failed: { label: "Failed", dotClass: "bg-red-500", color: "var(--c-red)" },
};

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
  { id: "s4" as const, label: "Sprint Tracker", short: "S4", path: "stage4" },
];

/* Cached stage results per UC */
interface UCCache {
  s1?: S1Result;
  s2?: S2Result;
  s3?: S3Result;
}

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [project, setProject] = useState<Project | null>(null);
  const [useCases, setUseCases] = useState<UseCase[]>([]);
  const [readiness, setReadiness] = useState<Map<string, ReadinessResponse>>(
    new Map(),
  );
  const [ucCache, setUcCache] = useState<Map<string, UCCache>>(new Map());
  const [selectedUcId, setSelectedUcId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // const [orchestratorSession, setOrchestratorSession] = useState<string | null>(
  //   null,
  // );
  const [newUcOpen, setNewUcOpen] = useState(false);
  const [newUcName, setNewUcName] = useState("");
  const [newUcDesc, setNewUcDesc] = useState("");
  const [creatingUc, setCreatingUc] = useState(false);
  const [bulkUploadOpen, setBulkUploadOpen] = useState(false);
  const [activeView, setActiveView] = useState<"pipeline" | "portfolio">(
    "pipeline",
  );

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/auth/login");
      return;
    }

    const fetchData = async () => {
      try {
        const [projectData, useCasesData] = await Promise.all([
          apiGet<Project>(`/api/v1/projects/${projectId}`),
          apiGet<UseCase[]>(`/api/v1/projects/${projectId}/use-cases`),
        ]);
        setProject(projectData);
        setUseCases(useCasesData);
        if (useCasesData.length > 0) setSelectedUcId(useCasesData[0].id);

        const readinessMap = new Map<string, ReadinessResponse>();
        await Promise.all(
          useCasesData.map(async (uc) => {
            try {
              const r = await apiGet<ReadinessResponse>(
                `/api/v1/use-cases/${uc.id}/readiness`,
              );
              readinessMap.set(uc.id, r);
            } catch {
              /* skip */
            }
          }),
        );
        setReadiness(readinessMap);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load project");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [projectId, router]);

  /* Lazily resolve stage results for hero stats */
  useEffect(() => {
    if (useCases.length === 0) return;

    // Proper async handling with Promise.all instead of forEach
    const loadCaches = async () => {
      const cacheEntries = await Promise.all(
        useCases.map(async (uc) => {
          const cache: UCCache = {};
          try {
            if (uc.s1_latest_run_id) {
              const runs = await apiGetRuns<{
                id: string;
                status: string;
                result: unknown;
              }>(`/api/v1/use-cases/${uc.id}/s1/runs`);
              const lr = runs.find(
                (r) => r.id === uc.s1_latest_run_id && r.status === "complete",
              );
              if (lr) cache.s1 = lr.result as S1Result;
            }
            if (uc.s2_latest_run_id) {
              const runs = await apiGetRuns<{
                id: string;
                status: string;
                result: unknown;
              }>(`/api/v1/use-cases/${uc.id}/s2/runs`);
              const lr = runs.find(
                (r) => r.id === uc.s2_latest_run_id && r.status === "complete",
              );
              if (lr) cache.s2 = lr.result as S2Result;
            }
            if (uc.s3_latest_run_id) {
              // S3 list returns summary only — fetch full result directly
              const fullRun = await apiGet<{
                id: string;
                status: string;
                result: S3Result;
              }>(`/api/v1/use-cases/${uc.id}/s3/runs/${uc.s3_latest_run_id}`);
              if (fullRun.status === "complete") cache.s3 = fullRun.result;
            }
          } catch {
            /* silent */
          }
          return [uc.id, cache] as const;
        }),
      );

      setUcCache(new Map(cacheEntries));
    };

    loadCaches();
  }, [useCases]);

  const handleCreateUc = async () => {
    if (!newUcName.trim()) {
      toast.error("Name is required");
      return;
    }
    setCreatingUc(true);
    try {
      await apiPost(`/api/v1/use-cases`, {
        name: newUcName,
        description: newUcDesc,
        project_id: projectId,
      });
      toast.success("Use case created");
      setNewUcOpen(false);
      setNewUcName("");
      setNewUcDesc("");
      // Reload page to fetch updated data
      window.location.reload();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to create use case",
      );
    } finally {
      setCreatingUc(false);
    }
  };

  const handleDeleteProject = async () => {
    try {
      await apiDelete(`/api/v1/projects/${projectId}`);
      toast.success("Project deleted");
      router.push("/projects");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to delete project",
      );
    }
  };

  const handleDeleteUseCase = async (useCaseId: string) => {
    try {
      await apiDelete(`/api/v1/use-cases/${useCaseId}`);
      toast.success("Use case deleted");
      // Reload page to fetch updated data
      window.location.reload();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to delete use case",
      );
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="min-h-screen bg-background">
        <div className="py-6 px-7">
          <Alert variant="destructive">
            <AlertDescription>{error || "Project not found"}</AlertDescription>
          </Alert>
          <Link href="/projects">
            <Button className="mt-4">Back to Projects</Button>
          </Link>
        </div>
      </div>
    );
  }

  const selectedUc = useCases.find((uc) => uc.id === selectedUcId);
  const selectedReadiness = selectedUcId ? readiness.get(selectedUcId) : null;

  /* Hero stats */
  const quickWins = useCases.filter((uc) => {
    const c = ucCache.get(uc.id);
    return c?.s1?.migration_decision === "QUICK_WIN";
  }).length;
  const totalBuildWeeks = useCases.reduce((sum, uc) => {
    const phases = ucCache.get(uc.id)?.s3?.phases || [];
    const buildPhase = phases.find((p) =>
      p.name.toLowerCase().includes("build"),
    );
    return sum + (buildPhase?.weeks || 0);
  }, 0);
  const totalFeatures = useCases.reduce((sum, uc) => {
    return sum + 0; // s4 features not cached — placeholder
  }, 0);

  return (
    <div className="min-h-screen bg-background">
      {/* ── Header ── */}
      <header className="border-b border-border/50 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex h-14 items-center gap-3 px-6">
          <Link href="/projects">
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-foreground -ml-2"
            >
              <ArrowLeft className="mr-1.5 h-4 w-4" />
              Projects
            </Button>
          </Link>
          <div className="h-4 w-px bg-border/50" />
          <h1 className="font-semibold text-sm">{project.name}</h1>
        </div>
      </header>

      <div
        style={{
          height: "calc(100vh - 3.5rem)",
          overflow: "hidden",
          padding: "26px 30px",
          display: "flex",
          flexDirection: "column",
          gap: 22,
        }}
      >
        {/* ── Hero ── */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div>
              <h1
                className="rpa-gradient-text"
                style={{
                  fontSize: 30,
                  fontWeight: 700,
                  letterSpacing: -0.6,
                  margin: 0,
                }}
              >
                {project.name}
              </h1>
              <p
                style={{
                  fontSize: 13.5,
                  color: "var(--muted-fg)",
                  margin: "6px 0 0",
                }}
              >
                {project.description || "Four-stage delivery intelligence"} ·{" "}
                {useCases.length} use case{useCases.length !== 1 ? "s" : ""} ·{" "}
                {quickWins} quick win{quickWins !== 1 ? "s" : ""} identified
              </p>
            </div>
            <AlertDialog>
              <AlertDialogTrigger
                render={
                  <button className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors hover:bg-accent hover:text-destructive h-9 px-3 text-muted-foreground">
                    <Trash2 className="h-4 w-4" />
                  </button>
                }
              />
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete project?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will permanently delete "{project.name}" and all {useCases.length} use case{useCases.length !== 1 ? "s" : ""}. This action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={handleDeleteProject}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    Delete
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
          <div style={{ display: "flex", gap: 26 }}>
            {[
              { n: useCases.length, l: "use cases" },
              { n: quickWins, l: "quick wins" },
              { n: totalBuildWeeks || "—", l: "build weeks" },
              { n: totalFeatures || "—", l: "features" },
            ].map(({ n, l }) => (
              <div key={l}>
                <div
                  style={{
                    fontFamily: "var(--mono)",
                    fontSize: 24,
                    fontWeight: 700,
                  }}
                >
                  {n}
                </div>
                <div style={{ fontSize: 11, color: "var(--muted-fg)" }}>
                  {l}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── View toggle + actions ── */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div
            style={{
              display: "flex",
              gap: 1,
              borderRadius: 9,
              border: "1px solid var(--border)",
              padding: 3,
            }}
          >
            {(["pipeline", "portfolio"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setActiveView(v)}
                style={{
                  padding: "5px 14px",
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                  background:
                    activeView === v
                      ? "color-mix(in oklab, var(--primary) 16%, transparent)"
                      : "transparent",
                  color:
                    activeView === v ? "var(--primary)" : "var(--muted-fg)",
                  border: "none",
                  transition: "all 0.12s",
                }}
              >
                {v === "pipeline" ? "Pipeline" : "Portfolio map"}
              </button>
            ))}
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Btn size="sm">
                <Plus className="mr-1.5 h-4 w-4" />
                Add Use Cases
                <ChevronDown className="ml-1.5 h-3 w-3" />
              </Btn>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => setNewUcOpen(true)}>
                <Edit3 className="mr-2 h-4 w-4" />
                Single Entry
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setBulkUploadOpen(true)}>
                <Upload className="mr-2 h-4 w-4" />
                Bulk Upload (CSV/XLSX)
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* ══ PIPELINE VIEW (HubRail pattern) ══════════════════════════ */}
        {activeView === "pipeline" && selectedUc && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 18,
              flex: 1,
              minHeight: 0,
            }}
          >
            <div>
              <SectionLabel style={{ marginBottom: 12 }}>
                Assessment pipeline · {selectedUc.name}
              </SectionLabel>
              <div style={{ display: "flex", alignItems: "stretch", gap: 0 }}>
                {STAGES.map((stage, idx) => {
                  const status: ReadinessStatus = resolveStatus(
                    selectedReadiness,
                    stage.id,
                  );
                  const cfg = STATUS_CONFIG[status];
                  const cache = ucCache.get(selectedUcId || "");
                  const href = `/projects/${projectId}/${stage.path}/${selectedUc.id}`;
                  const stageIcons: Record<
                    string,
                    "target" | "grid" | "calendar" | "layers"
                  > = {
                    s1: "target",
                    s2: "grid",
                    s3: "calendar",
                    s4: "layers",
                  };

                  return (
                    <React.Fragment key={stage.id}>
                      <div
                        className="rpa-card-hover"
                        style={{
                          flex: 1,
                          borderRadius: 14,
                          padding: 16,
                          background: "var(--surface)",
                          border: `1px solid ${status === "running" ? "color-mix(in oklab, var(--primary) 40%, transparent)" : "var(--border)"}`,
                          position: "relative",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            marginBottom: 14,
                          }}
                        >
                          <span
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 8,
                            }}
                          >
                            <span
                              style={{
                                fontFamily: "var(--mono)",
                                fontSize: 10.5,
                                fontWeight: 700,
                                color: "var(--primary)",
                                border:
                                  "1px solid color-mix(in oklab, var(--primary) 30%, transparent)",
                                borderRadius: 5,
                                padding: "2px 5px",
                              }}
                            >
                              {stage.short}
                            </span>
                            <Icon
                              name={stageIcons[stage.id]}
                              size={15}
                              style={{ color: "var(--muted-fg)" }}
                            />
                          </span>
                          <span
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 5,
                              fontSize: 11,
                              color: cfg.color,
                            }}
                          >
                            <span
                              style={{
                                width: 7,
                                height: 7,
                                borderRadius: 99,
                                background: cfg.color,
                                ...(status === "running"
                                  ? {
                                      animation:
                                        "rpaPulse 1.6s ease-in-out infinite",
                                    }
                                  : {}),
                              }}
                            />
                            {cfg.label}
                          </span>
                        </div>
                        <div
                          style={{
                            fontSize: 13.5,
                            fontWeight: 600,
                            marginBottom: 14,
                            lineHeight: 1.25,
                          }}
                        >
                          {stage.label}
                        </div>

                        {/* NodeViz - stage-specific mini visualization */}
                        <div
                          style={{
                            minHeight: 38,
                            display: "flex",
                            alignItems: "center",
                            gap: 10,
                          }}
                        >
                          {stage.id === "s1" && cache?.s1 ? (
                            <>
                              <div
                                style={{
                                  fontFamily: "var(--mono)",
                                  fontSize: 26,
                                  fontWeight: 700,
                                  color:
                                    BAND_META[cache.s1.migration_decision]
                                      ?.color || "var(--primary)",
                                }}
                              >
                                {cache.s1.total_score}
                              </div>
                              <PriorityBadge
                                band={cache.s1.migration_decision}
                              />
                            </>
                          ) : stage.id === "s2" && cache?.s2 ? (
                            <>
                              <ComplexityChip
                                cls={cache.s2.complexity_class as Band}
                                size={30}
                              />
                              <div
                                style={{ fontSize: 12, color: "var(--fg-2)" }}
                              >
                                {cache.s2.effort_min_weeks ===
                                cache.s2.effort_max_weeks
                                  ? `${cache.s2.effort_min_weeks}w`
                                  : `${cache.s2.effort_min_weeks}–${cache.s2.effort_max_weeks}w`}
                              </div>
                            </>
                          ) : stage.id === "s3" && cache?.s3 ? (
                            <>
                              <MiniSpark
                                values={cache.s3.phases.map((p) => p.weeks)}
                                color="var(--primary)"
                                w={70}
                                h={22}
                              />
                              <span
                                style={{ fontSize: 11.5, color: "var(--fg-2)" }}
                              >
                                ~
                                {cache.s3.phases.reduce(
                                  (s, p) => s + p.weeks,
                                  0,
                                )}{" "}
                                wks
                              </span>
                            </>
                          ) : stage.id === "s4" && status === "complete" ? (
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 6,
                              }}
                            >
                              {/* Placeholder: sprint count visualization */}
                              <span
                                style={{ fontSize: 11.5, color: "var(--fg-2)" }}
                              >
                                Sprint plan ready
                              </span>
                            </div>
                          ) : (
                            <span
                              style={{ fontSize: 11, color: "var(--muted-fg)" }}
                            >
                              {status === "not_ready"
                                ? "Not ready"
                                : "No data yet"}
                            </span>
                          )}
                        </div>

                        <Link href={href}>
                          <Btn
                            variant={
                              status === "not_ready" ? "outline" : "subtle"
                            }
                            size="sm"
                            iconR="arrowR"
                            style={{ width: "100%", marginTop: 14 }}
                          >
                            {status === "running" ? "View progress" : "Open"}
                          </Btn>
                        </Link>
                      </div>
                      {idx < STAGES.length - 1 && (
                        <div
                          style={{
                            width: 28,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color: "var(--muted-fg)",
                          }}
                        >
                          <Icon
                            name="chevR"
                            size={16}
                            style={{ opacity: 0.5 }}
                          />
                        </div>
                      )}
                    </React.Fragment>
                  );
                })}
              </div>
            </div>

            {/* Portfolio table */}
            <div
              style={{
                flex: 1,
                minHeight: 0,
                display: "flex",
                flexDirection: "column",
              }}
            >
              <SectionLabel style={{ marginBottom: 10 }}>
                All use cases
              </SectionLabel>
              <div
                style={{
                  borderRadius: 13,
                  border: "1px solid var(--border)",
                  overflow: "auto",
                  background: "var(--surface)",
                  flex: 1,
                  position: "relative",
                }}
              >
                <div
                  style={{
                    position: "sticky",
                    top: 0,
                    zIndex: 10,
                    display: "grid",
                    gridTemplateColumns: "1.9fr 0.9fr 0.7fr 1fr 0.9fr",
                    gap: 0,
                    padding: "9px 16px",
                    fontSize: 10.5,
                    fontWeight: 700,
                    letterSpacing: 0.6,
                    color: "var(--muted-fg)",
                    textTransform: "uppercase",
                    borderBottom: "1px solid var(--border)",
                    background: "var(--surface)",
                  }}
                >
                  <span>Use case</span>
                  <span>Priority</span>
                  <span>Complexity</span>
                  <span>Pipeline</span>
                  <span style={{ textAlign: "right" }}>Progress</span>
                </div>
                {useCases.map((u, idx) => {
                  const ucReadiness = readiness.get(u.id);
                  const stages = STAGES.map((s) =>
                    resolveStatus(ucReadiness, s.id),
                  );
                  const done = stages.filter((s) => s === "complete").length;
                  const cache = ucCache.get(u.id);
                  const isHighlighted = u.id === selectedUcId;

                  return (
                    <div
                      key={u.id}
                      className="group"
                      style={{
                        width: "100%",
                        display: "grid",
                        gridTemplateColumns: "1.9fr 0.9fr 0.7fr 1fr 0.9fr auto",
                        gap: 0,
                        padding: "12px 16px",
                        alignItems: "center",
                        borderBottom:
                          idx < useCases.length - 1
                            ? "1px solid var(--border)"
                            : "none",
                        background: isHighlighted
                          ? "color-mix(in oklab, var(--primary) 6%, transparent)"
                          : "transparent",
                        transition: "background 0.12s",
                      }}
                    >
                      <button
                        onClick={() => setSelectedUcId(u.id)}
                        style={{
                          all: "unset",
                          cursor: "pointer",
                          gridColumn: "1 / 6",
                          display: "grid",
                          gridTemplateColumns: "subgrid",
                          width: "100%",
                        }}
                      >
                      <div style={{ minWidth: 0, paddingRight: 12 }}>
                        <div
                          style={{
                            fontSize: 13,
                            fontWeight: 600,
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                          }}
                        >
                          {u.name}
                        </div>
                        <div
                          style={{
                            fontSize: 11,
                            color: "var(--muted-fg)",
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                          }}
                        >
                          {u.description || "No description"}
                        </div>
                      </div>
                      <div>
                        {cache?.s1 ? (
                          <PriorityBadge band={cache.s1.migration_decision} />
                        ) : (
                          <span
                            style={{ fontSize: 11, color: "var(--muted-fg)" }}
                          >
                            —
                          </span>
                        )}
                      </div>
                      <div>
                        {cache?.s2 ? (
                          <ComplexityChip
                            cls={cache.s2.complexity_class as Band}
                            size={26}
                          />
                        ) : (
                          <span
                            style={{ fontSize: 11, color: "var(--muted-fg)" }}
                          >
                            —
                          </span>
                        )}
                      </div>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 5,
                        }}
                      >
                        {STAGES.map((stage) => {
                          const status: ReadinessStatus = resolveStatus(
                            ucReadiness,
                            stage.id,
                          );
                          const cfg = STATUS_CONFIG[status];
                          return (
                            <span
                              key={stage.id}
                              title={`${stage.short}: ${cfg.label}`}
                              style={{
                                width: 7,
                                height: 7,
                                borderRadius: 99,
                                background: cfg.color,
                                display: "inline-block",
                              }}
                            />
                          );
                        })}
                      </div>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "flex-end",
                            gap: 8,
                          }}
                        >
                          <div
                            style={{
                              width: 52,
                              height: 5,
                              borderRadius: 99,
                              background: "var(--track)",
                              overflow: "hidden",
                            }}
                          >
                            <div
                              style={{
                                width: `${(done / 4) * 100}%`,
                                height: "100%",
                                background: "var(--c-green)",
                              }}
                            />
                          </div>
                          <span
                            style={{
                              fontFamily: "var(--mono)",
                              fontSize: 11,
                              color: "var(--muted-fg)",
                            }}
                          >
                            {done}/4
                          </span>
                        </div>
                      </button>
                      <AlertDialog>
                        <AlertDialogTrigger
                          render={
                            <button
                              className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors hover:bg-accent opacity-0 group-hover:opacity-100 h-9 px-3"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" />
                            </button>
                          }
                        />
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Delete use case?</AlertDialogTitle>
                            <AlertDialogDescription>
                              This will permanently delete "{u.name}". This action cannot be undone.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => handleDeleteUseCase(u.id)}
                              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            >
                              Delete
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {!selectedUc && activeView === "pipeline" && (
          <EmptyState
            icon={<Users className="h-8 w-8" />}
            title="No use cases yet"
            description="Create your first use case to start the four-stage assessment pipeline."
            action={
              <Button size="sm" onClick={() => setNewUcOpen(true)}>
                <Plus className="mr-1.5 h-4 w-4" />
                Create Use Case
              </Button>
            }
          />
        )}

        {/* ══ PORTFOLIO MAP (HubMatrix pattern) ══════════════════════ */}
        {activeView === "portfolio" && (
          <div
            style={{
              flex: 1,
              display: "grid",
              gridTemplateColumns: "1.55fr 1fr",
              gap: 22,
              minHeight: 0,
            }}
          >
            {/* Matrix */}
            <div
              style={{
                borderRadius: 14,
                border: "1px solid var(--border)",
                background: "var(--surface)",
                padding: "20px 22px 16px 50px",
                position: "relative",
                display: "flex",
                flexDirection: "column",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  left: 14,
                  top: "50%",
                  transform: "rotate(-90deg) translateX(50%)",
                  transformOrigin: "left center",
                  fontSize: 10.5,
                  fontWeight: 700,
                  letterSpacing: 1,
                  color: "var(--muted-fg)",
                  whiteSpace: "nowrap",
                }}
              >
                MIGRATION SCORE →
              </div>
              <div
                style={{
                  flex: 1,
                  position: "relative",
                  borderLeft: "1px solid var(--border)",
                  borderBottom: "1px solid var(--border)",
                  margin: "4px 4px 22px 4px",
                }}
              >
                {/* Quick win zone tint */}
                <div
                  style={{
                    position: "absolute",
                    left: 0,
                    top: 0,
                    width: "45%",
                    height: "42%",
                    background:
                      "color-mix(in oklab, var(--c-green) 8%, transparent)",
                    borderRight: "1px dashed var(--border)",
                    borderBottom: "1px dashed var(--border)",
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    left: 8,
                    top: 8,
                    fontSize: 10,
                    fontWeight: 700,
                    color: "var(--c-green)",
                    letterSpacing: 0.5,
                    opacity: 0.8,
                  }}
                >
                  QUICK WINS
                </div>
                {/* Gridlines */}
                {[0.25, 0.5, 0.75].map((g) => (
                  <div
                    key={g}
                    style={{
                      position: "absolute",
                      left: 0,
                      right: 0,
                      top: `${g * 100}%`,
                      borderTop:
                        "1px dashed color-mix(in oklab, var(--border) 60%, transparent)",
                    }}
                  />
                ))}
                {/* Bubbles */}
                {useCases.filter((uc) => {
                  const cache = ucCache.get(uc.id);
                  return cache?.s1; // Only S1 required, S2 optional
                }).length === 0 && (
                  <div
                    style={{
                      position: "absolute",
                      top: "50%",
                      left: "50%",
                      transform: "translate(-50%, -50%)",
                      textAlign: "center",
                      color: "var(--muted-fg)",
                      maxWidth: 280,
                    }}
                  >
                    <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                      Run Stage 1 assessments to populate map
                    </div>
                    <div style={{ fontSize: 11.5 }}>
                      Complete Stage 1 (Migration Assessment) for use cases to see them plotted. Stage 2 (Complexity) provides better positioning but is optional.
                    </div>
                  </div>
                )}
                {useCases.map((uc) => {
                  const cache = ucCache.get(uc.id);
                  if (!cache?.s1) return null; // Only S1 required

                  // S2 provides better X-axis positioning, fallback to center if missing
                  const complexityMap: Record<string, number> = {
                    XS: 0,
                    S: 1,
                    M: 2,
                    L: 3,
                    XL: 4,
                  };
                  const hasS2 = !!cache.s2;
                  const x = hasS2 && cache.s2
                    ? (complexityMap[cache.s2.complexity_class] / 4) * 88 + 4
                    : 50; // Center if no S2
                  const y = (1 - cache.s1.total_score / 100) * 86 + 2;
                  const wk = cache.s2?.effort_max_weeks || 5; // Default 5 weeks
                  const sz = 26 + wk * 3;
                  const c =
                    BAND_META[cache.s1.migration_decision]?.color ||
                    "var(--primary)";
                  return (
                    <div
                      key={uc.id}
                      title={uc.name}
                      style={{
                        position: "absolute",
                        left: `${x}%`,
                        top: `${y}%`,
                        transform: "translate(-50%,-50%)",
                      }}
                    >
                      <div
                        style={{
                          width: sz,
                          height: sz,
                          borderRadius: 99,
                          background: `color-mix(in oklab, ${c} 24%, transparent)`,
                          border: `1.5px solid ${c}`,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontFamily: "var(--mono)",
                          fontSize: 11,
                          fontWeight: 700,
                          color: c,
                          boxShadow: `0 0 14px color-mix(in oklab, ${c} 30%, transparent)`,
                        }}
                      >
                        {cache.s1.total_score}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  paddingLeft: 4,
                  fontSize: 10.5,
                  fontWeight: 700,
                  letterSpacing: 1,
                  color: "var(--muted-fg)",
                }}
              >
                <span>COMPLEXITY →</span>
                <span style={{ display: "flex", gap: 30 }}>
                  {["XS", "S", "M", "L", "XL"].map((c) => (
                    <span key={c}>{c}</span>
                  ))}
                </span>
              </div>
            </div>

            {/* Ranked recommendations */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 12,
                minHeight: 0,
              }}
            >
              <SectionLabel>Recommended sequence</SectionLabel>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 9,
                  overflow: "auto",
                }}
              >
                {[...useCases]
                  .filter((u) => ucCache.get(u.id)?.s1)
                  .sort((a, b) => {
                    const aScore = ucCache.get(a.id)?.s1?.total_score || 0;
                    const bScore = ucCache.get(b.id)?.s1?.total_score || 0;
                    return bScore - aScore;
                  })
                  .map((u, i) => {
                    const cache = ucCache.get(u.id);
                    const ucReadiness = readiness.get(u.id);
                    const stages = STAGES.map((s) =>
                      resolveStatus(ucReadiness, s.id),
                    );
                    return (
                      <div
                        key={u.id}
                        className="rpa-card-hover"
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 12,
                          padding: "11px 13px",
                          borderRadius: 11,
                          background: "var(--surface)",
                          border: "1px solid var(--border)",
                        }}
                      >
                        <span
                          style={{
                            fontFamily: "var(--mono)",
                            fontSize: 15,
                            fontWeight: 700,
                            color: "var(--muted-fg)",
                            width: 20,
                          }}
                        >
                          {i + 1}
                        </span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div
                            style={{
                              fontSize: 12.5,
                              fontWeight: 600,
                              whiteSpace: "nowrap",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                            }}
                          >
                            {u.name}
                          </div>
                          <div
                            style={{ display: "flex", gap: 6, marginTop: 4 }}
                          >
                            {cache?.s1 && (
                              <PriorityBadge
                                band={cache.s1.migration_decision}
                              />
                            )}
                            {cache?.s2 && (
                              <ComplexityChip
                                cls={cache.s2.complexity_class as Band}
                                size={20}
                              />
                            )}
                          </div>
                        </div>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 5,
                          }}
                        >
                          {STAGES.map((stage) => {
                            const status: ReadinessStatus = resolveStatus(
                              ucReadiness,
                              stage.id,
                            );
                            const cfg = STATUS_CONFIG[status];
                            return (
                              <span
                                key={stage.id}
                                title={`${stage.short}: ${cfg.label}`}
                                style={{
                                  width: 7,
                                  height: 7,
                                  borderRadius: 99,
                                  background: cfg.color,
                                  display: "inline-block",
                                }}
                              />
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          </div>
        )}

        {/* ── All use cases list ── */}
        {/* {useCases.length > 0 && ( */}

        {/* )} */}
      </div>

      {/* ── New Use Case Sheet ── */}
      <Sheet open={newUcOpen} onOpenChange={setNewUcOpen}>
        <SheetContent
          className="w-110"
          style={{ padding: spacing.cardDefault }}
        >
          <SheetHeader style={{ marginBottom: spacing.gapDefault }}>
            <SectionLabel>New Use Case</SectionLabel>
            <p
              style={{
                fontSize: 12.8,
                color: "var(--muted-foreground)",
                marginTop: 8,
              }}
            >
              Add a use case to this project. You can run all four stages
              independently after creation.
            </p>
          </SheetHeader>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleCreateUc();
            }}
            style={{
              display: "flex",
              flexDirection: "column",
              gap: spacing.gapDefault,
            }}
          >
            <div className="space-y-2">
              <Label>
                Name <span className="text-destructive">*</span>
              </Label>
              <Input
                placeholder="e.g., Invoice processing automation"
                value={newUcName}
                onChange={(e) => setNewUcName(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea
                placeholder="Brief description of the RPA use case…"
                value={newUcDesc}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                  setNewUcDesc(e.target.value)
                }
                rows={3}
              />
            </div>
            <div
              style={{
                display: "flex",
                gap: spacing.gapTight,
                paddingTop: spacing.gapTight,
              }}
            >
              <Btn
                type="button"
                variant="outline"
                style={{ flex: 1 }}
                onClick={() => setNewUcOpen(false)}
              >
                Cancel
              </Btn>
              <Btn
                type="submit"
                style={{ flex: 1 }}
                disabled={creatingUc || !newUcName.trim()}
              >
                {creatingUc ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Creating
                  </>
                ) : (
                  <>
                    <Plus className="h-4 w-4 mr-2" />
                    Create
                  </>
                )}
              </Btn>
            </div>
          </form>
        </SheetContent>
      </Sheet>

      {/* Bulk Upload Modal */}
      <BulkUploadModal
        projectId={projectId}
        open={bulkUploadOpen}
        onOpenChange={setBulkUploadOpen}
      />
    </div>
  );
}

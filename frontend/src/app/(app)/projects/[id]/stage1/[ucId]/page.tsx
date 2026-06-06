"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { AsyncRunProgress } from "@/components/shared/AsyncRunProgress";
import { RunHistoryDrawer } from "@/components/shared/RunHistoryDrawer";
import { StalenessIndicator } from "@/components/shared/StalenessIndicator";
import { InputSourceBadge } from "@/components/shared/InputSourceBadge";
import { Gauge } from "@/components/shared/Gauge";
import { DimBar } from "@/components/shared/DimBar";
import { RadialDim } from "@/components/shared/RadialDim";
import { PriorityBadge, BAND_META } from "@/components/shared/PriorityBadge";
import { Icon } from "@/components/shared/icons";
import {
  ArrowLeft,
  Loader2,
  Play,
  RefreshCw,
  BarChart3,
  LayoutList,
} from "lucide-react";
import { toast } from "sonner";
import {
  apiGet,
  apiGetRuns,
  apiPost,
  apiPatch,
  isAuthenticated,
} from "@/lib/api";
import type {
  UseCase,
  StageRun,
  S1Result,
  ReadinessResponse,
  MigrationDecision,
  Confidence,
} from "@/lib/types";

const CONF_COLOR: Record<Confidence, string> = {
  HIGH: "var(--c-green)",
  MEDIUM: "var(--c-amber)",
  LOW: "var(--c-red)",
};

const S1_DIMS = [
  {
    key: "technical_feasibility" as const,
    label: "Technical feasibility",
    max: 40,
    color: "var(--c-blue)",
  },
  {
    key: "migration_effort" as const,
    label: "Migration effort",
    max: 25,
    color: "var(--c-teal)",
  },
  {
    key: "platform_suitability" as const,
    label: "Platform suitability",
    max: 20,
    color: "var(--primary)",
  },
  {
    key: "risk" as const,
    label: "Risk (inverse)",
    max: 15,
    color: "var(--c-amber)",
  },
];

type ViewMode = "scorecard" | "portfolio";

/* ── Portfolio row (per-use-case) ──────────────────────────── */
interface PortfolioRow {
  uc: UseCase;
  result: S1Result | null;
  status: string;
}

export default function Stage1Page() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const ucId = params.ucId as string;

  const [useCase, setUseCase] = useState<UseCase | null>(null);
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [runs, setRuns] = useState<StageRun[]>([]);
  const [latestResult, setLatestResult] = useState<S1Result | null>(null);
  const [loading, setLoading] = useState(true);
  const [runningStage, setRunningStage] = useState(false);
  const [error, setError] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("scorecard");
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");
  const [overrideDims, setOverrideDims] = useState<Record<string, number>>({});
  const [portfolioRows, setPortfolioRows] = useState<PortfolioRow[]>([]);
  const [portfolioLoading, setPortfolioLoading] = useState(false);
  const [scoringAll, setScoringAll] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [ucData, readinessData, runsData] = await Promise.all([
        apiGet<UseCase>(`/api/v1/use-cases/${ucId}`),
        apiGet<ReadinessResponse>(`/api/v1/use-cases/${ucId}/readiness`),
        apiGetRuns<StageRun>(`/api/v1/stage1/${ucId}/s1/runs`).catch(
          () => [] as StageRun[],
        ),
      ]);
      setUseCase(ucData);
      setReadiness(readinessData);
      setRuns(runsData);

      if (ucData.s1_latest_run_id && runsData.length > 0) {
        const latestRun = runsData.find(
          (r) => r.id === ucData.s1_latest_run_id,
        );
        if (latestRun?.status === "complete") {
          setLatestResult(latestRun.result as unknown as S1Result);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [ucId]);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/auth/login");
      return;
    }
    fetchData();
  }, [fetchData, router]);

  /* portfolio: fetch all UCs + their s1 runs */
  const loadPortfolio = useCallback(async () => {
    setPortfolioLoading(true);
    try {
      const allUcs = await apiGet<UseCase[]>(
        `/api/v1/projects/${projectId}/use-cases`,
      );
      const rows: PortfolioRow[] = await Promise.all(
        allUcs.map(async (u) => {
          if (!u.s1_latest_run_id)
            return { uc: u, result: null, status: "not_ready" };
          try {
            const ucRuns = await apiGetRuns<StageRun>(
              `/api/v1/stage1/${u.id}/s1/runs`,
            );
            const latest = ucRuns.find((r) => r.id === u.s1_latest_run_id);
            if (latest?.status === "complete") {
              return {
                uc: u,
                result: latest.result as unknown as S1Result,
                status: "complete",
              };
            }
            return {
              uc: u,
              result: null,
              status: latest?.status || "not_ready",
            };
          } catch {
            return { uc: u, result: null, status: "not_ready" };
          }
        }),
      );
      setPortfolioRows(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load portfolio");
    } finally {
      setPortfolioLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (viewMode === "portfolio") loadPortfolio();
  }, [viewMode, loadPortfolio]);

  const handleRun = async () => {
    setRunningStage(true);
    setError("");
    try {
      await apiPost(`/api/v1/stage1/${ucId}/s1/runs`, {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run");
      setRunningStage(false);
    }
  };

  const handleRunComplete = () => {
    setRunningStage(false);
    window.location.reload();
  };

  const handleBackfill = async () => {
    try {
      await apiPost(`/api/v1/stage1/${ucId}/s1/backfill-from-s2`, {});
      toast.success(
        "Backfill complete — re-run assessment to see updated inputs",
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Backfill failed");
    }
  };

  const handleOverrideSave = async () => {
    if (!overrideReason.trim()) {
      toast.error("Reason is required");
      return;
    }
    try {
      await apiPost(`/api/v1/stage1/${ucId}/s1/override`, {
        ...overrideDims,
        reason: overrideReason,
      });
      toast.success("Override saved");
      setOverrideOpen(false);
      window.location.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Override failed");
    }
  };

  const handleScoreAll = async () => {
    const unscored = portfolioRows.filter((r) => r.status !== "complete");
    if (unscored.length === 0) {
      toast.info("All use cases already scored");
      return;
    }
    setScoringAll(true);
    try {
      await Promise.all(
        unscored.map((r) =>
          apiPost(`/api/v1/use-cases/${r.uc.id}/s1/runs`, {}),
        ),
      );
      toast.success(`Started scoring ${unscored.length} use cases`);
      setTimeout(() => loadPortfolio(), 3000);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Scoring failed");
    } finally {
      setScoringAll(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!useCase) {
    return (
      <div className="min-h-screen bg-background p-8">
        <Alert variant="destructive">
          <AlertDescription>Use case not found</AlertDescription>
        </Alert>
      </div>
    );
  }

  const isStale = readiness?.s1 === "stale";
  const isRunning = readiness?.s1 === "running" || runningStage;
  const isComplete = readiness?.s1 === "complete" && !!latestResult;

  return (
    <div className="min-h-screen bg-background">
      {/* ── Header ── */}
      <header className="border-b border-border/50 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex h-14 items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <Link href={`/projects/${projectId}`}>
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-foreground -ml-2"
              >
                <ArrowLeft className="mr-1.5 h-4 w-4" />
                Back
              </Button>
            </Link>
            <div className="h-4 w-px bg-border/50" />
            <div>
              <p className="text-sm font-semibold">{useCase.name}</p>
              <p className="text-xs text-muted-foreground">
                Stage 1 — Migration Assessment
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* view toggle */}
            <div className="flex items-center gap-1 rounded-lg border border-border/50 p-1">
              <button
                onClick={() => setViewMode("scorecard")}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  viewMode === "scorecard"
                    ? "bg-primary/15 text-primary"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <BarChart3 className="h-3.5 w-3.5" />
                Scorecard
              </button>
              <button
                onClick={() => setViewMode("portfolio")}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  viewMode === "portfolio"
                    ? "bg-primary/15 text-primary"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <LayoutList className="h-3.5 w-3.5" />
                Portfolio
              </button>
            </div>

            {isComplete && (
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 5,
                  height: 30,
                  padding: "0 10px",
                  borderRadius: 6,
                  fontSize: 11.5,
                  fontWeight: 600,
                  color: "var(--c-green)",
                  background:
                    "color-mix(in oklab, var(--c-green) 12%, transparent)",
                  border:
                    "1px solid color-mix(in oklab, var(--c-green) 28%, transparent)",
                }}
              >
                <Icon name="check" size={12} /> Complete · run #{runs.length}
              </span>
            )}
            <RunHistoryDrawer
              runs={runs}
              stage="s1"
              stageName="Stage 1 - Assessment"
            />
            <Button size="sm" onClick={handleRun} disabled={isRunning}>
              <Play className="mr-1.5 h-3.5 w-3.5" />
              {isRunning ? "Running…" : "Run Assessment"}
            </Button>
          </div>
        </div>
      </header>

      <div className="py-6 px-7 space-y-5">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {isStale && <StalenessIndicator isStale stageName="Stage 1" />}
        {isRunning && (
          <AsyncRunProgress
            useCaseId={ucId}
            stage="s1"
            onComplete={handleRunComplete}
            onError={(e) => setError(e)}
          />
        )}

        {/* ══ SCORECARD VIEW ══════════════════════════════════════════ */}
        {viewMode === "scorecard" && (
          <>
            {/* Empty state — no run yet */}
            {!isComplete && !isRunning && (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: "60px 24px",
                  gap: 16,
                  textAlign: "center",
                  borderRadius: 14,
                  border: "1px solid var(--border)",
                  background: "var(--card)",
                }}
              >
                <span
                  style={{
                    width: 56,
                    height: 56,
                    borderRadius: 14,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background:
                      "color-mix(in oklab, var(--primary) 14%, transparent)",
                    color: "var(--primary)",
                  }}
                >
                  <Icon name="target" size={28} />
                </span>
                <div>
                  <div
                    style={{ fontSize: 17, fontWeight: 700, marginBottom: 6 }}
                  >
                    Run Migration Assessment
                  </div>
                  <div
                    style={{
                      fontSize: 13,
                      color: "var(--muted-foreground)",
                      maxWidth: 420,
                    }}
                  >
                    Haiku evaluates this use case across four dimensions —
                    technical feasibility, migration effort, platform
                    suitability, and risk — and recommends a migration band.
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                  <div
                    style={{
                      padding: "10px 16px",
                      borderRadius: 10,
                      background:
                        "color-mix(in oklab, var(--primary) 7%, transparent)",
                      border:
                        "1px solid color-mix(in oklab, var(--primary) 18%, transparent)",
                      fontSize: 12,
                      color: "var(--muted-foreground)",
                    }}
                  >
                    <div
                      style={{
                        fontWeight: 600,
                        color: "var(--foreground)",
                        marginBottom: 2,
                      }}
                    >
                      Use case
                    </div>
                    {useCase.name}
                  </div>
                  {useCase.source_platform && (
                    <div
                      style={{
                        padding: "10px 16px",
                        borderRadius: 10,
                        background:
                          "color-mix(in oklab, var(--primary) 7%, transparent)",
                        border:
                          "1px solid color-mix(in oklab, var(--primary) 18%, transparent)",
                        fontSize: 12,
                        color: "var(--muted-foreground)",
                      }}
                    >
                      <div
                        style={{
                          fontWeight: 600,
                          color: "var(--foreground)",
                          marginBottom: 2,
                        }}
                      >
                        Platform
                      </div>
                      {useCase.source_platform}
                    </div>
                  )}
                </div>
                <Button onClick={handleRun} className="glow-primary mt-2">
                  <Play className="mr-2 h-4 w-4" />
                  Run Assessment
                </Button>
              </div>
            )}

            {/* Scorecard — complete */}
            {isComplete && latestResult && (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "340px 1fr",
                  gap: 22,
                }}
              >
                {/* ── Left column ── */}
                <div
                  style={{ display: "flex", flexDirection: "column", gap: 18 }}
                >
                  {/* Score card */}
                  <div
                    style={{
                      borderRadius: 14,
                      border: "1px solid var(--border)",
                      background: "var(--card)",
                      padding: "26px 18px 22px",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 16,
                    }}
                  >
                    <Gauge
                      value={latestResult.total_score}
                      band={latestResult.migration_decision}
                      size={170}
                    />
                    <PriorityBadge
                      band={latestResult.migration_decision}
                      solid
                    />
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 7,
                        fontSize: 12,
                      }}
                    >
                      <span style={{ color: "var(--muted-foreground)" }}>
                        Confidence
                      </span>
                      <span
                        style={{
                          padding: "3px 8px",
                          borderRadius: 6,
                          fontSize: 11,
                          fontWeight: 600,
                          color: CONF_COLOR[latestResult.confidence],
                          background: `color-mix(in oklab, ${CONF_COLOR[latestResult.confidence]} 14%, transparent)`,
                          border: `1px solid color-mix(in oklab, ${CONF_COLOR[latestResult.confidence]} 30%, transparent)`,
                        }}
                      >
                        {latestResult.confidence}
                      </span>
                    </div>
                  </div>

                  {/* Inputs card */}
                  <div
                    style={{
                      borderRadius: 14,
                      border: "1px solid var(--border)",
                      background: "var(--card)",
                      padding: 18,
                    }}
                  >
                    <div
                      style={{
                        fontSize: 10.5,
                        fontWeight: 700,
                        letterSpacing: "1.4px",
                        textTransform: "uppercase",
                        color: "var(--muted-foreground)",
                        marginBottom: 14,
                      }}
                    >
                      Inputs
                    </div>
                    {[
                      ["Use case", useCase.name, "manual"],
                      ["Platform", useCase.source_platform || "—", "imported"],
                      ["Install", useCase.install_status || "—", "manual"],
                    ].map(([lbl, val, src]) => (
                      <div
                        key={lbl}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "9px 0",
                          borderBottom: "1px solid var(--border)",
                        }}
                      >
                        <span
                          style={{
                            fontSize: 12.5,
                            color: "var(--muted-foreground)",
                          }}
                        >
                          {lbl}
                        </span>
                        <span
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                          }}
                        >
                          <span style={{ fontSize: 12.5, fontWeight: 500 }}>
                            {val}
                          </span>
                          <InputSourceBadge source={src as never} />
                        </span>
                      </div>
                    ))}
                    <div style={{ paddingTop: 10 }}>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleBackfill}
                        style={{ width: "100%" }}
                      >
                        <Icon
                          name="link"
                          size={13}
                          style={{ marginRight: 6 }}
                        />
                        Backfill from Stage 2 (Sonnet)
                      </Button>
                    </div>
                  </div>
                </div>

                {/* ── Right column ── */}
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 18,
                    minHeight: 0,
                  }}
                >
                  {/* Scoring dims */}
                  <div
                    style={{
                      borderRadius: 14,
                      border: "1px solid var(--border)",
                      background: "var(--card)",
                      padding: 18,
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: 16,
                      }}
                    >
                      <div
                        style={{
                          fontSize: 10.5,
                          fontWeight: 700,
                          letterSpacing: "1.4px",
                          textTransform: "uppercase",
                          color: "var(--muted-foreground)",
                        }}
                      >
                        Scoring dimensions
                      </div>
                      <span
                        style={{
                          fontSize: 11,
                          color: "var(--muted-foreground)",
                          fontFamily: "var(--font-geist-mono)",
                        }}
                      >
                        weighted · Haiku 4.5
                      </span>
                    </div>
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr",
                        gap: "18px 28px",
                      }}
                    >
                      {S1_DIMS.map((d) => (
                        <DimBar
                          key={d.key}
                          label={d.label}
                          value={latestResult[d.key] ?? 0}
                          max={d.max}
                          color={d.color}
                        />
                      ))}
                    </div>
                  </div>

                  {/* AI analysis */}
                  <div
                    style={{
                      flex: 1,
                      borderRadius: 14,
                      border: "1px solid var(--border)",
                      background: "var(--card)",
                      padding: 18,
                      display: "flex",
                      flexDirection: "column",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: 12,
                      }}
                    >
                      <div
                        style={{
                          fontSize: 10.5,
                          fontWeight: 700,
                          letterSpacing: "1.4px",
                          textTransform: "uppercase",
                          color: "var(--muted-foreground)",
                        }}
                      >
                        AI analysis
                      </div>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 5,
                          padding: "3px 8px",
                          borderRadius: 6,
                          fontSize: 11,
                          fontWeight: 600,
                          color: "var(--primary)",
                          background:
                            "color-mix(in oklab, var(--primary) 13%, transparent)",
                          border:
                            "1px solid color-mix(in oklab, var(--primary) 28%, transparent)",
                        }}
                      >
                        <Icon name="spark" size={11} /> Generated
                      </span>
                    </div>
                    <p
                      style={{
                        fontSize: 13,
                        lineHeight: 1.62,
                        color: "var(--muted-foreground)",
                        margin: 0,
                      }}
                    >
                      {latestResult.analysis}
                    </p>

                    {latestResult.blockers.length > 0 && (
                      <div style={{ marginTop: 16 }}>
                        <div
                          style={{
                            fontSize: 11.5,
                            fontWeight: 600,
                            color: "var(--c-amber)",
                            marginBottom: 8,
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                          }}
                        >
                          <Icon name="flag" size={13} /> Blockers (
                          {latestResult.blockers.length})
                        </div>
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: 7,
                          }}
                        >
                          {latestResult.blockers.map((b, i) => (
                            <div
                              key={i}
                              style={{
                                display: "flex",
                                gap: 9,
                                alignItems: "flex-start",
                                fontSize: 12.5,
                                color: "var(--muted-foreground)",
                                padding: "9px 12px",
                                borderRadius: 9,
                                background:
                                  "color-mix(in oklab, var(--c-amber) 8%, transparent)",
                                border:
                                  "1px solid color-mix(in oklab, var(--c-amber) 20%, transparent)",
                              }}
                            >
                              <span
                                style={{
                                  width: 5,
                                  height: 5,
                                  borderRadius: 99,
                                  background: "var(--c-amber)",
                                  marginTop: 6,
                                  flexShrink: 0,
                                }}
                              />
                              {b}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div
                      style={{
                        marginTop: 16,
                        paddingTop: 14,
                        borderTop: "1px solid var(--border)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                      }}
                    >
                      <div>
                        <div
                          style={{
                            fontSize: 11,
                            color: "var(--muted-foreground)",
                          }}
                        >
                          Power Automate fit
                        </div>
                        <div
                          style={{
                            fontSize: 12.5,
                            color: "var(--muted-foreground)",
                            marginTop: 2,
                          }}
                        >
                          {latestResult.power_automate_fit}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setOverrideDims({
                            technical_feasibility:
                              latestResult.technical_feasibility,
                            migration_effort: latestResult.migration_effort,
                            platform_suitability:
                              latestResult.platform_suitability,
                            risk: latestResult.risk,
                          });
                          setOverrideOpen(true);
                        }}
                      >
                        <Icon
                          name="edit"
                          size={13}
                          style={{ marginRight: 6 }}
                        />
                        Override decision
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* ══ PORTFOLIO VIEW ══════════════════════════════════════════ */}
        {viewMode === "portfolio" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Header row */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div>
                <h2 style={{ fontSize: 19, fontWeight: 700, margin: 0 }}>
                  Parallel assessment
                </h2>
                <p
                  style={{
                    fontSize: 12.5,
                    color: "var(--muted-foreground)",
                    margin: "4px 0 0",
                  }}
                >
                  Haiku scores every use case concurrently across the four
                  dimensions.
                </p>
              </div>
              <Button
                size="sm"
                onClick={handleScoreAll}
                disabled={scoringAll || portfolioLoading}
              >
                <Icon name="zap" size={13} style={{ marginRight: 6 }} />
                {scoringAll ? "Scoring…" : "Score all (Haiku)"}
              </Button>
            </div>

            {portfolioLoading && (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            )}

            {!portfolioLoading && (
              <div
                style={{
                  borderRadius: 13,
                  border: "1px solid var(--border)",
                  overflow: "hidden",
                  background: "var(--card)",
                }}
              >
                {/* Table header */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "2.1fr repeat(4, 1fr) 1fr 1.1fr",
                    padding: "11px 18px",
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: 0.5,
                    color: "var(--muted-foreground)",
                    textTransform: "uppercase",
                    borderBottom: "1px solid var(--border)",
                  }}
                >
                  <span>Use case</span>
                  {S1_DIMS.map((d) => (
                    <span key={d.key} style={{ textAlign: "center" }}>
                      {d.label.split(" ")[0].slice(0, 5)}
                    </span>
                  ))}
                  <span style={{ textAlign: "center" }}>Score</span>
                  <span style={{ textAlign: "right" }}>Decision</span>
                </div>

                {portfolioRows.map((row, idx) => {
                  const { uc, result, status } = row;
                  const isActive = uc.id === ucId;
                  const running = status === "running";
                  return (
                    <div
                      key={uc.id}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "2.1fr repeat(4, 1fr) 1fr 1.1fr",
                        padding: "13px 18px",
                        alignItems: "center",
                        borderBottom:
                          idx < portfolioRows.length - 1
                            ? "1px solid var(--border)"
                            : "none",
                        background: isActive
                          ? "color-mix(in oklab, var(--primary) 6%, transparent)"
                          : "transparent",
                      }}
                    >
                      <div style={{ minWidth: 0, paddingRight: 10 }}>
                        <div
                          style={{
                            fontSize: 12.5,
                            fontWeight: 600,
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                          }}
                        >
                          {uc.name}
                        </div>
                        <div
                          style={{
                            fontSize: 10.5,
                            color: "var(--muted-foreground)",
                          }}
                        >
                          {uc.source_platform || "—"}
                        </div>
                      </div>

                      {running ? (
                        <div
                          style={{
                            gridColumn: "2 / 7",
                            display: "flex",
                            alignItems: "center",
                            gap: 10,
                            color: "var(--primary)",
                            fontSize: 12,
                          }}
                        >
                          <span
                            style={{
                              width: 8,
                              height: 8,
                              borderRadius: 99,
                              background: "var(--primary)",
                              animation: "rpaPulse 1.6s ease-in-out infinite",
                            }}
                          />
                          Scoring across 4 dimensions…
                        </div>
                      ) : result ? (
                        <>
                          {S1_DIMS.map((d) => (
                            <div
                              key={d.key}
                              style={{
                                display: "flex",
                                flexDirection: "column",
                                alignItems: "center",
                                gap: 4,
                              }}
                            >
                              <span
                                style={{
                                  fontFamily: "var(--font-geist-mono)",
                                  fontSize: 11.5,
                                  color: "var(--muted-foreground)",
                                }}
                              >
                                {result[d.key] ?? 0}
                              </span>
                              <div
                                style={{
                                  width: 34,
                                  height: 4,
                                  borderRadius: 99,
                                  background: "var(--track)",
                                  overflow: "hidden",
                                }}
                              >
                                <div
                                  style={{
                                    width: `${((result[d.key] ?? 0) / d.max) * 100}%`,
                                    height: "100%",
                                    background: d.color,
                                  }}
                                />
                              </div>
                            </div>
                          ))}
                          <div
                            style={{
                              textAlign: "center",
                              fontFamily: "var(--font-geist-mono)",
                              fontSize: 16,
                              fontWeight: 700,
                              color:
                                BAND_META[result.migration_decision]?.color,
                            }}
                          >
                            {result.total_score}
                          </div>
                        </>
                      ) : (
                        <div
                          style={{
                            gridColumn: "2 / 7",
                            fontSize: 12,
                            color: "var(--muted-foreground)",
                          }}
                        >
                          Queued — awaiting score
                        </div>
                      )}

                      <div
                        style={{
                          textAlign: "right",
                          display: "flex",
                          justifyContent: "flex-end",
                        }}
                      >
                        {result ? (
                          <PriorityBadge band={result.migration_decision} />
                        ) : (
                          <span
                            style={{
                              fontSize: 11,
                              color: "var(--muted-foreground)",
                            }}
                          >
                            —
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Follow-up callout */}
            {portfolioRows.some(
              (r) => r.result?.follow_up_questions?.length,
            ) && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  padding: "14px 18px",
                  borderRadius: 12,
                  background:
                    "color-mix(in oklab, var(--primary) 7%, var(--card))",
                  border:
                    "1px solid color-mix(in oklab, var(--primary) 18%, transparent)",
                }}
              >
                <span
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 10,
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background:
                      "color-mix(in oklab, var(--primary) 16%, transparent)",
                    color: "var(--primary)",
                  }}
                >
                  <Icon name="spark" size={18} />
                </span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 600 }}>
                    Follow-up questions generated for low-confidence cases
                  </div>
                  <div
                    style={{ fontSize: 11.5, color: "var(--muted-foreground)" }}
                  >
                    Review the individual scorecard for each flagged use case.
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Override Sheet ── */}
      <Sheet open={overrideOpen} onOpenChange={setOverrideOpen}>
        <SheetContent className="w-120">
          <SheetHeader>
            <SheetTitle>Manual Override</SheetTitle>
          </SheetHeader>
          <p className="text-sm text-muted-foreground mt-2 mb-6">
            Adjust dimensions directly. Overrides are stored as a new run with a
            required reason.
          </p>
          <div className="space-y-6">
            <div className="flex justify-around">
              {S1_DIMS.map((d) => (
                <RadialDim
                  key={d.key}
                  label={d.label}
                  value={overrideDims[d.key] ?? 0}
                  max={d.max}
                  color={d.color}
                  size={80}
                />
              ))}
            </div>

            <Separator />

            <div className="space-y-3">
              {S1_DIMS.map((d) => (
                <div key={d.key}>
                  <div
                    className="flex justify-between text-xs mb-1.5"
                    style={{ color: "var(--muted-foreground)" }}
                  >
                    <span>{d.label}</span>
                    <span className="font-mono">
                      {overrideDims[d.key] ?? 0} / {d.max}
                    </span>
                  </div>
                  <div
                    className="relative h-2 rounded-full"
                    style={{ background: "var(--track)" }}
                  >
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${((overrideDims[d.key] ?? 0) / d.max) * 100}%`,
                        background: d.color,
                      }}
                    />
                    <input
                      type="range"
                      min={0}
                      max={d.max}
                      value={overrideDims[d.key] ?? 0}
                      onChange={(e) =>
                        setOverrideDims((prev) => ({
                          ...prev,
                          [d.key]: +e.target.value,
                        }))
                      }
                      className="absolute inset-0 w-full opacity-0 cursor-pointer h-full"
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Decision preview */}
            <div>
              <Label className="text-xs mb-2 block">Decision preview</Label>
              <div className="flex gap-2 flex-wrap">
                {(
                  [
                    "QUICK_WIN",
                    "STRATEGIC",
                    "HOLD",
                    "DO_NOT_MIGRATE",
                  ] as MigrationDecision[]
                ).map((b) => (
                  <PriorityBadge key={b} band={b} />
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label>
                Reason <span className="text-destructive">*</span>
              </Label>
              <Textarea
                placeholder="Why are you overriding the AI assessment?"
                value={overrideReason}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                  setOverrideReason(e.target.value)
                }
                rows={3}
              />
            </div>

            <div className="flex gap-2">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setOverrideOpen(false)}
              >
                Cancel
              </Button>
              <Button className="flex-1" onClick={handleOverrideSave}>
                <Icon name="check" size={13} style={{ marginRight: 6 }} />
                Save Override
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

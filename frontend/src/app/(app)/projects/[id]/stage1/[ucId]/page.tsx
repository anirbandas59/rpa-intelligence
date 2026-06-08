"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Sheet, SheetContent, SheetHeader } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Btn, SectionLabel, Card, Pill, FieldRow } from "@/components/rpa";
import { spacing } from "@/lib/design-tokens";
import { AsyncRunProgress } from "@/components/shared/AsyncRunProgress";
import { RunHistoryDrawer } from "@/components/shared/RunHistoryDrawer";
import { StalenessIndicator } from "@/components/shared/StalenessIndicator";
import { Gauge } from "@/components/shared/Gauge";
import { DimBar } from "@/components/shared/DimBar";
import { RadialDim } from "@/components/shared/RadialDim";
import { PriorityBadge, BAND_META } from "@/components/shared/PriorityBadge";
import { Icon } from "@/components/shared/icons";
import { ArrowLeft, Loader2, Play } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiGetRuns, apiPost, isAuthenticated } from "@/lib/api";
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
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");
  const [overrideDims, setOverrideDims] = useState<Record<string, number>>({});
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRunIndex, setSelectedRunIndex] = useState<number>(0);
  const [overrideExplanation, setOverrideExplanation] = useState("");
  const [loadingExplanation, setLoadingExplanation] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/auth/login");
      return;
    }

    const fetchData = async () => {
      try {
        const [ucData, readinessData, runsData] = await Promise.all([
          apiGet<UseCase>(`/api/v1/use-cases/${ucId}`),
          apiGet<ReadinessResponse>(`/api/v1/use-cases/${ucId}/readiness`),
          apiGetRuns<StageRun>(`/api/v1/use-cases/${ucId}/s1/runs`).catch(
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
    };

    fetchData();
  }, [ucId, router]);


  const handleRun = async () => {
    setRunningStage(true);
    setError("");
    try {
      await apiPost(`/api/v1/use-cases/${ucId}/s1/runs`, {});
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
      await apiPost(`/api/v1/use-cases/${ucId}/s1/backfill-from-s2`, {});
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
      // Calculate new total score from override values
      const newTotal = Object.values(overrideDims).reduce((sum, val) => sum + (val || 0), 0);

      await apiPost(`/api/v1/use-cases/${ucId}/s1/override`, {
        ...overrideDims,
        reason: overrideReason,
      });

      toast.success(`Override saved — new score: ${newTotal}/100`);
      setOverrideOpen(false);
      window.location.reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Override failed");
    }
  };

  const handleExplainOverride = async () => {
    setLoadingExplanation(true);
    try {
      const result = await apiPost<{ status: string; explanation: string }>(
        `/api/v1/use-cases/${ucId}/s1/explain-override`,
        {}
      );
      setOverrideExplanation(result.explanation);
      toast.success("Explanation generated");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to generate explanation");
    } finally {
      setLoadingExplanation(false);
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
  // Show scorecard if we have a result, regardless of readiness status
  const isComplete = !!latestResult;

  // Display result: selected run if navigating history, otherwise latest
  const displayResult = selectedRunId
    ? (runs.find((r) => r.id === selectedRunId)?.result as S1Result | undefined)
    : latestResult;

  // Navigation functions
  const navigateToPreviousRun = () => {
    if (selectedRunIndex > 0) {
      const newIndex = selectedRunIndex - 1;
      setSelectedRunIndex(newIndex);
      setSelectedRunId(runs[newIndex].id);
    }
  };

  const navigateToNextRun = () => {
    if (selectedRunIndex < runs.length - 1) {
      const newIndex = selectedRunIndex + 1;
      setSelectedRunIndex(newIndex);
      setSelectedRunId(runs[newIndex].id);
    }
  };

  const handleSetCurrentRun = async () => {
    if (!selectedRunId) return;
    try {
      await apiPost(
        `/api/v1/use-cases/${ucId}/s1/runs/${selectedRunId}/set-current`,
        {},
      );
      toast.success("Set as current run");
      window.location.reload();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to set current run",
      );
    }
  };

  const handleRunSelect = (runId: string) => {
    const index = runs.findIndex((r) => r.id === runId);
    if (index !== -1) {
      setSelectedRunId(runId);
      setSelectedRunIndex(index);
    }
  };

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
            {/* Run history navigation */}
            {isComplete && runs.length > 1 && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "0 10px",
                  height: 30,
                  borderRadius: 6,
                  border: "1px solid var(--border)",
                  background: "var(--surface)",
                }}
              >
                <button
                  onClick={navigateToPreviousRun}
                  disabled={selectedRunIndex === 0}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 20,
                    height: 20,
                    borderRadius: 4,
                    border: "none",
                    background: "transparent",
                    cursor: selectedRunIndex === 0 ? "not-allowed" : "pointer",
                    opacity: selectedRunIndex === 0 ? 0.4 : 1,
                    color: "var(--muted-fg)",
                  }}
                >
                  <Icon
                    name="chevR"
                    size={14}
                    style={{ transform: "rotate(180deg)" }}
                  />
                </button>
                <span
                  style={{
                    fontSize: 11,
                    fontFamily: "var(--mono)",
                    color: "var(--muted-fg)",
                  }}
                >
                  Run {selectedRunIndex + 1} of {runs.length}
                </span>
                <button
                  onClick={navigateToNextRun}
                  disabled={selectedRunIndex === runs.length - 1}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 20,
                    height: 20,
                    borderRadius: 4,
                    border: "none",
                    background: "transparent",
                    cursor:
                      selectedRunIndex === runs.length - 1
                        ? "not-allowed"
                        : "pointer",
                    opacity: selectedRunIndex === runs.length - 1 ? 0.4 : 1,
                    color: "var(--muted-fg)",
                  }}
                >
                  <Icon name="chevR" size={14} />
                </button>
              </div>
            )}

            {isComplete && !selectedRunId && (
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
                <Icon name="check" size={12} /> Current
              </span>
            )}

            {selectedRunId && selectedRunId !== useCase?.s1_latest_run_id && (
              <Button size="sm" variant="outline" onClick={handleSetCurrentRun}>
                <Icon name="check" size={13} style={{ marginRight: 6 }} />
                Set as Current
              </Button>
            )}

            <RunHistoryDrawer
              runs={runs}
              stage="s1"
              stageName="Stage 1 - Assessment"
              currentRunId={useCase?.s1_latest_run_id}
              selectedRunId={
                selectedRunId || useCase?.s1_latest_run_id || undefined
              }
              onSelectRun={handleRunSelect}
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
                    AI evaluates this use case across four dimensions —
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
            {isComplete && displayResult && (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 18,
                }}
              >
                {/* Override banner - show when result has override */}
                {displayResult.override_reason && displayResult.override_reason.length > 0 && (
                  <div
                    style={{
                      padding: "12px 16px",
                      borderRadius: 10,
                      background: "color-mix(in oklab, var(--c-amber) 10%, transparent)",
                      border: "1px solid color-mix(in oklab, var(--c-amber) 25%, transparent)",
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                    }}
                  >
                    <Icon name="user" size={16} style={{ color: "var(--c-amber)" }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--foreground)", marginBottom: 2 }}>
                        Manually Adjusted Score
                      </div>
                      <div style={{ fontSize: 11.5, color: "var(--muted-foreground)" }}>
                        This assessment was overridden by {displayResult.override_by}
                      </div>
                    </div>
                  </div>
                )}

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
                    <Card
                      style={{
                        paddingTop: 26,
                        paddingBottom: 22,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: 16,
                      }}
                  >
                    <Gauge
                      value={displayResult.total_score}
                      band={displayResult.migration_decision}
                      size={170}
                    />
                    <PriorityBadge
                      band={displayResult.migration_decision}
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
                      <span style={{ color: "var(--muted-fg)" }}>
                        Confidence
                      </span>
                      <Pill color={CONF_COLOR[displayResult.confidence]}>
                        {displayResult.confidence}
                      </Pill>
                    </div>
                  </Card>

                  {/* Inputs card */}
                  <Card>
                    <SectionLabel style={{ marginBottom: 6 }}>
                      Inputs
                    </SectionLabel>
                    <FieldRow label="Use case" value={useCase.name} />
                    <FieldRow label="Description" value={useCase.description} />
                    <FieldRow
                      label="Platform"
                      value={useCase.source_platform || "—"}
                    />
                    <FieldRow
                      label="Install"
                      value={useCase.install_status || "—"}
                    />
                    <div style={{ paddingTop: 10 }}>
                      <Btn
                        variant="outline"
                        size="sm"
                        onClick={handleBackfill}
                        icon="link"
                        style={{ width: "100%" }}
                      >
                        Backfill from Stage 2
                      </Btn>
                    </div>
                  </Card>
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
                  <Card>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: 16,
                      }}
                    >
                      <SectionLabel>Scoring dimensions</SectionLabel>
                      <span
                        style={{
                          fontSize: 11,
                          color: "var(--muted-fg)",
                          fontFamily: "var(--mono)",
                        }}
                      >
                        weighted · AI-powered
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
                          value={displayResult[d.key] ?? 0}
                          max={d.max}
                          color={d.color}
                        />
                      ))}
                    </div>
                  </Card>

                  {/* AI analysis */}
                  <Card
                    style={{
                      flex: 1,
                      minHeight: 0,
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
                      <SectionLabel>AI analysis</SectionLabel>
                      <Pill color="var(--primary)">
                        <Icon name="spark" size={11} /> Generated
                      </Pill>
                    </div>
                    <p
                      style={{
                        fontSize: 13,
                        lineHeight: 1.62,
                        color: "var(--muted-foreground)",
                        margin: 0,
                      }}
                    >
                      {displayResult.analysis}
                    </p>

                    {displayResult.blockers.length > 0 && (
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
                          {displayResult.blockers.length})
                        </div>
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: 7,
                          }}
                        >
                          {displayResult.blockers.map((b, i) => (
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

                    {displayResult.override_reason &&
                      displayResult.override_reason.length > 0 && (
                        <div style={{ marginTop: 16 }}>
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                              marginBottom: 12,
                            }}
                          >
                            <SectionLabel>Override Reason</SectionLabel>
                            <Pill color="var(--foreground)">
                              <Icon name="user" size={11} />{" "}
                              {displayResult.override_by}
                            </Pill>
                          </div>
                          <p
                            style={{
                              fontSize: 13,
                              lineHeight: 1.62,
                              color: "var(--muted-foreground)",
                              margin: 0,
                            }}
                          >
                            {displayResult.override_reason}
                          </p>

                          {/* Explain Override button and explanation */}
                          {!overrideExplanation ? (
                            <div style={{ marginTop: 12 }}>
                              <Btn
                                variant="ghost"
                                size="sm"
                                icon="bot"
                                onClick={handleExplainOverride}
                                disabled={loadingExplanation}
                              >
                                {loadingExplanation ? "Generating..." : "Explain Override"}
                              </Btn>
                            </div>
                          ) : (
                            <Card
                              style={{
                                marginTop: 12,
                                padding: 14,
                                background: "color-mix(in oklab, var(--primary) 5%, transparent)",
                                border: "1px solid color-mix(in oklab, var(--primary) 15%, transparent)",
                              }}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 8,
                                  marginBottom: 8,
                                }}
                              >
                                <Icon name="bot" size={14} style={{ color: "var(--primary)" }} />
                                <div
                                  style={{
                                    fontSize: 11,
                                    fontWeight: 600,
                                    color: "var(--primary)",
                                  }}
                                >
                                  AI Explanation
                                </div>
                              </div>
                              <p
                                style={{
                                  fontSize: 12.5,
                                  lineHeight: 1.62,
                                  color: "var(--muted-foreground)",
                                  margin: 0,
                                }}
                              >
                                {overrideExplanation}
                              </p>
                            </Card>
                          )}
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
                          {displayResult.power_automate_fit}
                        </div>
                      </div>
                      <Btn
                        variant="ghost"
                        size="sm"
                        icon="edit"
                        onClick={() => {
                          setOverrideDims({
                            technical_feasibility:
                              displayResult.technical_feasibility,
                            migration_effort: displayResult.migration_effort,
                            platform_suitability:
                              displayResult.platform_suitability,
                            risk: displayResult.risk,
                          });
                          setOverrideOpen(true);
                        }}
                      >
                        Override decision
                      </Btn>
                    </div>
                  </Card>
                </div>
              </div>
              </div>
            )}
      </div>

      {/* ── Override Sheet ── */}
      <Sheet open={overrideOpen} onOpenChange={setOverrideOpen}>
        <SheetContent
          className="w-120"
          style={{ padding: spacing.cardDefault }}
        >
          <SheetHeader style={{ marginBottom: spacing.gapDefault }}>
            <SectionLabel>Manual Override</SectionLabel>
            <p
              style={{
                fontSize: 12.8,
                color: "var(--muted-foreground)",
                marginTop: 8,
              }}
            >
              Adjust dimensions directly. Overrides are stored as a new run with
              a required reason.
            </p>
          </SheetHeader>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: spacing.gapLoose,
            }}
          >
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

            <div style={{ display: "flex", gap: spacing.gapTight }}>
              <Btn
                variant="outline"
                style={{ flex: 1 }}
                onClick={() => setOverrideOpen(false)}
              >
                Cancel
              </Btn>
              <Btn style={{ flex: 1 }} onClick={handleOverrideSave}>
                <Icon name="check" size={13} style={{ marginRight: 6 }} />
                Save Override
              </Btn>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

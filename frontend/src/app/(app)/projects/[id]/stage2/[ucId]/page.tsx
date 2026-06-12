"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { InputSourceBadge } from "@/components/shared/InputSourceBadge";
import { Card, Btn, SectionLabel, Pill } from "@/components/rpa";
import { spacing } from "@/lib/design-tokens";
import { StalenessIndicator } from "@/components/shared/StalenessIndicator";
import { AsyncRunProgress } from "@/components/shared/AsyncRunProgress";
import { StageHeader } from "@/components/shared/StageHeader";
import { ComplexityChip, CLS_COLORS } from "@/components/shared/ComplexityChip";
import { Icon } from "@/components/shared/icons";
import { Upload, Play, Loader2 } from "lucide-react";
import {
  apiGet,
  apiGetRuns,
  apiPost,
  apiPatch,
  apiPostFormData,
  isAuthenticated,
} from "@/lib/api";
import {
  scoreComplexity,
  getComplexityColor,
  hasAllBands,
  WEIGHTS,
} from "@/lib/scoring";
import type {
  UseCase,
  StageRun,
  Band,
  AttributeBands,
  ReadinessResponse,
  S2Result,
  InputSource,
} from "@/lib/types";

const BANDS: Band[] = ["XS", "S", "M", "L", "XL"];
const ATTRS: Array<{ key: keyof AttributeBands; label: string }> = [
  { key: "activities", label: "Activities" },
  { key: "business_rules", label: "Business Rules" },
  { key: "layouts", label: "Layouts" },
  { key: "interfaces", label: "Interfaces" },
  { key: "technology", label: "Technology" },
];

/* Score ladder — 5 segments: XS S M L XL */
const LADDER_RANGES = [
  { band: "XS" as Band, max: 6, label: "XS" },
  { band: "S" as Band, max: 8, label: "S" },
  { band: "M" as Band, max: 15, label: "M" },
  { band: "L" as Band, max: 22, label: "L" },
  { band: "XL" as Band, max: 28, label: "XL" },
];

export default function Stage2Page() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const ucId = params.ucId as string;

  const [useCase, setUseCase] = useState<UseCase | null>(null);
  const [bands, setBands] = useState<Partial<AttributeBands>>({});
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [runs, setRuns] = useState<StageRun[]>([]);
  const [latestResult, setLatestResult] = useState<S2Result | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [runningStage, setRunningStage] = useState(false);
  const [error, setError] = useState("");
  const [weightMatrix, setWeightMatrix] = useState<any>(null);
  const [documentUploaded, setDocumentUploaded] = useState(false);
  const [projectUseCases, setProjectUseCases] = useState<UseCase[]>([]);

  const liveScore = hasAllBands(bands as AttributeBands)
    ? scoreComplexity(bands as AttributeBands)
    : null;

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/auth/login");
      return;
    }

    const fetchData = async () => {
      try {
        const [ucData, readinessData, runsData, matrixData, useCasesData] =
          await Promise.all([
            apiGet<UseCase>(`/api/v1/use-cases/${ucId}`),
            apiGet<ReadinessResponse>(`/api/v1/use-cases/${ucId}/readiness`),
            apiGetRuns<StageRun>(`/api/v1/use-cases/${ucId}/s2/runs`),
            apiGet<any>(`/api/v1/settings/weight-matrix`),
            apiGet<UseCase[]>(`/api/v1/projects/${projectId}/use-cases`).catch(
              () => [] as UseCase[],
            ),
          ]);
        setUseCase(ucData);
        setReadiness(readinessData);
        setRuns(runsData);
        setWeightMatrix(matrixData);
        setProjectUseCases(useCasesData);

        if (ucData.s2_inputs?.bands)
          setBands(ucData.s2_inputs.bands as Partial<AttributeBands>);

        if (ucData.s2_latest_run_id && runsData.length > 0) {
          const latestRun = runsData.find(
            (r) => r.id === ucData.s2_latest_run_id,
          );
          if (latestRun?.status === "complete") {
            const result = latestRun.result as unknown as S2Result;
            setLatestResult(result);

            // Load bands from run result (handles both old nested and new flat structures)
            if (result.bands) {
              setBands(result.bands as Partial<AttributeBands>);
            }
          } else if (latestRun?.status === "failed") {
            setError(
              `Run failed: ${latestRun.error_message || "Unknown error"}`,
            );
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

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingFile(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      await apiPostFormData(`/api/v1/use-cases/${ucId}/s2/documents`, formData);

      // Upload successful - band extraction happens when user clicks "Run Analysis"
      setDocumentUploaded(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploadingFile(false);
    }
  };

  const handleBandChange = async (
    attribute: keyof AttributeBands,
    value: Band,
  ) => {
    const newBands = { ...bands, [attribute]: value };
    setBands(newBands);
    try {
      await apiPatch(`/api/v1/use-cases/${ucId}/s2/inputs`, {
        bands: { [attribute]: value, [`${attribute}_source`]: "corrected" },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update input");
    }
  };

  const handleRunStage = async () => {
    setRunningStage(true);
    setError("");
    try {
      await apiPost(`/api/v1/use-cases/${ucId}/s2/runs`, {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run");
      setRunningStage(false);
    }
  };

  const handleRunComplete = () => {
    setRunningStage(false);
    window.location.reload();
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

  const isStale = readiness?.s2 === "stale";
  const isRunning = readiness?.s2 === "running" || runningStage;

  const displayScore = liveScore
    ? {
        ...liveScore,
        sprint_min: liveScore.sprints,
        sprint_max: liveScore.sprints,
      }
    : latestResult
      ? (() => {
          // Backward compatibility: handle both old nested and new flat structures
          const scoring = (latestResult as any).scoring; // Old structure has nested "scoring"
          const source = scoring || latestResult; // Use nested if exists, otherwise flat

          return {
            total_score: source.total_score,
            complexity_class: source.complexity_class,
            effort_min_weeks: source.effort_min_weeks,
            effort_max_weeks: source.effort_max_weeks,
            sprint_min: source.sprint_min ?? source.sprints ?? 0,
            sprint_max: source.sprint_max ?? source.sprints ?? 0,
          };
        })()
      : null;

  // Build tooltip text from weight matrix
  const getBandTooltip = (attribute: keyof AttributeBands, band: Band) => {
    if (!weightMatrix) return "";
    const attrData = weightMatrix.weights?.[attribute]?.[band];
    if (!attrData) return "";
    return `${band}: ${attrData.range}`;
  };

  return (
    <div className="min-h-screen bg-background">
      <StageHeader
        projectId={projectId}
        stageNumber={2}
        stageName="Complexity Analysis"
        stageId="s2"
        ucId={ucId}
        useCase={useCase}
        useCases={[...projectUseCases].sort((a, b) =>
          a.name.localeCompare(b.name),
        )}
        runs={runs}
        currentRunId={useCase?.s2_latest_run_id}
        isComplete={!!latestResult}
        actions={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {latestResult && (
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
          </div>
        }
      />

      <div className="py-6 px-7 space-y-6">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {isStale && <StalenessIndicator isStale stageName="Stage 2" />}
        {isRunning && (
          <AsyncRunProgress
            useCaseId={ucId}
            stage="s2"
            onComplete={handleRunComplete}
            onError={(e) => setError(e)}
          />
        )}

        {/* Main grid: band picker + result panel */}
        <div
          style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 22 }}
        >
          {/* ── Left: band picker ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            {/* Doc upload */}
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
                Input method
              </div>
              <Label
                htmlFor="file-upload"
                style={{
                  display: "flex",
                  height: 80,
                  cursor: "pointer",
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 10,
                  border: "2px dashed",
                  borderColor:
                    "color-mix(in oklab, var(--primary) 25%, transparent)",
                  background:
                    "color-mix(in oklab, var(--primary) 5%, transparent)",
                  transition: "border-color 0.15s",
                  gap: 10,
                }}
              >
                <Upload
                  style={{
                    height: 18,
                    width: 18,
                    color: "var(--primary)",
                    opacity: 0.7,
                  }}
                />
                <div style={{ textAlign: "center" }}>
                  <div
                    style={{
                      fontSize: 12.5,
                      fontWeight: 500,
                      color: "var(--muted-foreground)",
                    }}
                  >
                    {uploadingFile
                      ? "Uploading…"
                      : "Upload Process Document (PDF / DOCX)"}
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      color: "var(--muted-foreground)",
                      opacity: 0.6,
                      marginTop: 2,
                    }}
                  >
                    AI extracts band values automatically
                  </div>
                </div>
                <Input
                  id="file-upload"
                  type="file"
                  accept=".pdf,.docx"
                  className="hidden"
                  onChange={handleFileUpload}
                  disabled={uploadingFile || isRunning}
                />
              </Label>

              {/* Upload progress indicator */}
              {uploadingFile && (
                <div
                  style={{
                    padding: "12px 16px",
                    borderRadius: 10,
                    background:
                      "color-mix(in oklab, var(--primary) 8%, transparent)",
                    border:
                      "1px solid color-mix(in oklab, var(--primary) 20%, transparent)",
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                  }}
                >
                  <Icon
                    name="upload"
                    size={16}
                    style={{ color: "var(--primary)" }}
                  />
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        fontSize: 12.5,
                        fontWeight: 600,
                        color: "var(--primary)",
                      }}
                    >
                      Uploading document...
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: "var(--muted-foreground)",
                        marginTop: 2,
                      }}
                    >
                      Click &ldquo;Run Analysis&rdquo; after upload to extract
                      complexity bands
                    </div>
                  </div>
                  <div className="spinner" style={{ width: 16, height: 16 }} />
                </div>
              )}

              {/* Upload success indicator */}
              {documentUploaded && !uploadingFile && !latestResult && (
                <div
                  style={{
                    padding: "12px 16px",
                    borderRadius: 10,
                    background:
                      "color-mix(in oklab, var(--c-green) 8%, transparent)",
                    border:
                      "1px solid color-mix(in oklab, var(--c-green) 20%, transparent)",
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                  }}
                >
                  <Icon
                    name="check"
                    size={16}
                    style={{ color: "var(--c-green)" }}
                  />
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        fontSize: 12.5,
                        fontWeight: 600,
                        color: "var(--c-green)",
                      }}
                    >
                      Document uploaded successfully
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: "var(--muted-foreground)",
                        marginTop: 2,
                      }}
                    >
                      Click &ldquo;Run Analysis&rdquo; to extract complexity
                      bands and calculate score
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Run Analysis Button - moved from header actions */}
            {(documentUploaded || hasAllBands(bands as AttributeBands)) && (
              <Button
                size="sm"
                onClick={handleRunStage}
                disabled={
                  isRunning ||
                  (!hasAllBands(bands as AttributeBands) && !documentUploaded)
                }
                style={{ width: "fit-content" }}
              >
                <Play className="mr-1.5 h-3.5 w-3.5" />
                {isRunning ? "Running…" : "Run Analysis"}
              </Button>
            )}

            {/* 5×5 band grid */}
            <Card pad={0} style={{ overflow: "hidden" }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: spacing.cardDefault,
                  paddingBottom: 0,
                  marginBottom: 18,
                }}
              >
                <SectionLabel>Complexity bands</SectionLabel>
                <span
                  style={{
                    fontSize: 11,
                    color: "var(--muted-fg)",
                    fontFamily: "var(--mono)",
                  }}
                >
                  0 → 28 pts
                </span>
              </div>

              {/* Header row - simplified without weight column */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr repeat(5, 1fr)",
                  alignItems: "center",
                  padding: "12px 18px",
                  borderBottom: "1px solid var(--border)",
                }}
              >
                <span
                  style={{
                    fontSize: 10.5,
                    fontWeight: 700,
                    letterSpacing: 0.5,
                    color: "var(--muted-fg)",
                    textTransform: "uppercase",
                  }}
                >
                  Attribute
                </span>
                {BANDS.map((b) => (
                  <span
                    key={b}
                    style={{
                      textAlign: "center",
                      fontFamily: "var(--mono)",
                      fontSize: 12,
                      fontWeight: 700,
                      color: CLS_COLORS[b],
                    }}
                  >
                    {b}
                  </span>
                ))}
              </div>

              {/* Attribute rows - clean band buttons with tooltips */}
              {ATTRS.map(({ key, label }, idx) => {
                const active = bands[key];
                const source = useCase.s2_inputs?.[`${key}_source`] as
                  | InputSource
                  | undefined;
                return (
                  <div
                    key={key}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr repeat(5, 1fr)",
                      alignItems: "center",
                      padding: "12px 18px",
                      borderBottom:
                        idx < ATTRS.length - 1
                          ? "1px solid var(--border)"
                          : "none",
                    }}
                  >
                    <span
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        fontSize: 13,
                        fontWeight: 500,
                      }}
                    >
                      {label}{" "}
                      {active && source && <InputSourceBadge source={source} />}
                    </span>
                    {BANDS.map((b) => {
                      const isActive = active === b;
                      const color = CLS_COLORS[b];
                      const tooltip = getBandTooltip(key, b);
                      return (
                        <div
                          key={b}
                          style={{ display: "flex", justifyContent: "center" }}
                        >
                          <button
                            onClick={() => handleBandChange(key, b)}
                            disabled={isRunning}
                            title={tooltip}
                            aria-label={`${label}: ${b} - ${tooltip}`}
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
                              boxShadow: isActive
                                ? `0 0 12px color-mix(in oklab, ${color} 45%, transparent)`
                                : "none",
                              transition: "all .14s",
                            }}
                          >
                            {b}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </Card>

            {/* Process Summary Table */}
            {latestResult?.process_summary && (
              <Card pad={0} style={{ overflow: "hidden" }}>
                <div
                  style={{
                    padding: spacing.cardDefault,
                    paddingBottom: 0,
                    marginBottom: 12,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <SectionLabel>Process Summary</SectionLabel>
                    <Pill
                      color="var(--primary)"
                      mono
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 4,
                      }}
                    >
                      <Icon name="bot" size={10} />
                      Generated
                    </Pill>
                  </div>
                </div>

                <div style={{ display: "flex", flexDirection: "column" }}>
                  {/* Activities */}
                  {latestResult.process_summary.key_activities &&
                    latestResult.process_summary.key_activities.length > 0 && (
                      <div
                        style={{
                          padding: "12px 18px",
                          borderBottom: "1px solid var(--border)",
                        }}
                      >
                        <div
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            color: "var(--muted-fg)",
                            textTransform: "uppercase",
                            letterSpacing: 0.5,
                            marginBottom: 8,
                          }}
                        >
                          Key Activities (
                          {latestResult.process_summary.key_activities.length})
                        </div>
                        <ul
                          style={{
                            margin: 0,
                            paddingLeft: 18,
                            display: "flex",
                            flexDirection: "column",
                            gap: 4,
                          }}
                        >
                          {latestResult.process_summary.key_activities.map(
                            (activity, idx) => (
                              <li
                                key={idx}
                                style={{
                                  fontSize: 12,
                                  lineHeight: 1.5,
                                  color: "var(--fg-2)",
                                }}
                              >
                                {activity}
                              </li>
                            ),
                          )}
                        </ul>
                      </div>
                    )}

                  {/* Business Rules */}
                  {latestResult.process_summary.key_logical_points &&
                    latestResult.process_summary.key_logical_points.length >
                      0 && (
                      <div
                        style={{
                          padding: "12px 18px",
                          borderBottom: "1px solid var(--border)",
                        }}
                      >
                        <div
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            color: "var(--muted-fg)",
                            textTransform: "uppercase",
                            letterSpacing: 0.5,
                            marginBottom: 8,
                          }}
                        >
                          Business Rules (
                          {
                            latestResult.process_summary.key_logical_points
                              .length
                          }
                          )
                        </div>
                        <ul
                          style={{
                            margin: 0,
                            paddingLeft: 18,
                            display: "flex",
                            flexDirection: "column",
                            gap: 4,
                          }}
                        >
                          {latestResult.process_summary.key_logical_points.map(
                            (rule, idx) => (
                              <li
                                key={idx}
                                style={{
                                  fontSize: 12,
                                  lineHeight: 1.5,
                                  color: "var(--fg-2)",
                                }}
                              >
                                {rule}
                              </li>
                            ),
                          )}
                        </ul>
                      </div>
                    )}

                  {/* Applications */}
                  {latestResult.process_summary.key_applications &&
                    latestResult.process_summary.key_applications.length >
                      0 && (
                      <div
                        style={{
                          padding: "12px 18px",
                          borderBottom: "1px solid var(--border)",
                        }}
                      >
                        <div
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            color: "var(--muted-fg)",
                            textTransform: "uppercase",
                            letterSpacing: 0.5,
                            marginBottom: 8,
                          }}
                        >
                          Applications (
                          {latestResult.process_summary.key_applications.length}
                          )
                        </div>
                        <div
                          style={{
                            fontSize: 12,
                            lineHeight: 1.5,
                            color: "var(--fg-2)",
                          }}
                        >
                          {latestResult.process_summary.key_applications.join(
                            ", ",
                          )}
                        </div>
                      </div>
                    )}

                  {/* Layouts */}
                  {latestResult.process_summary.key_layouts &&
                    latestResult.process_summary.key_layouts.length > 0 && (
                      <div
                        style={{
                          padding: "12px 18px",
                          borderBottom: "1px solid var(--border)",
                        }}
                      >
                        <div
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            color: "var(--muted-fg)",
                            textTransform: "uppercase",
                            letterSpacing: 0.5,
                            marginBottom: 8,
                          }}
                        >
                          Layouts (
                          {latestResult.process_summary.key_layouts.length})
                        </div>
                        <div
                          style={{
                            fontSize: 12,
                            lineHeight: 1.5,
                            color: "var(--fg-2)",
                          }}
                        >
                          {latestResult.process_summary.key_layouts.join(", ")}
                        </div>
                      </div>
                    )}

                  {/* Technologies */}
                  {latestResult.process_summary.key_additional_technologies &&
                    latestResult.process_summary.key_additional_technologies
                      .length > 0 && (
                      <div style={{ padding: "12px 18px" }}>
                        <div
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            color: "var(--muted-fg)",
                            textTransform: "uppercase",
                            letterSpacing: 0.5,
                            marginBottom: 8,
                          }}
                        >
                          Technologies (
                          {
                            latestResult.process_summary
                              .key_additional_technologies.length
                          }
                          )
                        </div>
                        <div
                          style={{
                            fontSize: 12,
                            lineHeight: 1.5,
                            color: "var(--fg-2)",
                          }}
                        >
                          {latestResult.process_summary.key_additional_technologies.join(
                            ", ",
                          )}
                        </div>
                      </div>
                    )}
                </div>
              </Card>
            )}
          </div>

          {/* ── Right: result panel ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {displayScore ? (
              <>
                {/* Complexity class card - matching exploration S2Result (stage2.jsx line 47) */}
                <Card
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 12,
                    paddingTop: 24,
                    background: `linear-gradient(160deg, color-mix(in oklab, ${CLS_COLORS[displayScore.complexity_class as Band]} 12%, var(--surface)), var(--surface) 75%)`,
                  }}
                >
                  <SectionLabel>Complexity class</SectionLabel>
                  <ComplexityChip
                    cls={displayScore.complexity_class as Band}
                    size={76}
                  />
                  <div
                    style={{ display: "flex", alignItems: "baseline", gap: 8 }}
                  >
                    <span
                      style={{
                        fontFamily: "var(--mono)",
                        fontSize: 30,
                        fontWeight: 700,
                      }}
                    >
                      {displayScore.total_score}
                    </span>
                    <span style={{ fontSize: 13, color: "var(--muted-fg)" }}>
                      / 28 pts
                    </span>
                  </div>
                  {/* Score scale ladder - matching exploration stage2.jsx line 56 */}
                  <div style={{ width: "100%", marginTop: 4 }}>
                    <div
                      style={{
                        display: "flex",
                        height: 8,
                        borderRadius: 99,
                        overflow: "hidden",
                        gap: 2,
                      }}
                    >
                      {BANDS.map((k) => (
                        <div
                          key={k}
                          style={{
                            flex: k === displayScore.complexity_class ? 1.6 : 1,
                            background:
                              k === displayScore.complexity_class
                                ? CLS_COLORS[k]
                                : "var(--track)",
                            transition: "flex .3s, background .3s",
                          }}
                        />
                      ))}
                    </div>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        marginTop: 6,
                        fontSize: 9.5,
                        color: "var(--muted-fg)",
                        fontFamily: "var(--mono)",
                      }}
                    >
                      {BANDS.map((k) => (
                        <span
                          key={k}
                          style={{
                            color:
                              k === displayScore.complexity_class
                                ? CLS_COLORS[k]
                                : "var(--muted-fg)",
                            fontWeight:
                              k === displayScore.complexity_class ? 700 : 400,
                          }}
                        >
                          {k}
                        </span>
                      ))}
                    </div>
                  </div>
                </Card>

                {/* Effort estimate card */}
                <Card>
                  <SectionLabel style={{ marginBottom: 12 }}>
                    Effort estimate
                  </SectionLabel>
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 14,
                    }}
                  >
                    {/* Weeks range */}
                    <div>
                      <div
                        style={{
                          fontSize: 11,
                          color: "var(--muted-fg)",
                          marginBottom: 6,
                        }}
                      >
                        Development weeks
                      </div>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "baseline",
                          gap: 6,
                        }}
                      >
                        {displayScore.effort_min_weeks !==
                        displayScore.effort_max_weeks ? (
                          <>
                            <span
                              style={{
                                fontFamily: "var(--mono)",
                                fontSize: 22,
                                fontWeight: 700,
                              }}
                            >
                              {displayScore.effort_min_weeks}
                            </span>
                            <span
                              style={{ fontSize: 14, color: "var(--muted-fg)" }}
                            >
                              –
                            </span>
                          </>
                        ) : (
                          ""
                        )}
                        <span
                          style={{
                            fontFamily: "var(--mono)",
                            fontSize: 22,
                            fontWeight: 700,
                          }}
                        >
                          {displayScore.effort_max_weeks}
                        </span>
                        <span
                          style={{ fontSize: 13, color: "var(--muted-fg)" }}
                        >
                          weeks
                        </span>
                      </div>
                    </div>

                    {/* Sprint count */}
                    <div>
                      <div
                        style={{
                          fontSize: 11,
                          color: "var(--muted-fg)",
                          marginBottom: 6,
                        }}
                      >
                        Sprint estimate
                      </div>
                      <div
                        style={{
                          fontFamily: "var(--mono)",
                          fontSize: 18,
                          fontWeight: 700,
                        }}
                      >
                        {displayScore.sprint_min === displayScore.sprint_max
                          ? `${displayScore.sprint_max}`
                          : `${displayScore.sprint_min ?? "?"}–${displayScore.sprint_max ?? "?"}`}
                        <span
                          style={{ fontSize: 13, color: "var(--muted-fg)" }}
                        >
                          &nbsp;sprints
                        </span>
                      </div>
                    </div>
                  </div>
                </Card>

                {/* Source section - show document info if available */}
                {latestResult?.document_metadata && (
                  <Card style={{ display: "flex", flexDirection: "column" }}>
                    <div style={{ marginBottom: 12 }}>
                      <SectionLabel>Source</SectionLabel>
                    </div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                      }}
                    >
                      <Icon
                        name="layers"
                        size={16}
                        style={{ color: "var(--primary)" }}
                      />
                      <div
                        style={{
                          fontSize: 12.5,
                          fontWeight: 500,
                          color: "var(--fg)",
                        }}
                      >
                        {latestResult.document_metadata.original_filename}
                      </div>
                    </div>
                  </Card>
                )}
              </>
            ) : (
              <div
                style={{
                  borderRadius: 14,
                  border: "1px dashed var(--border)",
                  padding: "40px 18px",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 12,
                  color: "var(--muted-foreground)",
                  textAlign: "center",
                }}
              >
                <Icon name="gauge" size={32} style={{ opacity: 0.4 }} />
                <div style={{ fontSize: 12.5 }}>
                  Set all 5 bands to see
                  <br />
                  live score preview
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { RunHistoryDrawer } from "@/components/shared/RunHistoryDrawer";
import { Icon } from "@/components/shared/icons";
import { ArrowLeft } from "lucide-react";
import type { UseCase, StageRun, StageId } from "@/lib/types";

interface StageHeaderProps {
  projectId: string;
  stageNumber: 1 | 2 | 3 | 4;
  stageName: string;
  stageId: StageId;
  ucId: string;
  useCase: UseCase;
  useCases?: UseCase[];
  runs?: StageRun[];
  currentRunId?: string;
  selectedRunId?: string | null;
  selectedRunIndex?: number;
  isComplete?: boolean;
  onNavigatePrev?: () => void;
  onNavigateNext?: () => void;
  onSetCurrentRun?: () => void;
  onSelectRun?: (runId: string) => void;
  actions?: React.ReactNode;
}

export function StageHeader({
  projectId,
  stageNumber,
  stageName,
  stageId,
  ucId,
  useCase,
  useCases = [],
  runs = [],
  currentRunId,
  selectedRunId,
  selectedRunIndex = 0,
  isComplete,
  onNavigatePrev,
  onNavigateNext,
  onSetCurrentRun,
  onSelectRun,
  actions,
}: StageHeaderProps) {
  const router = useRouter();
  const showSwitcher = useCases.length > 1;
  const showRunNav = runs.length > 1 && onNavigatePrev && onNavigateNext;

  return (
    <header className="border-b border-border/50 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
      <div className="flex h-14 items-center justify-between px-6">
        {/* Left: back + divider + name/subtitle */}
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
            {showSwitcher ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      background: "transparent",
                      border: "none",
                      fontSize: 14,
                      fontWeight: 600,
                      color: "var(--foreground)",
                      cursor: "pointer",
                      padding: 0,
                      outline: "none",
                      maxWidth: 260,
                    }}
                  >
                    <span
                      style={{
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        maxWidth: 240,
                      }}
                    >
                      {useCase.name}
                    </span>
                    <Icon
                      name="chevD"
                      size={13}
                      style={{ opacity: 0.5, flexShrink: 0 }}
                    />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  align="start"
                  className="max-h-72 overflow-y-auto"
                >
                  {useCases.map((uc) => (
                    <DropdownMenuItem
                      key={uc.id}
                      onClick={() =>
                        router.push(
                          `/projects/${projectId}/stage${stageNumber}/${uc.id}`,
                        )
                      }
                      style={{ fontWeight: uc.id === ucId ? 600 : 400 }}
                    >
                      {uc.name}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <p className="text-sm font-semibold">{useCase.name}</p>
            )}
            <p className="text-xs text-muted-foreground">
              Stage {stageNumber} — {stageName}
            </p>
          </div>
        </div>

        {/* Right: run nav + current badge + history drawer + actions */}
        <div className="flex items-center gap-2">
          {showRunNav && (
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
                onClick={onNavigatePrev}
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
                onClick={onNavigateNext}
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
                background: "color-mix(in oklab, var(--c-green) 12%, transparent)",
                border:
                  "1px solid color-mix(in oklab, var(--c-green) 28%, transparent)",
              }}
            >
              <Icon name="check" size={12} /> Current
            </span>
          )}

          {selectedRunId && selectedRunId !== currentRunId && onSetCurrentRun && (
            <Button size="sm" variant="outline" onClick={onSetCurrentRun}>
              <Icon name="check" size={13} style={{ marginRight: 6 }} />
              Set as Current
            </Button>
          )}

          {runs.length > 0 && (
            <RunHistoryDrawer
              runs={runs}
              stage={stageId}
              stageName={`Stage ${stageNumber} - ${stageName}`}
              useCaseId={ucId}
              currentRunId={currentRunId}
              selectedRunId={selectedRunId || currentRunId || undefined}
              onSelectRun={onSelectRun}
            />
          )}

          {actions}
        </div>
      </div>
    </header>
  );
}

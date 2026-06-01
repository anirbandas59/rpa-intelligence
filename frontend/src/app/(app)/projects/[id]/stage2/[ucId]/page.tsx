"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { InputSourceBadge } from "@/components/shared/InputSourceBadge"
import { StalenessIndicator } from "@/components/shared/StalenessIndicator"
import { AsyncRunProgress } from "@/components/shared/AsyncRunProgress"
import { RunHistoryDrawer } from "@/components/shared/RunHistoryDrawer"
import { ArrowLeft, Upload, Play, Loader2 } from "lucide-react"
import { apiGet, apiPost, apiPatch, apiPostFormData, isAuthenticated } from "@/lib/api"
import { scoreComplexity, getComplexityColor, hasAllBands, WEIGHTS } from "@/lib/scoring"
import type { UseCase, StageRun, Band, AttributeBands, ReadinessResponse, S2Result, InputSource } from "@/lib/types"
import { cn } from "@/lib/utils"

export default function Stage2Page() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.id as string
  const ucId = params.ucId as string

  const [useCase, setUseCase] = useState<UseCase | null>(null)
  const [bands, setBands] = useState<Partial<AttributeBands>>({})
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null)
  const [runs, setRuns] = useState<StageRun[]>([])
  const [latestResult, setLatestResult] = useState<S2Result | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploadingFile, setUploadingFile] = useState(false)
  const [runningStage, setRunningStage] = useState(false)
  const [error, setError] = useState("")

  const bandOptions: Band[] = ["XS", "S", "M", "L", "XL"]
  const attributes: Array<keyof AttributeBands> = [
    "activities",
    "business_rules",
    "layouts",
    "interfaces",
    "technology",
  ]

  const liveScore = hasAllBands(bands as AttributeBands)
    ? scoreComplexity(bands as AttributeBands)
    : null

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/auth/login")
      return
    }

    const fetchData = async () => {
      try {
        const [ucData, readinessData, runsData] = await Promise.all([
          apiGet<UseCase>(`/api/v1/use-cases/${ucId}`),
          apiGet<ReadinessResponse>(`/api/v1/use-cases/${ucId}/readiness`),
          apiGet<StageRun[]>(`/api/v1/use-cases/${ucId}/s2/runs`),
        ])

        setUseCase(ucData)
        setReadiness(readinessData)
        setRuns(runsData)

        if (ucData.s2_inputs?.bands) {
          setBands(ucData.s2_inputs.bands as Partial<AttributeBands>)
        }

        if (ucData.s2_latest_run_id && runsData.length > 0) {
          const latestRun = runsData.find((r) => r.id === ucData.s2_latest_run_id)
          if (latestRun?.status === "complete") {
            setLatestResult(latestRun.result as unknown as S2Result)
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load data")
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [ucId, router])

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploadingFile(true)
    setError("")

    try {
      const formData = new FormData()
      formData.append("file", file)
      await apiPostFormData(`/api/v1/use-cases/${ucId}/s2/documents`, formData)
      alert("File uploaded successfully. Run Stage 2 to extract complexity attributes.")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setUploadingFile(false)
    }
  }

  const handleBandChange = async (attribute: keyof AttributeBands, value: Band) => {
    const newBands = { ...bands, [attribute]: value }
    setBands(newBands)

    try {
      await apiPatch(`/api/v1/use-cases/${ucId}/s2/inputs`, {
        bands: {
          [attribute]: value,
          [`${attribute}_source`]: "manual",
        },
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update input")
    }
  }

  const handleRunStage = async () => {
    setRunningStage(true)
    setError("")

    try {
      await apiPost(`/api/v1/use-cases/${ucId}/s2/runs`, {})
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run")
      setRunningStage(false)
    }
  }

  const handleRunComplete = () => {
    setRunningStage(false)
    window.location.reload()
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  if (!useCase) {
    return (
      <div className="min-h-screen bg-background p-8">
        <Alert variant="destructive">
          <AlertDescription>Use case not found</AlertDescription>
        </Alert>
      </div>
    )
  }

  const isStale = readiness?.s2 === "stale"
  const isRunning = readiness?.s2 === "running" || runningStage

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border/50 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="container flex h-14 items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href={`/projects/${projectId}`}>
              <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground -ml-2">
                <ArrowLeft className="mr-1.5 h-4 w-4" />
                Back
              </Button>
            </Link>
            <div className="h-4 w-px bg-border/50" />
            <div>
              <p className="text-sm font-semibold">{useCase.name}</p>
              <p className="text-xs text-muted-foreground">Stage 2 — Complexity Analysis</p>
            </div>
          </div>
          <RunHistoryDrawer runs={runs} stage="s2" stageName="Stage 2 - Complexity" />
        </div>
      </header>

      <div className="container max-w-5xl py-8 space-y-6">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {isStale && <StalenessIndicator isStale={true} stageName="Stage 2" />}

        {isRunning && (
          <AsyncRunProgress
            useCaseId={ucId}
            stage="s2"
            onComplete={handleRunComplete}
            onError={(err) => setError(err)}
          />
        )}

        {/* Upload card */}
        <Card className="glass-card border-border/50">
          <CardHeader>
            <CardTitle>Input Method</CardTitle>
            <CardDescription>
              Upload a process document for AI extraction, or manually enter complexity bands
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Label
              htmlFor="file-upload"
              className="flex h-28 cursor-pointer items-center justify-center rounded-xl border-2 border-dashed border-primary/20 hover:border-primary/40 transition-colors bg-primary/5"
            >
              <div className="space-y-1.5 text-center">
                <Upload className="mx-auto h-7 w-7 text-primary/60" />
                <div className="text-sm font-medium text-muted-foreground">
                  {uploadingFile ? "Uploading..." : "Upload Process Document"}
                </div>
                <div className="text-xs text-muted-foreground/60">.pdf or .docx</div>
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
          </CardContent>
        </Card>

        {/* Attributes card */}
        <Card className="glass-card border-border/50">
          <CardHeader>
            <CardTitle>Complexity Attributes</CardTitle>
            <CardDescription>
              Select the band for each attribute (AI-extracted values can be corrected)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {loading
                ? attributes.map((attr) => (
                    <div key={attr} className="flex items-center gap-4">
                      <Skeleton className="h-4 w-36" />
                      <Skeleton className="h-10 flex-1 rounded-lg" />
                    </div>
                  ))
                : attributes.map((attr) => (
                    <div key={attr} className="flex items-center gap-4">
                      <Label className="w-40 capitalize text-sm shrink-0">
                        {attr.replace("_", " ")}
                      </Label>
                      <Select
                        value={bands[attr] || ""}
                        onValueChange={(val) => handleBandChange(attr, val as Band)}
                        disabled={isRunning}
                      >
                        <SelectTrigger className="flex-1 h-10">
                          <SelectValue placeholder="Select band..." />
                        </SelectTrigger>
                        <SelectContent>
                          {bandOptions.map((band) => (
                            <SelectItem key={band} value={band}>
                              {band} — weight {WEIGHTS[attr][band]}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {bands[attr] && (
                        <InputSourceBadge
                          source={(useCase.s2_inputs?.[`${attr}_source`] as InputSource) || "manual"}
                        />
                      )}
                    </div>
                  ))}
            </div>

            {/* Live score preview */}
            {liveScore && (
              <div className="mt-6 rounded-xl gradient-hero border border-border/50 p-5 space-y-3">
                <h4 className="text-sm font-semibold">Live Preview</h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Total Score</div>
                    <div className="text-2xl font-bold">{liveScore.total_score}/28</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Complexity</div>
                    <Badge
                      className={cn(
                        "text-base px-3 py-1",
                        getComplexityColor(liveScore.complexity_class),
                        (liveScore.complexity_class === "L" || liveScore.complexity_class === "XL") &&
                          "glow-primary"
                      )}
                    >
                      {liveScore.complexity_class}
                    </Badge>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Effort</div>
                    <div className="font-bold">
                      {liveScore.effort_min_weeks === liveScore.effort_max_weeks
                        ? `${liveScore.effort_min_weeks} weeks`
                        : `${liveScore.effort_min_weeks}–${liveScore.effort_max_weeks} weeks`}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Sprints</div>
                    <div className="font-bold">{liveScore.sprints}</div>
                  </div>
                </div>
              </div>
            )}

            <div className="mt-6">
              <Button
                onClick={handleRunStage}
                disabled={isRunning || !hasAllBands(bands as AttributeBands)}
                className={hasAllBands(bands as AttributeBands) ? "glow-primary" : ""}
              >
                <Play className="mr-2 h-4 w-4" />
                {isRunning ? "Running..." : "Run Complexity Analysis"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Latest results */}
        {latestResult && (
          <Card className="glass-card border-border/50">
            <CardHeader>
              <CardTitle>Latest Results</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-lg bg-muted/30 p-4">
                  <div className="text-xs text-muted-foreground mb-1">Total Score</div>
                  <div className="text-2xl font-bold">{latestResult.total_score}/28</div>
                </div>
                <div className="rounded-lg bg-muted/30 p-4">
                  <div className="text-xs text-muted-foreground mb-1">Complexity Class</div>
                  <Badge className={`text-lg px-3 py-1 ${getComplexityColor(latestResult.complexity_class)}`}>
                    {latestResult.complexity_class}
                  </Badge>
                </div>
                <div className="rounded-lg bg-muted/30 p-4">
                  <div className="text-xs text-muted-foreground mb-1">Effort Estimate</div>
                  <div className="text-2xl font-bold">
                    {latestResult.effort_min_weeks === latestResult.effort_max_weeks
                      ? `${latestResult.effort_min_weeks}w`
                      : `${latestResult.effort_min_weeks}–${latestResult.effort_max_weeks}w`}
                  </div>
                </div>
              </div>

              <div className="mt-5">
                <h4 className="text-sm font-semibold mb-3">Attribute Weights</h4>
                <div className="grid grid-cols-5 gap-2 text-sm">
                  {Object.entries(latestResult.attribute_weights).map(([attr, weight]) => (
                    <div
                      key={attr}
                      className="rounded-lg glass-card border border-border/50 p-3 text-center"
                    >
                      <div className="text-[10px] text-muted-foreground capitalize mb-1">
                        {attr.replace("_", " ")}
                      </div>
                      <div className="font-bold text-primary">{weight as number}</div>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

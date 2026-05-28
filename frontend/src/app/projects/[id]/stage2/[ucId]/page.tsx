"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Select } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { InputSourceBadge } from "@/components/shared/InputSourceBadge"
import { StalenessIndicator } from "@/components/shared/StalenessIndicator"
import { AsyncRunProgress } from "@/components/shared/AsyncRunProgress"
import { RunHistoryDrawer } from "@/components/shared/RunHistoryDrawer"
import { ArrowLeft, Upload, FileText, Play, Loader2 } from "lucide-react"
import { apiGet, apiPost, apiPatch, apiPostFormData, isAuthenticated } from "@/lib/api"
import { scoreComplexity, getComplexityColor, hasAllBands, WEIGHTS } from "@/lib/scoring"
import type { UseCase, StageRun, Band, AttributeBands, ReadinessResponse, S2Result, InputSource } from "@/lib/types"

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

        // Load bands from inputs
        if (ucData.s2_inputs?.bands) {
          setBands(ucData.s2_inputs.bands)
        }

        // Load latest result if complete
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
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  if (!useCase) {
    return (
      <div className="min-h-screen bg-muted/50 p-8">
        <Alert variant="destructive">
          <AlertDescription>Use case not found</AlertDescription>
        </Alert>
      </div>
    )
  }

  const isStale = readiness?.s2 === "stale"
  const isRunning = readiness?.s2 === "running" || runningStage

  return (
    <div className="min-h-screen bg-muted/50">
      <div className="border-b bg-background">
        <div className="container flex h-16 items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href={`/projects/${projectId}`}>
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
            </Link>
            <div className="h-6 w-px bg-border" />
            <div>
              <h1 className="text-sm font-semibold">{useCase.name}</h1>
              <p className="text-xs text-muted-foreground">Stage 2: Complexity Analysis</p>
            </div>
          </div>
          <RunHistoryDrawer runs={runs} stage="s2" stageName="Stage 2 - Complexity" />
        </div>
      </div>

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

        <Card>
          <CardHeader>
            <CardTitle>Input Method</CardTitle>
            <CardDescription>
              Upload a process document for AI extraction, or manually enter complexity bands
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-4">
              <Label
                htmlFor="file-upload"
                className="flex h-32 flex-1 cursor-pointer items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/25 transition-colors hover:border-muted-foreground/50"
              >
                <div className="space-y-2 text-center">
                  <Upload className="mx-auto h-8 w-8 text-muted-foreground" />
                  <div className="text-sm font-medium">
                    {uploadingFile ? "Uploading..." : "Upload Process Document"}
                  </div>
                  <div className="text-xs text-muted-foreground">.pdf or .docx</div>
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
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Complexity Attributes</CardTitle>
            <CardDescription>
              Select the band for each attribute (AI-extracted values can be corrected)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {attributes.map((attr) => (
                <div key={attr} className="flex items-center gap-4">
                  <Label className="w-40 capitalize">{attr.replace("_", " ")}</Label>
                  <select
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    value={bands[attr] || ""}
                    onChange={(e) => handleBandChange(attr, e.target.value as Band)}
                    disabled={isRunning}
                  >
                    <option value="">Select...</option>
                    {bandOptions.map((band) => (
                      <option key={band} value={band}>
                        {band} (Weight: {WEIGHTS[attr][band]})
                      </option>
                    ))}
                  </select>
                  {bands[attr] && (
                    <InputSourceBadge source={(useCase.s2_inputs?.[`${attr}_source`] as InputSource) || "manual"} />
                  )}
                </div>
              ))}
            </div>

            {liveScore && (
              <div className="mt-6 rounded-lg bg-muted p-4 space-y-2">
                <h4 className="font-semibold text-sm">Live Preview</h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Total Score:</span>{" "}
                    <span className="font-bold">{liveScore.total_score}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Complexity:</span>{" "}
                    <Badge className={getComplexityColor(liveScore.complexity_class)}>
                      {liveScore.complexity_class}
                    </Badge>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Effort:</span>{" "}
                    <span className="font-bold">
                      {liveScore.effort_min_weeks === liveScore.effort_max_weeks
                        ? `${liveScore.effort_min_weeks} weeks`
                        : `${liveScore.effort_min_weeks}-${liveScore.effort_max_weeks} weeks`}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Sprints:</span>{" "}
                    <span className="font-bold">{liveScore.sprints}</span>
                  </div>
                </div>
              </div>
            )}

            <div className="mt-6">
              <Button onClick={handleRunStage} disabled={isRunning || !hasAllBands(bands as AttributeBands)}>
                <Play className="mr-2 h-4 w-4" />
                {isRunning ? "Running..." : "Run Complexity Analysis"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {latestResult && (
          <Card>
            <CardHeader>
              <CardTitle>Latest Results</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-3">
                <div>
                  <div className="text-sm text-muted-foreground">Total Score</div>
                  <div className="text-2xl font-bold">{latestResult.total_score}/28</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">Complexity Class</div>
                  <div>
                    <Badge className={`text-lg ${getComplexityColor(latestResult.complexity_class)}`}>
                      {latestResult.complexity_class}
                    </Badge>
                  </div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">Effort Estimate</div>
                  <div className="text-2xl font-bold">
                    {latestResult.effort_min_weeks === latestResult.effort_max_weeks
                      ? `${latestResult.effort_min_weeks} weeks`
                      : `${latestResult.effort_min_weeks}-${latestResult.effort_max_weeks} weeks`}
                  </div>
                </div>
              </div>

              <div className="mt-4">
                <h4 className="text-sm font-semibold mb-2">Attribute Weights</h4>
                <div className="grid grid-cols-5 gap-2 text-sm">
                  {Object.entries(latestResult.attribute_weights).map(([attr, weight]) => (
                    <div key={attr} className="rounded bg-muted p-2 text-center">
                      <div className="text-xs text-muted-foreground capitalize">
                        {attr.replace("_", " ")}
                      </div>
                      <div className="font-bold">{weight}</div>
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

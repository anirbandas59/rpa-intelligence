"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { PageHeader } from "@/components/shared/PageHeader"
import {
  ArrowLeft,
  User,
  Sliders,
  Bot,
  FileCode,
  Users,
  Brain,
  ExternalLink,
  Loader2,
  Shield,
} from "lucide-react"
import { apiGet, isAuthenticated, getUserEmail } from "@/lib/api"
import type { User as UserType, WeightConfig } from "@/lib/types"

export default function SettingsPage() {
  const router = useRouter()
  const [user, setUser] = useState<UserType | null>(null)
  const [weightConfigs, setWeightConfigs] = useState<WeightConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/auth/login")
      return
    }

    const fetchData = async () => {
      try {
        const userData = await apiGet<UserType>("/api/v1/auth/me")
        setUser(userData)

        // Load weight configs (available to all users for their projects)
        try {
          const wc = await apiGet<WeightConfig[]>("/api/v1/settings/weight-configs")
          setWeightConfigs(wc)
        } catch {
          // not critical
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load settings")
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [router])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  const isSuperuser = user?.role === "superuser"

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border/50 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex h-14 items-center gap-3 px-6">
          <Link href="/projects">
            <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground -ml-2">
              <ArrowLeft className="mr-1.5 h-4 w-4" />
              Projects
            </Button>
          </Link>
          <div className="h-4 w-px bg-border/50" />
          <h1 className="font-semibold text-sm">Settings</h1>
        </div>
      </header>

      <PageHeader
        title="Settings"
        subtitle="Platform configuration and agent memory management."
      />

      <div className="py-6 px-7 space-y-6">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Profile section */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <User className="h-4 w-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground/70">
              Profile
            </h2>
          </div>
          <Card className="glass-card border-border/50">
            <CardContent className="pt-6 space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Email</Label>
                  <div className="font-medium">{user?.email || getUserEmail()}</div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    variant="outline"
                    className={
                      isSuperuser
                        ? "border-primary/40 text-primary bg-primary/10"
                        : "border-border/50 text-muted-foreground"
                    }
                  >
                    {isSuperuser && <Shield className="h-3 w-3 mr-1" />}
                    {user?.role || "user"}
                  </Badge>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="display-email">Email Address</Label>
                  <Input
                    id="display-email"
                    value={user?.email || ""}
                    disabled
                    className="bg-muted/20"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="role-display">Role</Label>
                  <Input
                    id="role-display"
                    value={user?.role || "user"}
                    disabled
                    className="bg-muted/20"
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </section>

        {/* Weight Configuration */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <Sliders className="h-4 w-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground/70">
              Weight Configuration
            </h2>
          </div>
          <Card className="glass-card border-border/50">
            <CardHeader>
              <CardTitle className="text-base">Complexity Scoring Weights</CardTitle>
              <CardDescription>
                Each project can have a custom weight configuration for complexity scoring. The default
                configuration uses the standard weight matrix.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {weightConfigs.length === 0 ? (
                <div className="text-sm text-muted-foreground py-2">
                  No custom weight configurations. Using platform defaults.
                </div>
              ) : (
                <div className="space-y-2">
                  {weightConfigs.map((wc) => (
                    <div
                      key={wc.id}
                      className="flex items-center justify-between rounded-lg border border-border/50 bg-muted/20 px-4 py-3"
                    >
                      <div>
                        <div className="text-sm font-medium">{wc.name}</div>
                        <div className="text-xs text-muted-foreground">
                          Threshold: {wc.yes_threshold} · Created {new Date(wc.created_at).toLocaleDateString()}
                        </div>
                      </div>
                      {wc.is_active && (
                        <Badge className="bg-green-500/20 text-green-400 border-green-500/30">Active</Badge>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </section>

        {/* Agent Memory */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <Brain className="h-4 w-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground/70">
              Agent Memory
            </h2>
          </div>
          <Card className="glass-card border-border/50">
            <CardHeader>
              <CardTitle className="text-base">Assessment Memory</CardTitle>
              <CardDescription>
                Agent Memory stores past assessment results to improve future scoring accuracy.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground leading-relaxed">
                Memories are automatically created after each completed stage run. The orchestrator uses
                these memories to provide context-aware scoring and avoid repeating the same analysis on
                similar process patterns.
              </p>
              <div className="rounded-lg gradient-hero border border-border/50 p-4 space-y-1">
                <div className="text-sm font-medium">How it works</div>
                <ul className="text-xs text-muted-foreground space-y-1 list-disc list-inside">
                  <li>Stage 1 results are stored after each assessment run</li>
                  <li>Stage 2 complexity patterns are indexed by process type</li>
                  <li>The orchestrator retrieves similar past results before each new run</li>
                  <li>Memories do not affect deterministic scoring — only AI-generated narratives</li>
                </ul>
              </div>
              <Link href="/projects">
                <Button variant="outline" size="sm">
                  <ExternalLink className="mr-2 h-4 w-4" />
                  View Projects
                </Button>
              </Link>
            </CardContent>
          </Card>
        </section>

        {/* Superuser sections */}
        {isSuperuser && (
          <>
            <div className="pt-2">
              <div className="flex items-center gap-2 mb-1">
                <Shield className="h-4 w-4 text-primary" />
                <span className="text-xs font-semibold uppercase tracking-widest text-primary/70">
                  Superuser Controls
                </span>
              </div>
              <p className="text-xs text-muted-foreground mb-4">
                These settings are only visible to superuser accounts.
              </p>
            </div>

            {/* LLM Config */}
            <section>
              <div className="flex items-center gap-2 mb-3">
                <Bot className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground/70">
                  LLM Configuration
                </h2>
              </div>
              <Card className="glass-card border-primary/20">
                <CardHeader>
                  <CardTitle className="text-base">Model & Parameter Settings</CardTitle>
                  <CardDescription>
                    Configure the AI models used for each stage. Changes affect all future runs.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {[
                      { stage: "S1", task: "Migration Assessment", model: "claude-haiku-4-5" },
                      { stage: "S2", task: "Document Extraction", model: "claude-haiku-4-5" },
                      { stage: "S3", task: "Narrative Summary", model: "claude-sonnet-4-5" },
                      { stage: "S4", task: "Feature Decomposition", model: "claude-sonnet-4-5" },
                    ].map((item) => (
                      <div
                        key={item.stage}
                        className="flex items-center justify-between rounded-lg border border-border/50 bg-muted/20 px-4 py-3"
                      >
                        <div>
                          <div className="text-sm font-medium">{item.task}</div>
                          <div className="text-xs text-muted-foreground">{item.stage}</div>
                        </div>
                        <Badge
                          variant="outline"
                          className="font-mono text-xs border-primary/30 text-primary/80"
                        >
                          {item.model}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </section>

            {/* Prompt Variants */}
            <section>
              <div className="flex items-center gap-2 mb-3">
                <FileCode className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground/70">
                  Prompt Variants
                </h2>
              </div>
              <Card className="glass-card border-primary/20">
                <CardHeader>
                  <CardTitle className="text-base">Active Prompt Variants</CardTitle>
                  <CardDescription>
                    Manage which prompt variant is active for each stage. All prompts live in
                    <code className="mx-1 rounded bg-muted/50 px-1 text-xs">backend/prompts/</code>.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-sm text-muted-foreground">
                    Prompt management is available via the backend admin API. Use{" "}
                    <code className="rounded bg-muted/50 px-1 text-xs">GET /api/v1/settings/prompt-variants</code>{" "}
                    to list and update active variants.
                  </div>
                </CardContent>
              </Card>
            </section>

            {/* User Management */}
            <section>
              <div className="flex items-center gap-2 mb-3">
                <Users className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground/70">
                  User Management
                </h2>
              </div>
              <Card className="glass-card border-primary/20">
                <CardHeader>
                  <CardTitle className="text-base">Platform Users</CardTitle>
                  <CardDescription>Manage user accounts and role assignments.</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-sm text-muted-foreground">
                    User management is available via{" "}
                    <code className="rounded bg-muted/50 px-1 text-xs">GET /api/v1/settings/users</code>.
                    A full UI is planned for a future phase.
                  </div>
                </CardContent>
              </Card>
            </section>
          </>
        )}
      </div>
    </div>
  )
}

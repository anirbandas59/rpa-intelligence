"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Card, Btn } from "@/components/rpa"
import { spacing } from "@/lib/design-tokens"
import { apiPost, setAuthToken, setUserEmail } from "@/lib/api"
import type { AuthResponse } from "@/lib/types"

export default function RegisterPage() {
  const router = useRouter()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    if (password !== confirmPassword) {
      setError("Passwords do not match")
      return
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters")
      return
    }

    setLoading(true)

    try {
      const response = await apiPost<AuthResponse>("/api/v1/auth/register", {
        email,
        password,
      })

      setAuthToken(response.access_token)
      setUserEmail(email)
      router.push("/projects")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/50 p-4">
      <Card
        pad={spacing.cardLarge}
        style={{ width: "100%", maxWidth: 440 }}
      >
        <div style={{ marginBottom: spacing.gapDefault }}>
          <h1 style={{ fontSize: 26, fontWeight: 700, marginBottom: 8 }}>
            Create an account
          </h1>
          <p style={{ fontSize: 12.8, color: "var(--muted-foreground)" }}>
            Enter your details to get started
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: spacing.gapDefault }}>
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={loading}
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirmPassword">Confirm Password</Label>
            <Input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              disabled={loading}
            />
          </div>

          <Btn type="submit" style={{ width: "100%" }} disabled={loading}>
            {loading ? "Creating account..." : "Create account"}
          </Btn>

          <div style={{ textAlign: "center", fontSize: 12.8, color: "var(--muted-foreground)" }}>
            Already have an account?{" "}
            <Link href="/auth/login" className="text-primary hover:underline">
              Sign in
            </Link>
          </div>
        </form>
      </Card>
    </div>
  )
}

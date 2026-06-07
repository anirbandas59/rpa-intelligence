"use client"

import { useEffect, useState } from "react"
import { Card } from "@/components/rpa/Card"
import { SectionLabel } from "@/components/rpa/SectionLabel"
import { Icon } from "@/components/rpa/Icon"
import { spacing } from "@/lib/design-tokens"
import { apiGet } from "@/lib/api"
import { toast } from "sonner"
import type { BulkUploadStatusResponse } from "@/lib/types"

interface ProcessingStepProps {
  uploadId: string
  onComplete: () => void
}

export function ProcessingStep({ uploadId, onComplete }: ProcessingStepProps) {
  const [status, setStatus] = useState<BulkUploadStatusResponse | null>(null)

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await apiGet<BulkUploadStatusResponse>(
          `/api/v1/projects/use-cases/bulk-upload/${uploadId}/status`
        )
        setStatus(res)

        if (res.status === "complete") {
          clearInterval(interval)
          toast.success(
            `Created ${res.created_count} use cases, ${res.assessed_count || 0} assessments complete`
          )
          // Delay before closing to let user see final state
          setTimeout(() => {
            onComplete()
          }, 1500)
        } else if (res.status === "failed") {
          clearInterval(interval)
          toast.error(res.error || "Upload failed")
        }
      } catch (error: any) {
        clearInterval(interval)
        toast.error(error.message || "Failed to fetch status")
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [uploadId, onComplete])

  const creationProgress = status
    ? ((status.created_count || 0) / status.total_count) * 100
    : 0

  const assessmentProgress = status
    ? ((status.assessed_count || 0) / status.total_count) * 100
    : 0

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: spacing.gapDefault }}>
      <SectionLabel>Processing Import</SectionLabel>

      <Card pad={spacing.cardDefault}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Creation progress */}
          <div>
            <div
              style={{
                fontSize: 12.5,
                fontWeight: 600,
                marginBottom: 8,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              {status?.status === "complete" ? (
                <Icon name="check" size={14} style={{ color: "var(--c-green)" }} />
              ) : (
                <div
                  style={{
                    width: 7,
                    height: 7,
                    borderRadius: 99,
                    background: "var(--primary)",
                    animation: "rpaPulse 1.6s ease-in-out infinite",
                  }}
                />
              )}
              Creating use cases
            </div>
            <div
              style={{
                width: "100%",
                height: 8,
                borderRadius: 99,
                background: "var(--border)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${creationProgress}%`,
                  height: "100%",
                  background: "var(--c-teal)",
                  transition: "width 0.3s ease",
                }}
              />
            </div>
            <div style={{ fontSize: 11, color: "var(--muted-fg)", marginTop: 4 }}>
              {status?.created_count || 0} of {status?.total_count || 0} created
            </div>
          </div>

          {/* Assessment progress */}
          <div>
            <div
              style={{
                fontSize: 12.5,
                fontWeight: 600,
                marginBottom: 8,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              {assessmentProgress === 100 ? (
                <Icon name="check" size={14} style={{ color: "var(--c-green)" }} />
              ) : (
                <div
                  style={{
                    width: 7,
                    height: 7,
                    borderRadius: 99,
                    background: "var(--c-violet)",
                    animation: "rpaPulse 1.6s ease-in-out infinite",
                  }}
                />
              )}
              Running Stage 1 assessments
            </div>
            <div
              style={{
                width: "100%",
                height: 8,
                borderRadius: 99,
                background: "var(--border)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${assessmentProgress}%`,
                  height: "100%",
                  background: "var(--c-violet)",
                  transition: "width 0.3s ease",
                }}
              />
            </div>
            <div style={{ fontSize: 11, color: "var(--muted-fg)", marginTop: 4 }}>
              {status?.assessed_count || 0} of {status?.total_count || 0} assessed
            </div>
          </div>
        </div>
      </Card>

      <div
        style={{
          fontSize: 11.5,
          color: "var(--muted-fg)",
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        <Icon name="info" size={14} />
        Processing in background. You can close this dialog and check progress later.
      </div>
    </div>
  )
}

"use client"

import { useState } from "react"
import { Card } from "@/components/rpa/Card"
import { Btn } from "@/components/rpa/Btn"
import { SectionLabel } from "@/components/rpa/SectionLabel"
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select"
import { spacing } from "@/lib/design-tokens"
import { apiPut, apiPost } from "@/lib/api"
import { toast } from "sonner"
import type { BulkUploadResponse, ColumnMapping, BulkConfirmResponse } from "@/lib/types"

interface ColumnMappingStepProps {
  session: BulkUploadResponse
  onMapped: () => void
}

export function ColumnMappingStep({ session, onMapped }: ColumnMappingStepProps) {
  const [mapping, setMapping] = useState<ColumnMapping>({
    name: null,
    description: null,
    source_platform: null,
    install_status: null,
  })
  const [confirming, setConfirming] = useState(false)

  const handleConfirm = async () => {
    if (!mapping.name) {
      toast.error("Please select a column for Use Case Name")
      return
    }
    if (!mapping.description) {
      toast.error("Please select a column for Description")
      return
    }

    setConfirming(true)
    try {
      // Update mapping
      await apiPut(`/api/v1/projects/use-cases/bulk-upload/${session.upload_id}/mapping`, {
        column_mapping: mapping,
        edited_rows: null,
      })

      // Confirm and start processing
      await apiPost<BulkConfirmResponse>(
        `/api/v1/projects/use-cases/bulk-upload/${session.upload_id}/confirm`,
        {}
      )

      toast.success("Processing started")
      onMapped()
    } catch (error: any) {
      toast.error(error.message || "Failed to start processing")
    } finally {
      setConfirming(false)
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: spacing.gapDefault }}>
      <SectionLabel>Map Columns to Fields</SectionLabel>

      <Card pad={spacing.cardDefault}>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div
              style={{
                fontSize: 10.5,
                fontWeight: 700,
                textTransform: "uppercase",
                marginBottom: 8,
                color: "var(--muted-fg)",
              }}
            >
              Use Case Name (required)
            </div>
            <Select
              value={mapping.name || undefined}
              onValueChange={(v) => setMapping({ ...mapping, name: v })}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select column..." />
              </SelectTrigger>
              <SelectContent>
                {session.columns.map((col) => (
                  <SelectItem key={col} value={col}>
                    {col}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <div
              style={{
                fontSize: 10.5,
                fontWeight: 700,
                textTransform: "uppercase",
                marginBottom: 8,
                color: "var(--muted-fg)",
              }}
            >
              Description (required)
            </div>
            <Select
              value={mapping.description || undefined}
              onValueChange={(v) =>
                setMapping({ ...mapping, description: v })
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select column..." />
              </SelectTrigger>
              <SelectContent>
                {session.columns.map((col) => (
                  <SelectItem key={col} value={col}>
                    {col}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <div
              style={{
                fontSize: 10.5,
                fontWeight: 700,
                textTransform: "uppercase",
                marginBottom: 8,
                color: "var(--muted-fg)",
              }}
            >
              Source Platform (optional)
            </div>
            <Select
              value={mapping.source_platform || undefined}
              onValueChange={(v) =>
                setMapping({ ...mapping, source_platform: v })
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="None" />
              </SelectTrigger>
              <SelectContent>
                {session.columns.map((col) => (
                  <SelectItem key={col} value={col}>
                    {col}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <div
              style={{
                fontSize: 10.5,
                fontWeight: 700,
                textTransform: "uppercase",
                marginBottom: 8,
                color: "var(--muted-fg)",
              }}
            >
              Install Status (optional)
            </div>
            <Select
              value={mapping.install_status || undefined}
              onValueChange={(v) =>
                setMapping({ ...mapping, install_status: v })
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="None" />
              </SelectTrigger>
              <SelectContent>
                {session.columns.map((col) => (
                  <SelectItem key={col} value={col}>
                    {col}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </Card>

      <SectionLabel>Preview · {session.row_count} rows total</SectionLabel>

      <div style={{ fontSize: 11.5, color: "var(--muted-fg)", marginBottom: 8 }}>
        Showing first {session.preview.length} of {session.row_count} rows
      </div>

      <Card
        pad={0}
        style={{
          overflow: "hidden",
          maxHeight: 600,
        }}
      >
        <div
          style={{
            overflowY: "auto",
            maxHeight: 600,
          }}
        >
          {session.preview.map((row, rowIndex) => (
            <div
              key={rowIndex}
              style={{
                padding: "16px",
                borderBottom: rowIndex < session.preview.length - 1 ? "1px solid var(--border)" : "none",
              }}
            >
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <tbody>
                  {session.columns.map((col) => (
                    <tr key={col}>
                      <td
                        style={{
                          padding: "6px 0",
                          fontSize: 10.5,
                          fontWeight: 700,
                          textTransform: "uppercase",
                          color: "var(--muted-fg)",
                          verticalAlign: "top",
                          width: "140px",
                        }}
                      >
                        {col}
                      </td>
                      <td
                        style={{
                          padding: "6px 0 6px 16px",
                          fontSize: 12.5,
                          wordBreak: "break-word",
                        }}
                      >
                        {row[col] || (
                          <span style={{ color: "var(--muted-fg)" }}>—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      </Card>

      <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
        <Btn
          variant="default"
          onClick={handleConfirm}
          disabled={!mapping.name || !mapping.description || confirming}
        >
          {confirming ? "Processing..." : "Confirm & Import"}
        </Btn>
      </div>
    </div>
  )
}

"use client"

import { useState } from "react"
import { Card } from "@/components/rpa/Card"
import { Icon } from "@/components/rpa/Icon"
import { spacing } from "@/lib/design-tokens"
import { apiPostFormData } from "@/lib/api"
import { toast } from "sonner"
import type { BulkUploadResponse } from "@/lib/types"

interface FileUploadStepProps {
  projectId: string
  onUpload: (session: BulkUploadResponse) => void
}

export function FileUploadStep({ projectId, onUpload }: FileUploadStepProps) {
  const [uploading, setUploading] = useState(false)
  const [dragActive, setDragActive] = useState(false)

  const handleFile = async (file: File) => {
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append("file", file)

      const response = await apiPostFormData<BulkUploadResponse>(
        `/api/v1/projects/${projectId}/use-cases/bulk-upload`,
        formData
      )

      onUpload(response)
      toast.success(`Uploaded ${response.row_count} rows`)
    } catch (error: any) {
      console.error("Upload error:", error)
      let errorMsg = "Upload failed"

      try {
        if (error?.body) {
          const parsed = JSON.parse(error.body)
          errorMsg = parsed?.detail || error.message
        } else {
          errorMsg = error.message
        }
      } catch {
        errorMsg = error.message || "Upload failed"
      }

      toast.error(errorMsg)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: spacing.gapDefault }}>
      <Card
        pad={spacing.cardLarge}
        style={{
          border: dragActive
            ? "2px dashed var(--primary)"
            : "2px dashed var(--border)",
          background: dragActive
            ? "color-mix(in oklab, var(--primary) 5%, transparent)"
            : "var(--surface)",
          textAlign: "center",
          cursor: "pointer",
        }}
        onDragEnter={() => setDragActive(true)}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragActive(false)
          const file = e.dataTransfer.files[0]
          if (file) handleFile(file)
        }}
        onDragOver={(e) => e.preventDefault()}
        onClick={() => document.getElementById("file-input")?.click()}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 12,
          }}
        >
          <Icon
            name="upload"
            size={32}
            style={{ color: "var(--muted-fg)" }}
          />
          <div style={{ fontSize: 13.5, fontWeight: 600 }}>
            {uploading ? "Uploading..." : "Drop file here or click to browse"}
          </div>
          <div style={{ fontSize: 11.5, color: "var(--muted-fg)" }}>
            Supports CSV and XLSX files
          </div>
        </div>
        <input
          id="file-input"
          type="file"
          accept=".csv,.xlsx"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) handleFile(file)
          }}
          style={{ display: "none" }}
        />
      </Card>
    </div>
  )
}

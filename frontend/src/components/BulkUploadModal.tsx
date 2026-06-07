"use client"

import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { spacing } from "@/lib/design-tokens"
import { FileUploadStep } from "@/components/bulk-upload/FileUploadStep"
import { ColumnMappingStep } from "@/components/bulk-upload/ColumnMappingStep"
import { ProcessingStep } from "@/components/bulk-upload/ProcessingStep"
import type { BulkUploadResponse } from "@/lib/types"

interface BulkUploadModalProps {
  projectId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function BulkUploadModal({
  projectId,
  open,
  onOpenChange,
}: BulkUploadModalProps) {
  const [step, setStep] = useState<"upload" | "map" | "processing">("upload")
  const [uploadSession, setUploadSession] = useState<BulkUploadResponse | null>(null)

  const handleUpload = (session: BulkUploadResponse) => {
    setUploadSession(session)
    setStep("map")
  }

  const handleMapped = () => {
    setStep("processing")
  }

  const handleComplete = () => {
    // Reset state and close modal
    setStep("upload")
    setUploadSession(null)
    onOpenChange(false)
    // Reload page to show new use cases
    window.location.reload()
  }

  const handleClose = () => {
    // Reset state when closing
    setStep("upload")
    setUploadSession(null)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent
        className="max-w-5xl max-h-[90vh] flex flex-col"
        style={{ padding: spacing.cardLarge }}
      >
        <DialogHeader>
          <DialogTitle
            style={{
              fontSize: 10.5,
              fontWeight: 700,
              letterSpacing: 1.4,
              textTransform: "uppercase",
              color: "var(--muted-foreground)",
            }}
          >
            Bulk Import Use Cases
          </DialogTitle>
          <DialogDescription className="sr-only">
            Upload CSV or XLSX file to import multiple use cases at once
          </DialogDescription>
        </DialogHeader>

        <div
          className="flex-1 overflow-y-auto"
          style={{
            marginTop: spacing.gapDefault,
            paddingRight: 4,
          }}
        >
          {step === "upload" && (
            <FileUploadStep projectId={projectId} onUpload={handleUpload} />
          )}

          {step === "map" && uploadSession && (
            <ColumnMappingStep session={uploadSession} onMapped={handleMapped} />
          )}

          {step === "processing" && uploadSession && (
            <ProcessingStep
              uploadId={uploadSession.upload_id}
              onComplete={handleComplete}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

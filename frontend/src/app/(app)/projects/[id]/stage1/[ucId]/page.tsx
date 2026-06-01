"use client"

export default function Stage1Page({
  params,
}: {
  params: { id: string; ucId: string }
}) {
  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold gradient-text">Migration Assessment</h1>
        <p className="text-muted-foreground mt-1">Stage 1 — Evaluate RPA use-cases for migration readiness</p>
      </div>
      <p className="text-muted-foreground">Stage 1 assessment content — coming soon.</p>
    </div>
  )
}

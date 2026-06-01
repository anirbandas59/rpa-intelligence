"use client"

/**
 * AgentActivityFeed - live SSE event stream display for orchestrator runs
 */

import { useEffect, useRef, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { ChevronDown, ChevronUp, Wifi, WifiOff, Activity } from "lucide-react"
import { cn } from "@/lib/utils"
import { useAgentStream, type AgentEvent, type AgentEventType } from "@/lib/hooks/useAgentStream"

interface AgentActivityFeedProps {
  useCaseId: string
  sessionId: string | null
  className?: string
}

const EVENT_STYLES: Record<
  AgentEventType,
  { label: string; className: string; badge?: string }
> = {
  thinking: {
    label: "Thinking",
    className: "text-muted-foreground text-xs italic",
  },
  tool_call: {
    label: "Tool Call",
    className: "text-primary text-xs font-mono",
    badge: "bg-primary/20 text-primary border-primary/30",
  },
  tool_result: {
    label: "Result",
    className: "text-green-400 text-xs font-mono",
  },
  decision: {
    label: "Decision",
    className: "text-violet-400 text-xs font-semibold",
  },
  correction: {
    label: "Correction",
    className: "text-amber-400 text-xs",
  },
  error: {
    label: "Error",
    className: "text-destructive text-xs font-medium",
  },
  needs_input: {
    label: "Input Needed",
    className: "text-amber-300 text-xs",
  },
  complete: {
    label: "Complete",
    className: "text-green-300 text-sm font-semibold",
  },
  ping: {
    label: "",
    className: "hidden",
  },
}

function EventRow({ event }: { event: AgentEvent }) {
  const style = EVENT_STYLES[event.type]
  if (event.type === "ping") return null

  if (event.type === "complete") {
    return (
      <div className="rounded-md border border-green-500/30 bg-green-500/10 px-3 py-2 text-green-300 text-sm font-semibold flex items-center gap-2 my-1">
        <span className="h-1.5 w-1.5 rounded-full bg-green-400" />
        Orchestration complete
      </div>
    )
  }

  if (event.type === "needs_input") {
    return (
      <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 my-1">
        <div className="text-amber-400 text-xs font-semibold mb-1">Input Needed</div>
        <div className="text-amber-300 text-xs">{event.content}</div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-2 py-0.5">
      {style.badge ? (
        <Badge
          className={cn(
            "text-[10px] px-1.5 py-0 h-4 shrink-0 border font-mono",
            style.badge
          )}
        >
          {style.label}
        </Badge>
      ) : (
        <span className="text-[10px] text-muted-foreground/50 w-14 shrink-0 pt-0.5 text-right">
          {style.label}
        </span>
      )}
      <span className={style.className}>
        {event.type === "thinking" && "... "}
        {event.content}
      </span>
    </div>
  )
}

export function AgentActivityFeed({
  useCaseId,
  sessionId,
  className,
}: AgentActivityFeedProps) {
  const [collapsed, setCollapsed] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const { events, isConnected, error } = useAgentStream(useCaseId, sessionId)

  // Auto-scroll to bottom on new events
  useEffect(() => {
    if (!collapsed) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }
  }, [events, collapsed])

  if (!sessionId) return null

  return (
    <div className={cn("glass-card rounded-xl border border-border/50", className)}>
      {/* Header */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center justify-between px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold">Agent Activity</span>
          <span className="text-xs text-muted-foreground">
            {events.length} event{events.length !== 1 ? "s" : ""}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {isConnected ? (
            <Wifi className="h-3.5 w-3.5 text-green-400" />
          ) : (
            <WifiOff className="h-3.5 w-3.5 text-muted-foreground" />
          )}
          {collapsed ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
      </button>

      {/* Feed */}
      {!collapsed && (
        <div className="border-t border-border/50 px-4 py-3 max-h-64 overflow-y-auto space-y-0.5">
          {error && (
            <div className="text-destructive text-xs mb-2">{error}</div>
          )}
          {events.length === 0 && (
            <div className="text-muted-foreground text-xs py-2">
              Waiting for agent activity...
            </div>
          )}
          {events.map((event) => (
            <EventRow key={event.id} event={event} />
          ))}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  )
}

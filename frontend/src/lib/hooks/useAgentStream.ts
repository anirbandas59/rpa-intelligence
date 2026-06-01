"use client"

import { useEffect, useRef, useState } from "react"

export type AgentEventType =
  | "thinking"
  | "tool_call"
  | "tool_result"
  | "decision"
  | "correction"
  | "error"
  | "needs_input"
  | "complete"
  | "ping"

export interface AgentEvent {
  id: string
  type: AgentEventType
  content: string
  timestamp: number
}

interface UseAgentStreamResult {
  events: AgentEvent[]
  isConnected: boolean
  error: string | null
}

const MAX_EVENTS = 50

export function useAgentStream(
  useCaseId: string,
  sessionId: string | null
): UseAgentStreamResult {
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    // Clean up previous connection
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }

    if (!sessionId) {
      setEvents([])
      setIsConnected(false)
      return
    }

    const apiBase =
      typeof window !== "undefined"
        ? (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
        : "http://localhost:8000"

    const token =
      typeof window !== "undefined" ? localStorage.getItem("token") : null

    const url = `${apiBase}/api/v1/use-cases/${useCaseId}/agent-stream?session_id=${sessionId}${token ? `&token=${token}` : ""}`

    const es = new EventSource(url)
    esRef.current = es

    es.onopen = () => {
      setIsConnected(true)
      setError(null)
    }

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as {
          type: AgentEventType
          content: string
        }

        // Ignore keep-alive pings
        if (data.type === "ping") return

        const agentEvent: AgentEvent = {
          id: `${Date.now()}-${Math.random()}`,
          type: data.type,
          content: data.content,
          timestamp: Date.now(),
        }

        setEvents((prev) => {
          const next = [...prev, agentEvent]
          return next.length > MAX_EVENTS ? next.slice(next.length - MAX_EVENTS) : next
        })
      } catch {
        // Ignore parse errors for malformed events
      }
    }

    es.onerror = () => {
      setIsConnected(false)
      setError("Connection to agent stream lost")
      es.close()
    }

    return () => {
      es.close()
      esRef.current = null
      setIsConnected(false)
    }
  }, [useCaseId, sessionId])

  return { events, isConnected, error }
}

/**
 * StageCard - hub card for each stage showing status and summary
 */

import Link from "next/link"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import type { ReadinessStatus } from "@/lib/types"
import { CheckCircle2, Circle, Loader2, AlertCircle, ArrowRight } from "lucide-react"

interface StageCardProps {
  stageId: string
  title: string
  description: string
  status: ReadinessStatus
  stats?: Array<{ label: string; value: string | number }>
  href: string
  className?: string
}

const STATUS_CONFIG: Record<
  ReadinessStatus,
  {
    icon: React.ComponentType<{ className?: string }>
    label: string
    color: string
    dotColor: string
  }
> = {
  not_ready: {
    icon: Circle,
    label: "Not Ready",
    color: "text-muted-foreground",
    dotColor: "bg-muted-foreground",
  },
  ready: {
    icon: Circle,
    label: "Ready",
    color: "text-blue-600 dark:text-blue-400",
    dotColor: "bg-blue-600 dark:bg-blue-400",
  },
  running: {
    icon: Loader2,
    label: "Running",
    color: "text-purple-600 dark:text-purple-400 animate-spin",
    dotColor: "bg-purple-600 dark:bg-purple-400 animate-pulse",
  },
  complete: {
    icon: CheckCircle2,
    label: "Complete",
    color: "text-green-600 dark:text-green-400",
    dotColor: "bg-green-600 dark:bg-green-400",
  },
  stale: {
    icon: AlertCircle,
    label: "Stale",
    color: "text-amber-600 dark:text-amber-400",
    dotColor: "bg-amber-600 dark:bg-amber-400",
  },
}

export function StageCard({
  stageId,
  title,
  description,
  status,
  stats,
  href,
  className = "",
}: StageCardProps) {
  const config = STATUS_CONFIG[status]
  const Icon = config.icon

  return (
    <Card className={`transition-all hover:shadow-md ${className}`}>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <CardTitle className="text-lg">{title}</CardTitle>
              <Badge variant="outline" className="text-xs">
                {stageId.toUpperCase()}
              </Badge>
            </div>
            <CardDescription>{description}</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full ${config.dotColor}`} />
            <Icon className={`h-4 w-4 ${config.color}`} />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {stats && stats.length > 0 && (
            <div className="grid grid-cols-2 gap-3 text-sm">
              {stats.map((stat, idx) => (
                <div key={idx} className="space-y-1">
                  <div className="text-muted-foreground">{stat.label}</div>
                  <div className="font-semibold">{stat.value}</div>
                </div>
              ))}
            </div>
          )}
          <Link href={href}>
            <Button className="w-full" variant={status === "not_ready" ? "outline" : "default"}>
              {status === "not_ready" ? "Configure" : status === "running" ? "View Progress" : "View"}
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}

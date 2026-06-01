/**
 * EmptyState - centered empty state with icon, title, description, optional action
 */

interface EmptyStateProps {
  icon: React.ReactNode
  title: string
  description: string
  action?: React.ReactNode
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="gradient-hero rounded-2xl border border-border/50 py-20 px-8 flex flex-col items-center justify-center text-center">
      <div className="h-16 w-16 rounded-full bg-muted/60 flex items-center justify-center mb-5 text-muted-foreground">
        {icon}
      </div>
      <h3 className="text-2xl font-semibold mb-2">{title}</h3>
      <p className="text-muted-foreground max-w-sm mb-6">{description}</p>
      {action && <div>{action}</div>}
    </div>
  )
}

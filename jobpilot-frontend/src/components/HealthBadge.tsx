import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/api/client'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

type Health = { status: string; db: boolean }

export function HealthBadge() {
  const { data, isError, isPending } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<Health>('/api/health'),
    refetchInterval: 15_000,
  })

  let label = 'Checking API'
  let tone = 'bg-muted-foreground/40'
  if (isError) {
    label = 'API down'
    tone = 'bg-destructive'
  } else if (!isPending && data) {
    if (data.db) {
      label = 'API OK'
      tone = 'bg-status-ok'
    } else {
      label = 'Database not connected'
      tone = 'bg-status-warn'
    }
  }

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span role="img" aria-label={label} className="flex size-6 items-center justify-center" />
        }
      >
        <span className={`size-2.5 rounded-full ${tone}`} />
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

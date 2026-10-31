import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ListChecks } from 'lucide-react'
import { EmptyState } from '@/components/EmptyState'
import { Skeleton } from '@/components/ui/skeleton'
import { listByStatus, setStatus } from '@/api/jobs'

export const STAGES = ['shortlisted', 'applied', 'interview', 'offer', 'rejected'] as const

export function TrackerView() {
  const qc = useQueryClient()
  const jobs = useQuery({ queryKey: ['jobs', 'tracker'], queryFn: () => listByStatus([...STAGES]) })
  const move = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => setStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  })
  if (jobs.isLoading) return <Skeleton className="m-4 h-40" />
  const items = jobs.data?.items ?? []
  if (items.length === 0)
    return (
      <EmptyState
        icon={ListChecks}
        title="Nothing tracked yet"
        description="Open a job and set its status to Shortlisted or Applied to track it here."
      />
    )
  return (
    <div className="grid gap-3 p-4 md:grid-cols-5">
      {STAGES.map((stage) => (
        <section key={stage} aria-label={stage}>
          <h2 className="mb-2 text-sm font-medium capitalize">
            {stage} ({items.filter((j) => j.status === stage).length})
          </h2>
          <ul className="space-y-2">
            {items
              .filter((j) => j.status === stage)
              .map((j) => (
                <li key={j.id} className="rounded-md border p-2 text-sm">
                  <div className="font-medium">{j.title}</div>
                  <div className="text-muted-foreground">{j.company}</div>
                  <select
                    aria-label={`Status of ${j.title}`}
                    className="mt-1 h-8 w-full rounded border bg-background text-xs"
                    value={j.status}
                    onChange={(e) => move.mutate({ id: j.id, status: e.target.value })}
                  >
                    {STAGES.map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                    <option value="new">back to new</option>
                  </select>
                </li>
              ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

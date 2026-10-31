import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { ApiError } from '@/api/client'
import { listCompanies } from '@/api/directory'
import { type Candidate, type Run, cancelRun, checkByInput, findCareers, getRun } from '@/api/jobs'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'

const isUrl = (s: string) => /^https?:\/\//i.test(s.trim())

export function CheckCompanyDialog({
  open,
  onOpenChange,
  onDone,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  onDone: (companyId?: number) => void
}) {
  const qc = useQueryClient()
  const [input, setInput] = useState('')
  const [name, setName] = useState('')
  const [runs, setRuns] = useState<Run[]>([])
  const [error, setError] = useState<string | null>(null)
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const running = runs.some((r) => r.status === 'running')

  const suggestions = useQuery({
    queryKey: ['companies', input],
    queryFn: () => listCompanies(input),
    enabled: open && !!input.trim() && !isUrl(input),
  })

  useEffect(() => {
    if (!runs.length || !running) return
    const t = setInterval(async () => {
      const next = await Promise.all(runs.map((r) => getRun(r.id)))
      setRuns(next)
      if (next.every((r) => r.status !== 'running')) {
        const failed = next.find((r) => r.status === 'failed')
        const found = next.reduce((n, r) => n + (r.stats.kept ?? 0), 0)
        const added = next.reduce((n, r) => n + (r.stats.new ?? 0), 0)
        if (failed) toast.error(`${failed.company}: ${failed.error}`)
        else toast.success(`${next[0].company}: ${found} jobs, ${added} new`)
        qc.invalidateQueries({ queryKey: ['jobs'] })
        qc.invalidateQueries({ queryKey: ['companies'] })
        onDone()
      }
    }, 1500)
    return () => clearInterval(t)
  }, [runs, running, qc, onDone])

  async function start() {
    setError(null)
    try {
      const body = isUrl(input)
        ? { url: input.trim(), company_name: name }
        : { company_name: input }
      const res = await checkByInput(body)
      setRuns(res.runs)
    } catch (e) {
      const d = e instanceof ApiError ? e.detail : null
      if (d === 'company_not_found') {
        setError('Not in your list — searching for its careers page…')
        try {
          const found = await findCareers(input)
          setCandidates(found)
          setError(
            found.length
              ? 'Not in your list. Pick its careers page:'
              : 'Nothing found. Paste its careers link instead and give the company name.',
          )
        } catch {
          setError('Search failed. Paste its careers link instead and give the company name.')
        }
      } else if (d === 'company_name_required') setError('Enter the company name for this link.')
      else if (d === 'no_sources')
        setError('This company has no careers link yet. Add one on Companies.')
      else if (d && typeof d === 'object' && 'code' in d) setError('A check is already running.')
      else setError(e instanceof Error ? e.message : 'Failed')
    }
  }

  const phase = runs[0]?.phase
  return (
    <Dialog open={open} onOpenChange={(o) => !running && onOpenChange(o)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Check company</DialogTitle>
          <DialogDescription>
            Type a company from your list, or paste a careers link.
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault()
            if (input.trim() && !running) start()
          }}
        >
          <Input
            list="company-suggestions"
            placeholder="Company name or careers link"
            aria-label="Company name or careers link"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={running}
            autoFocus
          />
          <datalist id="company-suggestions">
            {(suggestions.data ?? []).slice(0, 8).map((c) => (
              <option key={c.id} value={c.name} />
            ))}
          </datalist>
          {isUrl(input) && (
            <Input
              placeholder="Company name"
              aria-label="Company name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
          {candidates.map((c) => (
            <button
              type="button"
              key={c.url}
              className="block w-full rounded-md border p-2 text-left text-sm hover:bg-accent"
              onClick={async () => {
                setCandidates([])
                setError(null)
                try {
                  setRuns((await checkByInput({ url: c.url, company_name: input })).runs)
                } catch (e) {
                  setError(e instanceof Error ? e.message : 'Failed')
                }
              }}
            >
              <span className="font-medium">{c.title || c.url}</span>{' '}
              <span className="text-muted-foreground">({c.ats_type})</span>
              <div className="truncate text-muted-foreground">{c.url}</div>
            </button>
          ))}
          {running ? (
            <div className="flex items-center justify-between text-sm">
              <span>Working… ({phase})</span>
              <Button
                type="button"
                variant="outline"
                onClick={() => runs.forEach((r) => cancelRun(r.id))}
              >
                Cancel
              </Button>
            </div>
          ) : (
            <Button type="submit" disabled={!input.trim()}>
              Check
            </Button>
          )}
        </form>
      </DialogContent>
    </Dialog>
  )
}

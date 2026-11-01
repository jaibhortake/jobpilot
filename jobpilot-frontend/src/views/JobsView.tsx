import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Briefcase, ExternalLink, Search, ThumbsDown, ThumbsUp } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import {
  type Job,
  aiMatch,
  coverLetter,
  dismissJob,
  setStatus,
  getJob,
  hideSimilar,
  listJobs,
  setDescription,
  setFeedback,
} from '@/api/jobs'
import { EmptyState } from '@/components/EmptyState'
import { CheckCompanyDialog } from '@/components/jobs/CheckCompanyDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { isTypingTarget } from '@/lib/hotkeys'

const GENERIC = new Set([
  'engineer',
  'software',
  'developer',
  'i',
  'ii',
  'iii',
  'intern',
  'the',
  'and',
  'of',
  'for',
  'with',
  'jr',
  'junior',
  'associate',
  'graduate',
  'trainee',
  'new',
  'india',
  'remote',
])

function ScoreChip({ job }: { job: Job }) {
  if (job.filtered) return <Badge variant="outline">Filtered</Badge>
  if (job.score === null) return null
  const tone =
    job.score >= 70
      ? 'bg-green-600 text-white'
      : job.score >= 40
        ? 'bg-amber-500 text-black'
        : 'bg-red-600 text-white'
  return <Badge className={tone}>{job.score}</Badge>
}

const fmt = (iso: string) => new Date(iso).toLocaleDateString()
const when = (j: Job) =>
  j.date_known && j.posted_at ? fmt(j.posted_at) : `first seen ${fmt(j.first_seen_at)}`

function JobPanel({ id, onDismissed }: { id: number; onDismissed: () => void }) {
  const qc = useQueryClient()
  const job = useQuery({ queryKey: ['job', id], queryFn: () => getJob(id) })
  const [text, setText] = useState('')
  const dismiss = useMutation({ mutationFn: () => dismissJob(id), onSuccess: onDismissed })
  const paste = useMutation({
    mutationFn: () => setDescription(id, text),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['job', id] }),
  })
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['job', id] })
    qc.invalidateQueries({ queryKey: ['jobs'] })
  }
  const thumb = useMutation({
    mutationFn: (v: 1 | -1 | null) => setFeedback(id, v),
    onSuccess: refresh,
  })
  const hide = useMutation({
    mutationFn: () => hideSimilar(id, hideWords),
    onSuccess: () => {
      toast.success('Hidden — similar jobs are filtered')
      refresh()
    },
  })
  const status = useMutation({
    mutationFn: (s: string) => setStatus(id, s),
    onSuccess: refresh,
  })
  const ai = useMutation({
    mutationFn: () => aiMatch(id),
    onSuccess: refresh,
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed'),
  })
  const [letterText, setLetterText] = useState('')
  const letter = useMutation({
    mutationFn: () => coverLetter(id),
    onSuccess: (r) => setLetterText(r.text),
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed'),
  })
  if (job.isLoading || !job.data) return <Skeleton className="m-4 h-40" />
  const j = job.data
  // after a thumbs-down, offer the title's distinctive words to hide
  const hideWords =
    j.feedback === -1
      ? (j.title
          .toLowerCase()
          .match(/[a-z0-9+#.]+/g)
          ?.filter((w) => !GENERIC.has(w))
          .slice(0, 3) ?? [])
      : []
  return (
    <div className="space-y-3 p-4">
      <div>
        <h2 className="text-lg font-semibold">{j.title}</h2>
        <p className="text-sm text-muted-foreground">
          {j.company} · {j.location ?? 'Location n/a'}
          {j.remote ? ' · Remote' : ''} · {when(j)}
        </p>
      </div>
      <div className="flex gap-2">
        {j.url && /^https?:\/\//.test(j.url) && (
          <Button render={<a href={j.url} target="_blank" rel="noreferrer" />}>
            <ExternalLink /> Open posting
          </Button>
        )}
        <select
          aria-label="Set status"
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={j.status}
          onChange={(e) => status.mutate(e.target.value)}
        >
          {['new', 'shortlisted', 'applied', 'interview', 'offer', 'rejected', 'dismissed'].map(
            (s) => (
              <option key={s}>{s}</option>
            ),
          )}
        </select>
        <Button variant="outline" onClick={() => dismiss.mutate()}>
          Dismiss
        </Button>
        <Button variant="outline" onClick={() => ai.mutate()} disabled={ai.isPending}>
          {ai.isPending ? 'Qwen is reading… (can take a minute)' : 'AI match'}
        </Button>
        <Button variant="outline" onClick={() => letter.mutate()} disabled={letter.isPending}>
          {letter.isPending ? 'Writing…' : 'Cover letter'}
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <ScoreChip job={j} />
        <Button
          variant={j.feedback === 1 ? 'default' : 'outline'}
          size="icon"
          aria-label="Good match"
          onClick={() => thumb.mutate(j.feedback === 1 ? null : 1)}
        >
          <ThumbsUp className="size-4" />
        </Button>
        <Button
          variant={j.feedback === -1 ? 'default' : 'outline'}
          size="icon"
          aria-label="Poor match"
          onClick={() => thumb.mutate(j.feedback === -1 ? null : -1)}
        >
          <ThumbsDown className="size-4" />
        </Button>
        {hideWords.length > 0 && (
          <Button variant="outline" size="sm" onClick={() => hide.mutate()}>
            Hide jobs with “{hideWords.join(', ')}”
          </Button>
        )}
      </div>
      {letterText && (
        <Textarea
          aria-label="Cover letter draft"
          rows={10}
          value={letterText}
          onChange={(e) => setLetterText(e.target.value)}
        />
      )}
      {j.reasons.length > 0 && (
        <ul className="list-disc pl-5 text-sm text-muted-foreground">
          {j.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}
      {j.description ? (
        <p className="whitespace-pre-wrap text-sm">{j.description}</p>
      ) : (
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">No description yet. Paste it here:</p>
          <Textarea
            aria-label="Paste job description"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={6}
          />
          <Button variant="outline" disabled={!text.trim()} onClick={() => paste.mutate()}>
            Save description
          </Button>
        </div>
      )}
      {j.events.length > 0 && (
        <div>
          <h3 className="text-sm font-medium">Activity</h3>
          <ul className="text-sm text-muted-foreground">
            {j.events.map((e) => (
              <li key={`${e.at}-${e.to_status}`}>
                {fmt(e.at)} · {e.from_status ?? '—'} → {e.to_status}
                {e.note ? ` (${e.note})` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export function JobsView() {
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [within, setWithin] = useState(0)
  const [minScore, setMinScore] = useState(0)
  const [showFiltered, setShowFiltered] = useState(false)
  const [sort, setSort] = useState<'date' | 'score'>('date')
  const [companyId, setCompanyId] = useState<number | undefined>()
  const [selected, setSelected] = useState<number | null>(null)
  const [checkOpen, setCheckOpen] = useState(false)

  const jobs = useQuery({
    queryKey: ['jobs', q, within, companyId, minScore, showFiltered, sort],
    queryFn: () =>
      listJobs({
        q,
        posted_within_days: within,
        company_id: companyId,
        min_score: minScore,
        include_filtered: showFiltered,
        sort,
      }),
  })
  const items = jobs.data?.items ?? []
  const dismissed = () => {
    setSelected(null)
    qc.invalidateQueries({ queryKey: ['jobs'] })
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTypingTarget(e.target) || checkOpen) return
      const i = items.findIndex((j) => j.id === selected)
      if (e.key === 'ArrowDown') setSelected(items[Math.min(i + 1, items.length - 1)]?.id ?? null)
      else if (e.key === 'ArrowUp') setSelected(items[Math.max(i - 1, 0)]?.id ?? null)
      else if (e.key === 'd' && selected) dismissJob(selected).then(dismissed)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b p-3">
        <div className="relative">
          <Search className="absolute left-2 top-2.5 size-4 text-muted-foreground" />
          <Input
            className="w-56 pl-8"
            placeholder="Search titles"
            aria-label="Search titles"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <select
          aria-label="Posted within"
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={within}
          onChange={(e) => setWithin(Number(e.target.value))}
        >
          <option value={0}>Any date</option>
          <option value={7}>Last 7 days</option>
          <option value={14}>Last 14 days</option>
          <option value={30}>Last 30 days</option>
        </select>
        <select
          aria-label="Sort"
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={sort}
          onChange={(e) => setSort(e.target.value as 'date' | 'score')}
        >
          <option value="date">Newest first</option>
          <option value="score">Best match first</option>
        </select>
        <select
          aria-label="Minimum score"
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={minScore}
          onChange={(e) => setMinScore(Number(e.target.value))}
        >
          <option value={0}>Any score</option>
          <option value={40}>Score 40+</option>
          <option value={60}>Score 60+</option>
          <option value={70}>Score 70+</option>
        </select>
        <label className="flex items-center gap-1 text-sm">
          <input
            type="checkbox"
            checked={showFiltered}
            onChange={(e) => setShowFiltered(e.target.checked)}
          />
          Show filtered
        </label>
        {companyId && (
          <Button variant="outline" size="sm" onClick={() => setCompanyId(undefined)}>
            Clear company filter
          </Button>
        )}
        <div className="ml-auto flex gap-2">
          <Button onClick={() => setCheckOpen(true)}>Check company</Button>
        </div>
      </div>

      {jobs.isLoading ? (
        <Skeleton className="m-4 h-40" />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title="No jobs yet"
          description="Check a company to pull its latest jobs."
          action={<Button onClick={() => setCheckOpen(true)}>Check company</Button>}
        />
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[2fr_3fr]">
          <ul className="min-h-0 overflow-auto border-r" aria-label="Jobs">
            {items.map((j) => (
              <li key={j.id}>
                <button
                  type="button"
                  onClick={() => setSelected(j.id)}
                  className={`w-full border-b p-3 text-left hover:bg-accent ${selected === j.id ? 'bg-accent' : ''}`}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{j.title}</span>
                    {j.is_new && <Badge>NEW</Badge>}
                    <ScoreChip job={j} />
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {j.company} · {j.location ?? 'n/a'} · {when(j)}
                  </div>
                </button>
              </li>
            ))}
          </ul>
          <div className="min-h-0 overflow-auto">
            {selected ? (
              <JobPanel key={selected} id={selected} onDismissed={dismissed} />
            ) : (
              <p className="p-6 text-sm text-muted-foreground">Select a job to see details.</p>
            )}
          </div>
        </div>
      )}

      <CheckCompanyDialog
        open={checkOpen}
        onOpenChange={setCheckOpen}
        onDone={() => setCompanyId(undefined)}
      />
    </div>
  )
}

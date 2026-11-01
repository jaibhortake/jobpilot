import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { type Profile, getLlm, getProfile, putLlm, putProfile, testLlm } from '@/api/jobs'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'

const LIST_FIELDS: { key: keyof Profile; label: string; hint: string }[] = [
  { key: 'role_keywords', label: 'Role keywords', hint: 'Used to search each company' },
  { key: 'locations', label: 'Locations', hint: 'Countries or cities you accept' },
  { key: 'exclude_title_words', label: 'Exclude title words', hint: 'e.g. senior, lead' },
  { key: 'hidden_title_words', label: 'Hidden title words', hint: 'Added by "hide similar"' },
]

function ModelPresets() {
  const qc = useQueryClient()
  const llm = useQuery({ queryKey: ['llm'], queryFn: getLlm })
  const pick = useMutation({
    mutationFn: putLlm,
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['llm'] })
      toast.success(`Using the ${r.active_preset} model preset`)
    },
    onError: () => toast.error('Could not change the model. Is the backend running?'),
  })
  const test = useMutation({
    mutationFn: testLlm,
    onSuccess: (r) =>
      r.ok ? toast.success(`${r.model}: OK (${r.ms} ms)`) : toast.error(`${r.model}: ${r.error}`),
  })
  if (!llm.data) return <Skeleton className="h-24" />
  const { providers } = llm.data
  const blocked = (preset: string) =>
    (preset === 'claude' && !providers.anthropic.configured && 'add ANTHROPIC_API_KEY to .env') ||
    (preset === 'free' && !providers.groq.configured && 'add GROQ_API_KEY to .env') ||
    false
  return (
    <div className="space-y-3 border-t pt-4">
      <h2 className="text-lg font-semibold">AI model</h2>
      <p className="text-sm text-muted-foreground">
        Ollama: {providers.ollama.reachable ? providers.ollama.models.join(', ') : 'not running'}
      </p>
      <div className="grid gap-2 sm:grid-cols-3">
        {Object.entries(llm.data.presets).map(([name, tasks]) => {
          const why = blocked(name)
          const active = llm.data.active_preset === name
          return (
            <div
              key={name}
              className={`rounded-md border p-3 text-sm ${active ? 'border-primary' : ''}`}
            >
              <div className="font-medium capitalize">{name}</div>
              <div className="text-muted-foreground">{tasks.extract}</div>
              {why && <div className="text-destructive">{why}</div>}
              <Button
                className="mt-2"
                size="sm"
                variant={active ? 'default' : 'outline'}
                disabled={!!why}
                onClick={() => pick.mutate(name)}
              >
                {active ? 'Active' : 'Use'}
              </Button>
            </div>
          )
        })}
      </div>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" onClick={() => test.mutate('extract')}>
          Test extract
        </Button>
        <Button variant="outline" size="sm" onClick={() => test.mutate('classify')}>
          Test classify
        </Button>
      </div>
    </div>
  )
}

export function SettingsView() {
  const qc = useQueryClient()
  const profile = useQuery({ queryKey: ['profile'], queryFn: getProfile })
  const [draft, setDraft] = useState<Profile | null>(null)
  useEffect(() => {
    if (profile.data) setDraft(profile.data)
  }, [profile.data])

  const save = useMutation({
    mutationFn: putProfile,
    onSuccess: () => {
      toast.success('Profile saved, jobs re-scored')
      qc.invalidateQueries({ queryKey: ['profile'] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed'),
  })

  if (!draft) return <Skeleton className="m-4 h-60" />
  const csv = (a: string[]) => a.join(', ')
  const parse = (s: string) =>
    s
      .split(',')
      .map((x) => x.trim())
      .filter(Boolean)

  return (
    <div className="max-w-xl space-y-4 p-4">
      <h2 className="text-lg font-semibold">Job-search profile</h2>
      {LIST_FIELDS.map(({ key, label, hint }) => (
        <label key={key} className="block space-y-1 text-sm">
          <span className="font-medium">{label}</span>
          <span className="ml-2 text-muted-foreground">{hint}</span>
          <Input
            aria-label={label}
            value={csv(draft[key] as string[])}
            onChange={(e) => setDraft({ ...draft, [key]: parse(e.target.value) })}
          />
        </label>
      ))}
      <label className="block space-y-1 text-sm">
        <span className="font-medium">Max years of experience you accept</span>
        <Input
          type="number"
          min={0}
          aria-label="Max years"
          className="w-24"
          value={draft.max_experience_years}
          onChange={(e) => setDraft({ ...draft, max_experience_years: Number(e.target.value) })}
        />
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={draft.include_remote}
          onChange={(e) => setDraft({ ...draft, include_remote: e.target.checked })}
        />
        Include remote jobs
      </label>
      <Button onClick={() => save.mutate(draft)} disabled={save.isPending}>
        Save and re-score
      </Button>
      <ModelPresets />
    </div>
  )
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import {
  type Applicant,
  deleteAnswer,
  getApplicant,
  getDetailKeys,
  listAnswers,
  putApplicant,
  saveAnswers,
} from '@/api/apply'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'

const pretty = (key: string) => key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())

function Details() {
  const qc = useQueryClient()
  const applicant = useQuery({ queryKey: ['applicant'], queryFn: getApplicant })
  const keys = useQuery({ queryKey: ['applicant-keys'], queryFn: getDetailKeys })
  const [draft, setDraft] = useState<Applicant | null>(null)
  useEffect(() => {
    if (applicant.data) setDraft(applicant.data)
  }, [applicant.data])
  const save = useMutation({
    mutationFn: putApplicant,
    onSuccess: (a) => {
      qc.setQueryData(['applicant'], a)
      toast.success('Details saved')
    },
    onError: () => toast.error('Could not save. Is the backend running?'),
  })
  if (!draft || !keys.data) return <Skeleton className="h-64" />
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">Your details</h2>
      <p className="text-sm text-muted-foreground">
        The Apply Assist extension fills these into application forms. You always submit yourself.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {keys.data.map((k) => (
          <label key={k} className="space-y-1 text-sm">
            <span>{pretty(k)}</span>
            <Input
              value={draft.details[k] ?? ''}
              onChange={(e) =>
                setDraft({ ...draft, details: { ...draft.details, [k]: e.target.value } })
              }
            />
          </label>
        ))}
      </div>
      <label className="block space-y-1 text-sm">
        <span>Sites where filling is off (comma separated)</span>
        <Input
          value={draft.disabled_sites.join(', ')}
          onChange={(e) => setDraft({ ...draft, disabled_sites: e.target.value.split(',') })}
        />
      </label>
      <Button onClick={() => save.mutate(draft)} disabled={save.isPending}>
        Save details
      </Button>
    </section>
  )
}

function Answers() {
  const qc = useQueryClient()
  const answers = useQuery({ queryKey: ['answers'], queryFn: listAnswers })
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const refresh = () => qc.invalidateQueries({ queryKey: ['answers'] })
  const add = useMutation({
    mutationFn: saveAnswers,
    onSuccess: () => {
      setQuestion('')
      setAnswer('')
      refresh()
    },
    onError: () => toast.error('Could not save the answer'),
  })
  const remove = useMutation({ mutationFn: deleteAnswer, onSuccess: refresh })
  return (
    <section className="space-y-3 border-t pt-4">
      <h2 className="text-lg font-semibold">Saved answers</h2>
      <p className="text-sm text-muted-foreground">
        Answers to form questions. "Save my answers" in the extension adds to this list.
      </p>
      <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
        <Input
          placeholder="Question, e.g. Notice period?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <Textarea
          placeholder="Answer"
          rows={1}
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
        />
        <Button
          variant="outline"
          disabled={!question.trim() || !answer.trim()}
          onClick={() => add.mutate([{ question, answer }])}
        >
          Add
        </Button>
      </div>
      {!answers.data ? (
        <Skeleton className="h-24" />
      ) : answers.data.length === 0 ? (
        <p className="text-sm text-muted-foreground">No saved answers yet.</p>
      ) : (
        <ul className="divide-y rounded-md border">
          {answers.data.map((a) => (
            <li key={a.id} className="flex items-start gap-3 p-3 text-sm">
              <div className="min-w-0 flex-1">
                <div className="font-medium">{a.question}</div>
                <div className="whitespace-pre-wrap text-muted-foreground">{a.answer}</div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Delete answer to ${a.question}`}
                onClick={() => a.id !== null && remove.mutate(a.id)}
              >
                <Trash2 className="size-4" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export function ApplyView() {
  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4">
      <Details />
      <Answers />
    </div>
  )
}

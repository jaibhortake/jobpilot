import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, Pencil, Plus, Search, Trash2, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { ApiError } from '@/api/client'
import {
  type Company,
  type Source,
  addSource,
  createCompany,
  deleteCompany,
  deleteSource,
  importSheet,
  listCompanies,
  renameCompany,
  updateSource,
} from '@/api/directory'
import { type Candidate, findCareers } from '@/api/jobs'
import { EmptyState } from '@/components/EmptyState'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'

const MESSAGES: Record<string, string> = {
  unsafe_url: 'That link must start with http:// or https://',
  duplicate_url: 'That careers link is already in your list',
  duplicate_company: 'That company is already in your list',
}

function checkSummary(s: Source): { text: string; tone: string } {
  if (!s.last_check_at) return { text: 'Not checked', tone: 'text-muted-foreground' }
  const when = new Date(s.last_check_at).toLocaleDateString()
  if (s.last_status === 'ok')
    return { text: `${s.last_kept ?? 0} of ${s.last_found ?? 0} jobs kept · ${when}`, tone: '' }
  const why = s.last_error ? `: ${s.last_error}` : ''
  return { text: `${s.last_status ?? 'failed'}${why} · ${when}`, tone: 'text-destructive' }
}

type LinkDraft = { id: number | null; url: string; removed: boolean }

function CompanyRow({ company, onChanged, onError, onDelete }: {
  company: Company
  onChanged: () => void
  onError: (e: Error) => void
  onDelete: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState(company.name)
  const [links, setLinks] = useState<LinkDraft[]>([])

  function startEdit() {
    setName(company.name)
    setLinks([
      ...company.sources.map((s) => ({ id: s.id, url: s.url, removed: false })),
      { id: null, url: '', removed: false },
    ])
    setEditing(true)
  }
  const setLink = (i: number, patch: Partial<LinkDraft>) =>
    setLinks((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)))

  async function save() {
    setSaving(true)
    try {
      if (name.trim() && name.trim() !== company.name) await renameCompany(company.id, name.trim())
      for (const l of links) {
        const url = l.url.trim()
        const old = company.sources.find((s) => s.id === l.id)
        if (l.id !== null && (l.removed || !url)) await deleteSource(l.id)
        else if (l.id !== null && old && url !== old.url) await updateSource(l.id, url)
        else if (l.id === null && url && !l.removed) await addSource(company.id, url)
      }
      setEditing(false)
    } catch (e) {
      onError(e as Error)
    } finally {
      setSaving(false)
      onChanged() // show whatever was saved before a failure
    }
  }

  const buttons = (
    <div className="flex gap-1">
      {editing ? (
        <>
          <Button size="sm" disabled={saving} onClick={save}>
            Save
          </Button>
          <Button size="sm" variant="outline" disabled={saving} onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </>
      ) : (
        <>
          <Button
            variant="ghost"
            size="icon"
            aria-label={`Edit ${company.name}`}
            onClick={startEdit}
          >
            <Pencil className="size-4" />
          </Button>
          <Button variant="ghost" size="icon" aria-label={`Delete ${company.name}`} onClick={onDelete}>
            <Trash2 className="size-4" />
          </Button>
        </>
      )}
    </div>
  )

  if (editing)
    return (
      <tr className="border-t align-top">
        <td className="py-2">
          <Input
            className="h-8 w-48"
            aria-label={`Name of ${company.name}`}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </td>
        <td className="space-y-1 py-2">
          {links.map((l, i) =>
            l.removed ? null : (
              <div key={l.id ?? 'new'} className="flex gap-1">
                <Input
                  className="h-8 max-w-md"
                  placeholder={l.id === null ? 'Add a careers link' : 'Careers link'}
                  aria-label={l.id === null ? `New careers link for ${company.name}` : `Careers link ${i + 1} of ${company.name}`}
                  value={l.url}
                  onChange={(e) => setLink(i, { url: e.target.value })}
                />
                {l.id !== null && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Remove link ${i + 1} of ${company.name}`}
                    onClick={() => setLink(i, { removed: true })}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                )}
              </div>
            ),
          )}
        </td>
        <td className="py-2">{company.contact_count}</td>
        <td className="py-2">{buttons}</td>
      </tr>
    )

  return (
    <tr className="border-t align-top">
      <td className="py-2 font-medium">{company.name}</td>
      <td className="space-y-1 py-2">
        {company.sources.map((s) => {
          const r = checkSummary(s)
          return (
            <div key={s.id}>
              <div className="flex items-center gap-2">
                <Badge variant="secondary">{s.ats_type}</Badge>
                <a
                  href={s.url}
                  target="_blank"
                  rel="noreferrer"
                  className="max-w-md truncate text-primary hover:underline"
                >
                  {s.url}
                </a>
              </div>
              <div className={`text-xs ${r.tone}`}>{r.text}</div>
            </div>
          )
        })}
        {company.sources.length === 0 && (
          <span className="text-xs text-muted-foreground">No careers link — use the pencil</span>
        )}
      </td>
      <td className="py-2">{company.contact_count}</td>
      <td className="py-2">{buttons}</td>
    </tr>
  )
}

type Proposal = { company: Company; candidates: Candidate[] | null; failed: boolean }

function FindLinks({ companies, onAdded, onError }: {
  companies: Company[]
  onAdded: () => void
  onError: (e: Error) => void
}) {
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [busy, setBusy] = useState(false)
  const missing = companies.filter((c) => c.sources.length === 0 && c.name !== 'Other')

  async function run() {
    setBusy(true)
    setProposals(missing.map((company) => ({ company, candidates: null, failed: false })))
    for (const company of missing) {
      let next: Pick<Proposal, 'candidates' | 'failed'>
      try {
        next = { candidates: await findCareers(company.name), failed: false }
      } catch {
        next = { candidates: [], failed: true }
      }
      setProposals((ps) => ps.map((p) => (p.company.id === company.id ? { ...p, ...next } : p)))
    }
    setBusy(false)
  }

  async function accept(company: Company, url: string) {
    try {
      await addSource(company.id, url)
      setProposals((ps) => ps.filter((p) => p.company.id !== company.id))
      onAdded()
    } catch (e) {
      onError(e as Error)
    }
  }

  if (!missing.length && !proposals.length) return null
  return (
    <details className="rounded-md border p-3" open={proposals.length > 0}>
      <summary className="cursor-pointer text-sm font-medium">
        Find careers links ({missing.length} companies have none)
      </summary>
      <div className="mt-2 space-y-3">
        <Button size="sm" variant="outline" disabled={busy || !missing.length} onClick={run}>
          <Search /> {busy ? 'Searching…' : 'Search for all'}
        </Button>
        {proposals.map(({ company, candidates, failed }) => (
          <div key={company.id} className="text-sm">
            <div className="font-medium">{company.name}</div>
            {candidates === null ? (
              <p className="text-muted-foreground">Searching…</p>
            ) : failed ? (
              <p className="text-destructive">Search failed. Add a Brave API key, or paste a link.</p>
            ) : candidates.length === 0 ? (
              <p className="text-muted-foreground">Nothing found. Use the pencil on its row to paste a link.</p>
            ) : (
              candidates.slice(0, 3).map((c) => (
                <div key={c.url} className="flex items-center gap-2">
                  <Badge variant="secondary">{c.ats_type}</Badge>
                  <span className="max-w-lg truncate text-muted-foreground">{c.url}</span>
                  <Button size="sm" variant="outline" onClick={() => accept(company, c.url)}>
                    Use this
                  </Button>
                </div>
              ))
            )}
          </div>
        ))}
      </div>
    </details>
  )
}

export function CompaniesView() {
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [newName, setNewName] = useState('')
  const [newUrl, setNewUrl] = useState('')
  const [toDelete, setToDelete] = useState<{ id: number; name: string } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const companies = useQuery({ queryKey: ['companies', q], queryFn: () => listCompanies(q) })
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['companies'] })
    qc.invalidateQueries({ queryKey: ['contacts'] })
  }
  const fail = (e: Error) =>
    toast.error(
      e instanceof ApiError && typeof e.detail === 'string'
        ? (MESSAGES[e.detail] ?? e.detail)
        : e.message,
    )

  const add = useMutation({
    mutationFn: createCompany,
    onSuccess: () => {
      setNewName('')
      setNewUrl('')
      refresh()
    },
    onError: fail,
  })
  const remove = useMutation({ mutationFn: deleteCompany, onSuccess: refresh, onError: fail })
  const upload = useMutation({
    mutationFn: importSheet,
    onSuccess: (r) => {
      toast.success(
        `${r.companies_created} companies, ${r.sources_created} links, ${r.contacts_created} emails added`,
      )
      refresh()
    },
    onError: fail,
  })

  const rows = companies.data ?? []
  return (
    <div className="space-y-4 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          className="max-w-xs"
          placeholder="Search companies"
          aria-label="Search companies"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (newName.trim())
              add.mutate({ name: newName, url: newUrl.trim() || undefined })
          }}
        >
          <Input
            placeholder="New company name"
            aria-label="New company name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <Input
            placeholder="Careers link (optional)"
            aria-label="Careers link"
            value={newUrl}
            onChange={(e) => setNewUrl(e.target.value)}
          />
          <Button type="submit" variant="outline">
            <Plus /> Add company
          </Button>
        </form>
        <input
          ref={fileRef}
          type="file"
          accept=".xlsx,.csv"
          hidden
          data-testid="sheet-input"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) upload.mutate(f)
            e.target.value = ''
          }}
        />
        <Button className="ml-auto" onClick={() => fileRef.current?.click()}>
          <Upload /> Import sheet
        </Button>
      </div>

      <FindLinks companies={rows} onAdded={refresh} onError={fail} />

      {companies.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Building2}
          title="No companies yet"
          description="Import your sheet (company, website, HR contacts) or add a company by hand."
        />
      ) : (
        <table className="w-full text-sm">
          <thead className="text-left text-muted-foreground">
            <tr>
              <th className="py-2">Company</th>
              <th>Careers link(s) and last check</th>
              <th>Emails</th>
              <th className="w-10" />
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <CompanyRow
                key={c.id}
                company={c}
                onChanged={refresh}
                onError={fail}
                onDelete={() => setToDelete({ id: c.id, name: c.name })}
              />
            ))}
          </tbody>
        </table>
      )}

      <AlertDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {toDelete?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              This also removes its careers links and email contacts.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => toDelete && remove.mutate(toDelete.id)}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

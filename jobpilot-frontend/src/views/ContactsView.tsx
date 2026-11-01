import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Mail, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { ApiError } from '@/api/client'
import { Textarea } from '@/components/ui/textarea'
import {
  type Company,
  type Contact,
  bulkContacts,
  createContact,
  deleteContact,
  findEmails,
  listCompanies,
  listContacts,
  moveDomain,
} from '@/api/directory'
import { EmptyState } from '@/components/EmptyState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'

const FREE_MAIL = new Set(['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com'])

function BulkPaste({ onDone }: { onDone: () => void }) {
  const [text, setText] = useState('')
  const bulk = useMutation({
    mutationFn: () => bulkContacts(text),
    onSuccess: (r) => {
      toast.success(
        `${r.added} added, ${r.duplicates} already there` +
          (r.by_company.Other ? `, ${r.by_company.Other} under Other` : ''),
      )
      setText('')
      onDone()
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed'),
  })
  return (
    <details className="rounded-md border p-3">
      <summary className="cursor-pointer text-sm font-medium">Paste a list of emails</summary>
      <div className="mt-2 space-y-2">
        <Textarea
          aria-label="Pasted emails"
          rows={5}
          placeholder="Paste as copied from your mail client, e.g. Name <a@b.com>, c@d.com"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          Companies are matched by name from the email domain; anything unmatched goes under
          &quot;Other&quot;. These are stored as verified and teach the email finder.
        </p>
        <Button disabled={!text.trim() || bulk.isPending} onClick={() => bulk.mutate()}>
          Import
        </Button>
      </div>
    </details>
  )
}

function SortOther({ contacts, onDone }: { contacts: Contact[]; onDone: () => void }) {
  const [names, setNames] = useState<Record<string, string>>({})
  const move = useMutation({
    mutationFn: ({ domain, name }: { domain: string; name: string }) => moveDomain(domain, name),
    onSuccess: (r, v) => {
      toast.success(`${r.moved} moved to ${v.name}`)
      onDone()
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed'),
  })
  const counts = new Map<string, number>()
  for (const c of contacts) {
    const domain = c.email.split('@')[1]
    if (c.company === 'Other' && !FREE_MAIL.has(domain))
      counts.set(domain, (counts.get(domain) ?? 0) + 1)
  }
  if (!counts.size) return null
  return (
    <details className="rounded-md border p-3">
      <summary className="cursor-pointer text-sm font-medium">
        Sort &quot;Other&quot; emails ({counts.size} domains)
      </summary>
      <ul className="mt-2 space-y-1">
        {[...counts].map(([domain, n]) => (
          <li key={domain} className="flex items-center gap-2 text-sm">
            <span className="w-64 truncate">
              {domain} ({n})
            </span>
            <Input
              className="h-8 w-56"
              list="other-company-names"
              placeholder="Company name"
              aria-label={`Company for ${domain}`}
              value={names[domain] ?? ''}
              onChange={(e) => setNames({ ...names, [domain]: e.target.value })}
            />
            <Button
              size="sm"
              variant="outline"
              disabled={!names[domain]?.trim() || move.isPending}
              onClick={() => move.mutate({ domain, name: names[domain].trim() })}
            >
              Move
            </Button>
          </li>
        ))}
      </ul>
    </details>
  )
}

function EmailFinder({ companies, onAdd }: { companies: Company[]; onAdd: () => void }) {
  const [companyId, setCompanyId] = useState('')
  const [person, setPerson] = useState('')
  const [domain, setDomain] = useState('')
  const find = useMutation({
    mutationFn: () =>
      findEmails({
        company_id: Number(companyId),
        full_name: person.trim() || undefined,
        domain: domain.trim() || undefined,
      }),
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed'),
  })
  const add = useMutation({
    mutationFn: (email: string) =>
      createContact({ company_id: Number(companyId), email, name: person.trim() || undefined }),
    onSuccess: () => {
      toast.success('Added to your email list')
      onAdd()
    },
    onError: (e) =>
      toast.error(e instanceof ApiError && typeof e.detail === 'string' ? e.detail : 'Failed'),
  })
  const result = find.data
  return (
    <div className="space-y-2 rounded-md border p-3">
      <h2 className="text-sm font-medium">Find an email</h2>
      <form
        className="flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (companyId) find.mutate()
        }}
      >
        <select
          aria-label="Company to search"
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={companyId}
          onChange={(e) => setCompanyId(e.target.value)}
        >
          <option value="">Company…</option>
          {companies.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <Input
          className="w-48"
          placeholder="Person's full name"
          aria-label="Person's full name"
          value={person}
          onChange={(e) => setPerson(e.target.value)}
        />
        <Input
          className="w-48"
          placeholder="Email domain (optional)"
          aria-label="Email domain"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
        />
        <Button type="submit" variant="outline" disabled={!companyId}>
          Find
        </Button>
      </form>
      {result &&
        (result.domain ? (
          <div className="text-sm">
            <p className="text-muted-foreground">
              Domain {result.domain}
              {result.domain_resolves ? '' : ' (does not resolve — check it)'}. These are guesses,
              not verified.
            </p>
            <ul className="mt-1 space-y-1">
              {result.guesses.map((g) => (
                <li key={g.email} className="flex items-center gap-2">
                  <span>{g.email}</span>
                  <span className="text-xs text-muted-foreground">
                    {g.confidence}
                    {g.note ? ` · ${g.note}` : ''}
                  </span>
                  <Button size="sm" variant="ghost" onClick={() => add.mutate(g.email)}>
                    <Plus /> Add
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No known email domain for this company. Enter its domain (e.g. rockwellautomation.com)
            and search again.
          </p>
        ))}
    </div>
  )
}

export function ContactsView() {
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [companyId, setCompanyId] = useState('')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')

  const contacts = useQuery({ queryKey: ['contacts', q], queryFn: () => listContacts(q) })
  const companies = useQuery({ queryKey: ['companies', ''], queryFn: () => listCompanies('') })
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['contacts'] })
    qc.invalidateQueries({ queryKey: ['companies'] })
  }
  const fail = (e: Error) =>
    toast.error(e instanceof ApiError && typeof e.detail === 'string' ? e.detail : e.message)

  const add = useMutation({
    mutationFn: createContact,
    onSuccess: () => {
      setEmail('')
      setName('')
      refresh()
    },
    onError: fail,
  })
  const remove = useMutation({ mutationFn: deleteContact, onSuccess: refresh, onError: fail })

  const rows = contacts.data ?? []
  return (
    <div className="space-y-4 p-4">
      <Input
        className="max-w-xs"
        placeholder="Search emails or companies"
        aria-label="Search contacts"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <form
        className="flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (companyId && email.trim())
            add.mutate({ company_id: Number(companyId), email, name: name.trim() || undefined })
        }}
      >
        <select
          aria-label="Company"
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={companyId}
          onChange={(e) => setCompanyId(e.target.value)}
        >
          <option value="">Company…</option>
          {(companies.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <Input
          className="w-64"
          type="email"
          placeholder="Email"
          aria-label="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Input
          className="w-48"
          placeholder="Name (optional)"
          aria-label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Button type="submit">
          <Plus /> Add email
        </Button>
      </form>

      <BulkPaste onDone={refresh} />
      <datalist id="other-company-names">
        {(companies.data ?? []).map((c) => (
          <option key={c.id} value={c.name} />
        ))}
      </datalist>
      <SortOther contacts={rows} onDone={refresh} />
      <EmailFinder companies={companies.data ?? []} onAdd={refresh} />

      {contacts.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Mail}
          title="No emails yet"
          description="Import your sheet on the Companies page, or add an email above."
        />
      ) : (
        <table className="w-full text-sm">
          <thead className="text-left text-muted-foreground">
            <tr>
              <th className="py-2">Email</th>
              <th>Name</th>
              <th>Company</th>
              <th>Added from</th>
              <th className="w-10" />
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id} className="border-t">
                <td className="py-2">{c.email}</td>
                <td>{c.name ?? '—'}</td>
                <td>{c.company}</td>
                <td>{c.origin}</td>
                <td>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Delete ${c.email}`}
                    onClick={() => remove.mutate(c.id)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

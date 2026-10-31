import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, Plus, Trash2, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { ApiError } from '@/api/client'
import { createCompany, deleteCompany, importSheet, listCompanies } from '@/api/directory'
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

export function CompaniesView() {
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [newName, setNewName] = useState('')
  const [toDelete, setToDelete] = useState<{ id: number; name: string } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const companies = useQuery({ queryKey: ['companies', q], queryFn: () => listCompanies(q) })
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['companies'] })
    qc.invalidateQueries({ queryKey: ['contacts'] })
  }
  const fail = (e: Error) =>
    toast.error(e instanceof ApiError && typeof e.detail === 'string' ? e.detail : e.message)

  const add = useMutation({
    mutationFn: createCompany,
    onSuccess: () => {
      setNewName('')
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
            if (newName.trim()) add.mutate(newName)
          }}
        >
          <Input
            placeholder="New company name"
            aria-label="New company name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
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
              <th>Careers link(s)</th>
              <th>Emails</th>
              <th className="w-10" />
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id} className="border-t align-top">
                <td className="py-2 font-medium">{c.name}</td>
                <td className="space-y-1 py-2">
                  {c.sources.map((s) => (
                    <div key={s.id} className="flex items-center gap-2">
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
                  ))}
                </td>
                <td className="py-2">{c.contact_count}</td>
                <td className="py-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Delete ${c.name}`}
                    onClick={() => setToDelete({ id: c.id, name: c.name })}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </td>
              </tr>
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

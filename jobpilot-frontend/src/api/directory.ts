import { apiGet, apiSend } from '@/api/client'

export type Source = {
  id: number
  url: string
  ats_type: string
  last_check_at: string | null
  last_status: string | null
  last_error: string | null
  last_found: number | null
  last_kept: number | null
}
export type Company = { id: number; name: string; sources: Source[]; contact_count: number }
export type Contact = {
  id: number
  company_id: number
  company: string
  email: string
  name: string | null
  origin: string
}
export type ImportResult = {
  companies_created: number
  companies_existing: number
  sources_created: number
  contacts_created: number
  unsafe_urls: string[]
}

export const listCompanies = (q = '') =>
  apiGet<Company[]>(`/api/companies?q=${encodeURIComponent(q)}`)
export const createCompany = (body: { name: string; url?: string }) =>
  apiSend<Company>('POST', '/api/companies', body)
export const renameCompany = (id: number, name: string) =>
  apiSend<Company>('PATCH', `/api/companies/${id}`, { name })
export const deleteCompany =(id: number) => apiSend<void>('DELETE', `/api/companies/${id}`)
export const addSource = (companyId: number, url: string) =>
  apiSend<Source>('POST', `/api/companies/${companyId}/sources`, { url })
export const updateSource = (id: number, url: string) =>
  apiSend<Source>('PATCH', `/api/sources/${id}`, { url })
export const deleteSource =(id: number) => apiSend<void>('DELETE', `/api/sources/${id}`)
export const importSheet = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return apiSend<ImportResult>('POST', '/api/directory/import', form)
}

export const listContacts = (q = '') =>
  apiGet<Contact[]>(`/api/contacts?q=${encodeURIComponent(q)}`)
export const createContact = (body: { company_id: number; email: string; name?: string }) =>
  apiSend<Contact>('POST', '/api/contacts', body)
export const deleteContact = (id: number) => apiSend<void>('DELETE', `/api/contacts/${id}`)

export type Guess = { email: string; pattern: string; confidence: string; note: string }
export type FindResult = { domain: string | null; domain_resolves: boolean; guesses: Guess[] }
export const findEmails = (body: { company_id: number; full_name?: string; domain?: string }) =>
  apiSend<FindResult>('POST', '/api/contacts/find', body)

export type BulkResult = {
  added: number
  duplicates: number
  by_company: Record<string, number>
  other_domains: string[]
}
export const bulkContacts = (text: string) =>
  apiSend<BulkResult>('POST', '/api/contacts/bulk', { text })
export const moveDomain = (domain: string, company_name: string) =>
  apiSend<{ moved: number }>('POST', '/api/contacts/move-domain', { domain, company_name })

import { apiGet, apiSend } from '@/api/client'

export type Job = {
  id: number
  company_id: number
  company: string
  title: string
  location: string | null
  remote: boolean
  url: string | null
  posted_at: string | null
  date_known: boolean
  first_seen_at: string
  status: string
  is_new: boolean
  description: string | null
  score: number | null
  filtered: boolean
  reasons: string[]
  feedback: number | null
}
export type JobEvent = {
  from_status: string | null
  to_status: string
  at: string
  note: string | null
  actor: string
}
export type JobDetail = Job & { events: JobEvent[] }
export type Run = {
  id: number
  source_id: number
  company: string
  status: string
  phase: string
  stats: Record<string, number>
  error: string | null
}

export type JobFilters = {
  company_id?: number
  q: string
  posted_within_days: number
  min_score: number
  include_filtered: boolean
  sort: 'date' | 'score'
}

export const listJobs = (f: JobFilters) => {
  const p = new URLSearchParams({ limit: '200' })
  if (f.company_id) p.set('company_id', String(f.company_id))
  if (f.q) p.set('q', f.q)
  if (f.posted_within_days) p.set('posted_within_days', String(f.posted_within_days))
  if (f.min_score) p.set('min_score', String(f.min_score))
  if (f.include_filtered) p.set('include_filtered', 'true')
  p.set('sort', f.sort)
  return apiGet<{ items: Job[]; total: number }>(`/api/jobs?${p}`)
}
export const getJob = (id: number) => apiGet<JobDetail>(`/api/jobs/${id}`)
export const dismissJob = (id: number) => apiSend<Job>('POST', `/api/jobs/${id}/dismiss`)
export const setDescription = (id: number, text: string) =>
  apiSend<Job>('PUT', `/api/jobs/${id}/description`, { text })

export const checkByInput = (body: { company_name?: string; url?: string }) =>
  apiSend<{ runs: Run[] }>('POST', '/api/checks/by-input', body)
export const getRun = (id: number) => apiGet<Run>(`/api/checks/${id}`)
export const cancelRun = (id: number) => apiSend<Run>('POST', `/api/checks/${id}/cancel`)

export const setFeedback = (id: number, value: 1 | -1 | null) =>
  apiSend<Job>('POST', `/api/jobs/${id}/feedback`, { value })
export const hideSimilar = (id: number, words: string[]) =>
  apiSend<Job>('POST', `/api/jobs/${id}/hide-similar`, { words })

export type Profile = {
  role_keywords: string[]
  locations: string[]
  include_remote: boolean
  max_experience_years: number
  exclude_title_words: string[]
  hidden_title_words: string[]
}
export const getProfile = () => apiGet<Profile>('/api/profile')
export const putProfile = (p: Profile) => apiSend<Profile>('PUT', '/api/profile', p)

export type Candidate = { url: string; title: string; ats_type: string }
export const findCareers = (name: string) =>
  apiGet<Candidate[]>(`/api/companies/find-careers?name=${encodeURIComponent(name)}`)

export type LlmSettings = {
  active_preset: string
  presets: Record<string, Record<string, string>>
  providers: {
    groq: { configured: boolean }
    anthropic: { configured: boolean }
    ollama: { reachable: boolean; models: string[] }
  }
}
export const getLlm = () => apiGet<LlmSettings>('/api/settings/llm')
export const putLlm = (active_preset: string) =>
  apiSend<LlmSettings>('PUT', '/api/settings/llm', { active_preset })
export const testLlm = (task: 'extract' | 'classify') =>
  apiSend<{ ok: boolean; model: string; ms: number; error?: string }>(
    'POST',
    '/api/settings/llm/test',
    { task },
  )

export const setStatus = (id: number, status: string, note?: string) =>
  apiSend<Job>('POST', `/api/jobs/${id}/status`, { status, note })
export const listByStatus = (statuses: string[]) =>
  apiGet<{ items: Job[]; total: number }>(`/api/jobs?limit=200&statuses=${statuses.join(',')}`)
export const coverLetter = (id: number) =>
  apiSend<{ text: string }>('POST', `/api/jobs/${id}/cover-letter`)

export const aiMatch = (id: number) => apiSend<Job>('POST', `/api/jobs/${id}/ai-match`)

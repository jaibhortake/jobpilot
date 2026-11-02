import { apiGet, apiSend } from './client'

export type Applicant = { details: Record<string, string>; disabled_sites: string[] }
export type Answer = { id: number | null; question: string; answer: string }

export const getApplicant = () => apiGet<Applicant>('/api/applicant')
export const putApplicant = (a: Applicant) => apiSend<Applicant>('PUT', '/api/applicant', a)
export const getDetailKeys = () => apiGet<string[]>('/api/applicant/keys')
export const listAnswers = () => apiGet<Answer[]>('/api/answers')
export const saveAnswers = (a: Omit<Answer, 'id'>[]) =>
  apiSend<{ saved: number }>('POST', '/api/answers', a)
export const deleteAnswer = (id: number) => apiSend<void>('DELETE', `/api/answers/${id}`)

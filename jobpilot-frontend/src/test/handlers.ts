import { http, HttpResponse } from 'msw'

export const API = 'http://127.0.0.1:8000'

export const handlers = [
  http.get(`${API}/api/health`, () => HttpResponse.json({ status: 'ok', db: true })),
  http.get(`${API}/api/jobs`, () => HttpResponse.json({ items: [], total: 0 })),
  http.get(`${API}/api/companies`, () => HttpResponse.json([])),
  http.get(`${API}/api/contacts`, () => HttpResponse.json([])),
]

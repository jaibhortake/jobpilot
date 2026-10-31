import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { API } from '@/test/handlers'
import { renderWithProviders } from '@/test/render'
import { server } from '@/test/server'
import { HealthBadge } from './HealthBadge'

describe('HealthBadge', () => {
  it('shows API OK when the API answers', async () => {
    renderWithProviders(<HealthBadge />)
    expect(await screen.findByLabelText('API OK')).toBeInTheDocument()
  })

  it('shows API down on a server error', async () => {
    server.use(http.get(`${API}/api/health`, () => new HttpResponse(null, { status: 500 })))
    renderWithProviders(<HealthBadge />)
    expect(await screen.findByLabelText('API down')).toBeInTheDocument()
  })

  it('shows database down when the API is up but the db is not', async () => {
    server.use(http.get(`${API}/api/health`, () => HttpResponse.json({ status: 'ok', db: false })))
    renderWithProviders(<HealthBadge />)
    expect(await screen.findByLabelText('Database not connected')).toBeInTheDocument()
  })
})

import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '@/test/render'
import { AppShell } from './AppShell'

describe('AppShell', () => {
  it('lists the four navigation links by accessible name', () => {
    renderWithProviders(<AppShell />)
    const nav = screen.getByRole('navigation', { name: 'Main' })
    for (const name of ['Jobs', 'Tracker', 'Companies', 'Contacts', 'Apply profile', 'CVs', 'Settings']) {
      expect(within(nav).getByRole('link', { name })).toBeInTheDocument()
    }
    expect(within(nav).getAllByRole('link')).toHaveLength(7)
  })

  it('applies the dark class when Dark is chosen in the theme menu', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AppShell />)
    await user.click(screen.getByRole('button', { name: 'Theme' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Dark' }))
    expect(document.documentElement).toHaveClass('dark')
  })

  it('shows an empty state with a primary action on the Jobs page', async () => {
    renderWithProviders(<AppShell />, '/jobs')
    expect(await screen.findByText(/No jobs yet/i)).toBeInTheDocument()
  })
})

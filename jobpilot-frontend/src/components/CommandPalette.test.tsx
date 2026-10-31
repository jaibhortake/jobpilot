import { fireEvent, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '@/test/render'
import { CommandPalette } from './CommandPalette'

describe('CommandPalette', () => {
  it('opens with Ctrl+K and lists actions', async () => {
    renderWithProviders(<CommandPalette />)
    expect(screen.queryByPlaceholderText(/search/i)).not.toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'k', ctrlKey: true })
    expect(await screen.findByPlaceholderText(/search/i)).toBeInTheDocument()
    expect(screen.getByText('Toggle theme')).toBeInTheDocument()
  })

  it('toggles the dark class from the Toggle theme action', async () => {
    const user = userEvent.setup()
    renderWithProviders(<CommandPalette />)
    fireEvent.keyDown(document, { key: 'k', ctrlKey: true })
    await user.click(await screen.findByText('Toggle theme'))
    expect(document.documentElement).toHaveClass('dark')
  })

  it('does not open when typing "/" inside a text field', async () => {
    renderWithProviders(
      <>
        <input aria-label="field" />
        <CommandPalette />
      </>,
    )
    const field = screen.getByLabelText('field')
    field.focus()
    fireEvent.keyDown(field, { key: '/' })
    expect(screen.queryByPlaceholderText(/search/i)).not.toBeInTheDocument()
  })
})

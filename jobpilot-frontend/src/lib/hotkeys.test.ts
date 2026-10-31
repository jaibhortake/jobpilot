import { describe, expect, it, vi } from 'vitest'
import { isTypingTarget, matchesHotkey } from './hotkeys'

describe('isTypingTarget', () => {
  it('is true for inputs, textareas, selects and contenteditable', () => {
    expect(isTypingTarget(document.createElement('input'))).toBe(true)
    expect(isTypingTarget(document.createElement('textarea'))).toBe(true)
    expect(isTypingTarget(document.createElement('select'))).toBe(true)
    const div = document.createElement('div')
    div.setAttribute('contenteditable', 'true')
    Object.defineProperty(div, 'isContentEditable', { value: true })
    expect(isTypingTarget(div)).toBe(true)
  })

  it('is false for plain elements and null', () => {
    expect(isTypingTarget(document.createElement('div'))).toBe(false)
    expect(isTypingTarget(null)).toBe(false)
  })
})

describe('matchesHotkey', () => {
  it('ignores single-key shortcuts typed in an input', () => {
    const handler = vi.fn()
    const input = document.createElement('input')
    document.body.appendChild(input)
    const event = new KeyboardEvent('keydown', { key: 'd', bubbles: true })
    Object.defineProperty(event, 'target', { value: input })
    if (matchesHotkey(event, 'd')) handler()
    expect(handler).not.toHaveBeenCalled()
  })

  it('matches a plain key on the body', () => {
    const event = new KeyboardEvent('keydown', { key: 'd', bubbles: true })
    Object.defineProperty(event, 'target', { value: document.body })
    expect(matchesHotkey(event, 'd')).toBe(true)
  })

  it('still allows Ctrl+K inside an input', () => {
    const input = document.createElement('input')
    const event = new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true })
    Object.defineProperty(event, 'target', { value: input })
    expect(matchesHotkey(event, 'mod+k')).toBe(true)
  })
})

import { useEffect, useRef } from 'react'

/** True when the user is typing, so single-key shortcuts must not fire. */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName
  return (
    tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable === true
  )
}

/**
 * combo: a single key ("d", "/") or "mod+<key>" (Ctrl on Windows/Linux, Cmd on Mac).
 * Single keys are ignored while typing; mod+ combos always work.
 */
export function matchesHotkey(event: KeyboardEvent, combo: string): boolean {
  const wantsMod = combo.startsWith('mod+')
  const key = (wantsMod ? combo.slice(4) : combo).toLowerCase()
  if (event.key.toLowerCase() !== key) return false
  const hasMod = event.ctrlKey || event.metaKey
  if (wantsMod) return hasMod && !event.altKey
  if (hasMod || event.altKey) return false
  return !isTypingTarget(event.target)
}

export function useHotkey(combo: string, handler: (event: KeyboardEvent) => void, enabled = true) {
  const handlerRef = useRef(handler)
  useEffect(() => {
    handlerRef.current = handler
  }, [handler])

  useEffect(() => {
    if (!enabled) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (matchesHotkey(event, combo)) handlerRef.current(event)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [combo, enabled])
}

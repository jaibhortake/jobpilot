import { Briefcase, Building2, FileText, Settings, SunMoon } from 'lucide-react'
import { useTheme } from 'next-themes'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { useHotkey } from '@/lib/hotkeys'

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const { resolvedTheme, setTheme } = useTheme()

  useHotkey('mod+k', (event) => {
    event.preventDefault()
    setOpen((value) => !value)
  })
  useHotkey('/', (event) => {
    event.preventDefault()
    setOpen(true)
  })

  const run = (action: () => void) => {
    setOpen(false)
    action()
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <Command>
        <CommandInput placeholder="Search or run a command…" />
        <CommandList>
          <CommandEmpty>No results.</CommandEmpty>
          <CommandGroup heading="Actions">
            <CommandItem
              onSelect={() => run(() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark'))}
            >
              <SunMoon /> Toggle theme
            </CommandItem>
          </CommandGroup>
          <CommandGroup heading="Go to">
            <CommandItem onSelect={() => run(() => navigate('/jobs'))}>
              <Briefcase /> Jobs
            </CommandItem>
            <CommandItem onSelect={() => run(() => navigate('/companies'))}>
              <Building2 /> Companies
            </CommandItem>
            <CommandItem onSelect={() => run(() => navigate('/cvs'))}>
              <FileText /> CVs
            </CommandItem>
            <CommandItem onSelect={() => run(() => navigate('/settings'))}>
              <Settings /> Settings
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </CommandDialog>
  )
}

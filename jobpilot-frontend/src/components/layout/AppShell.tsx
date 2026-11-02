import {
  Briefcase,
  Building2,
  FileText,
  ListChecks,
  Send,
  Mail,
  Monitor,
  Moon,
  Settings,
  Sun,
} from 'lucide-react'
import { MotionConfig, motion } from 'motion/react'
import { useTheme } from 'next-themes'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { CommandPalette } from '@/components/CommandPalette'
import { HealthBadge } from '@/components/HealthBadge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Separator } from '@/components/ui/separator'
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { CompaniesView } from '@/views/CompaniesView'
import { ApplyView } from '@/views/ApplyView'
import { ContactsView } from '@/views/ContactsView'
import { CvsView } from '@/views/CvsView'
import { JobsView } from '@/views/JobsView'
import { SettingsView } from '@/views/SettingsView'
import { TrackerView } from '@/views/TrackerView'

const NAV = [
  { to: '/jobs', label: 'Jobs', icon: Briefcase },
  { to: '/tracker', label: 'Tracker', icon: ListChecks },
  { to: '/companies', label: 'Companies', icon: Building2 },
  { to: '/contacts', label: 'Contacts', icon: Mail },
  { to: '/apply', label: 'Apply profile', icon: Send },
  { to: '/cvs', label: 'CVs', icon: FileText },
  { to: '/settings', label: 'Settings', icon: Settings },
] as const

function ThemeMenu() {
  const { setTheme } = useTheme()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={<Button variant="ghost" size="icon" aria-label="Theme" />}>
        <Sun className="size-4 dark:hidden" />
        <Moon className="hidden size-4 dark:block" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => setTheme('system')}>
          <Monitor /> System
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme('light')}>
          <Sun /> Light
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme('dark')}>
          <Moon /> Dark
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function AppShell() {
  const { pathname } = useLocation()
  const current = NAV.find((item) => pathname.startsWith(item.to))

  return (
    <MotionConfig reducedMotion="user">
      <SidebarProvider>
        <Sidebar collapsible="icon">
          <SidebarHeader>
            <div className="flex items-center gap-2 px-2 py-1.5 font-semibold">
              <Briefcase className="size-5 shrink-0" aria-hidden />
              <span className="truncate group-data-[collapsible=icon]:hidden">JobPilot</span>
            </div>
          </SidebarHeader>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupContent>
                <nav aria-label="Main">
                  <SidebarMenu>
                    {NAV.map(({ to, label, icon: Icon }) => (
                      <SidebarMenuItem key={to}>
                        <SidebarMenuButton
                          tooltip={label}
                          isActive={pathname.startsWith(to)}
                          render={<NavLink to={to} />}
                        >
                          <Icon />
                          <span>{label}</span>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    ))}
                  </SidebarMenu>
                </nav>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
          <SidebarRail />
        </Sidebar>

        <SidebarInset>
          <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
            <SidebarTrigger aria-label="Toggle sidebar" />
            <Separator orientation="vertical" className="mx-1 h-5" />
            <h1 className="text-sm font-medium">{current?.label ?? 'JobPilot'}</h1>
            <div className="ml-auto flex items-center gap-1">
              <span className="hidden text-xs text-muted-foreground sm:inline">
                Press <kbd className="rounded border px-1">Ctrl</kbd>+
                <kbd className="rounded border px-1">K</kbd>
              </span>
              <HealthBadge />
              <ThemeMenu />
            </div>
          </header>
          <motion.main
            key={current?.to}
            className="min-h-0 flex-1 overflow-auto"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.15 }}
          >
            <Routes>
              <Route path="/" element={<Navigate to="/jobs" replace />} />
              <Route path="/jobs" element={<JobsView />} />
              <Route path="/tracker" element={<TrackerView />} />
              <Route path="/companies" element={<CompaniesView />} />
              <Route path="/contacts" element={<ContactsView />} />
              <Route path="/apply" element={<ApplyView />} />
              <Route path="/cvs" element={<CvsView />} />
              <Route path="/settings" element={<SettingsView />} />
              <Route path="*" element={<Navigate to="/jobs" replace />} />
            </Routes>
          </motion.main>
        </SidebarInset>
        <CommandPalette />
      </SidebarProvider>
    </MotionConfig>
  )
}

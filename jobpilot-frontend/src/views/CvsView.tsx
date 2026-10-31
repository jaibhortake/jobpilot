import { FileText } from 'lucide-react'
import { EmptyState } from '@/components/EmptyState'

export function CvsView() {
  return (
    <EmptyState
      icon={FileText}
      title="No CVs yet"
      description="Your master CVs will be listed here, with one set as the default."
    />
  )
}

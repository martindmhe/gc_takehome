import { Badge } from '@/components/ui/badge'
import type { LeadStatus } from '@/lib/api'
import { cn } from '@/lib/utils'

const STYLES: Record<LeadStatus, { label: string; className: string }> = {
  PENDING_ASSIGNMENT: { label: 'Pending assignment', className: 'bg-amber-100 text-amber-900' },
  ASSIGNED: { label: 'Assigned', className: 'bg-sky-100 text-sky-900' },
  DECLINED: { label: 'Declined', className: 'bg-rose-100 text-rose-900' },
  ACCEPTED: { label: 'Accepted', className: 'bg-emerald-100 text-emerald-900' },
}

export const LEAD_STATUS_LABELS = Object.fromEntries(
  Object.entries(STYLES).map(([status, s]) => [status, s.label]),
) as Record<LeadStatus, string>

export function LeadStatusBadge({ status }: { status: LeadStatus }) {
  const style = STYLES[status]
  return <Badge className={cn('border-transparent', style.className)}>{style.label}</Badge>
}

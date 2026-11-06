import { Badge } from '@/components/ui/badge'
import type { CaseStatus } from '@/lib/api'

export const CASE_STATUS_LABELS: Record<CaseStatus, string> = {
  OPEN: 'Open',
  IN_PROGRESS: 'In progress',
  WAITING_ON_PLAINTIFF: 'Waiting on plaintiff',
  CLOSED: 'Closed',
}

export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  return <Badge variant={status === 'CLOSED' ? 'secondary' : 'outline'}>{CASE_STATUS_LABELS[status]}</Badge>
}

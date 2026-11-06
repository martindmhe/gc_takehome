import { Badge } from '@/components/ui/badge'
import type { CaseStatus } from '@/lib/api'

const LABELS: Record<CaseStatus, string> = {
  OPEN: 'Open',
  IN_PROGRESS: 'In progress',
  WAITING_ON_PLAINTIFF: 'Waiting on plaintiff',
  CLOSED: 'Closed',
}

export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  return <Badge variant={status === 'CLOSED' ? 'secondary' : 'outline'}>{LABELS[status]}</Badge>
}

import type { Lead } from '@/lib/api'

/** Why a lead has no firm, for the two states that wait on an admin; otherwise null. */
export function unassignedReason(lead: Pick<Lead, 'status'>): string | null {
  if (lead.status === 'PENDING_ASSIGNMENT') return 'No firm matched its category and region.'
  if (lead.status === 'DECLINED') return 'Declined by the assigned firm.'
  return null
}

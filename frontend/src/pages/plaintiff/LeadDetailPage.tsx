import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'

import { CaseStatusBadge } from '@/components/CaseStatusBadge'
import { DetailItem, LeadInfoFields } from '@/components/LeadInfoFields'
import { LeadStatusBadge } from '@/components/LeadStatusBadge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ApiError, getLead, type Lead } from '@/lib/api'

function statusExplanation(lead: Lead): string {
  switch (lead.status) {
    case 'ASSIGNED':
      return `Routed to ${lead.assigned_firm?.name}. The firm will review it and accept or decline.`
    case 'PENDING_ASSIGNMENT':
      return 'No firm covers this region and category yet. An admin will assign it to a firm.'
    case 'DECLINED':
      return 'The firm declined this lead. An admin will assign it to another firm.'
    case 'ACCEPTED':
      return `${lead.assigned_firm?.name} accepted this lead and opened a case.`
  }
}

export function LeadDetailPage() {
  const { leadId = '' } = useParams()
  const lead = useQuery({ queryKey: ['lead', leadId], queryFn: () => getLead(leadId) })

  return (
    <div className="space-y-4">
      <Link to="/plaintiff" className="text-muted-foreground text-sm hover:underline">
        ← My leads
      </Link>

      {lead.isPending && <p className="text-muted-foreground">Loading…</p>}
      {lead.isError && (
        <p className="text-destructive">
          {lead.error instanceof ApiError && lead.error.status === 404
            ? 'Lead not found.'
            : lead.error.message}
        </p>
      )}

      {lead.isSuccess && (
        <Card>
          <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2">
            <CardTitle className="text-xl">
              {lead.data.category_label} · {lead.data.region_label}
            </CardTitle>
            <LeadStatusBadge status={lead.data.status} />
          </CardHeader>
          <CardContent className="space-y-6">
            <p className="bg-muted rounded-md p-3 text-sm">{statusExplanation(lead.data)}</p>

            <LeadInfoFields lead={lead.data}>
              <DetailItem label="Assigned firm">
                {lead.data.assigned_firm?.name ?? 'Not assigned yet'}
              </DetailItem>
              {lead.data.case && (
                <DetailItem label="Case status">
                  <CaseStatusBadge status={lead.data.case.status} />
                </DetailItem>
              )}
            </LeadInfoFields>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

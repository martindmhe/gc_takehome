import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'

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

            <dl className="grid gap-4 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-muted-foreground">Assigned firm</dt>
                <dd>{lead.data.assigned_firm?.name ?? 'Not assigned yet'}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Submitted</dt>
                <dd>{new Date(lead.data.created_at).toLocaleString()}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Contact name</dt>
                <dd>{lead.data.contact_name}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Contact email</dt>
                <dd>{lead.data.contact_email}</dd>
              </div>
            </dl>

            <div className="text-sm">
              <h2 className="text-muted-foreground mb-1">Description</h2>
              <p className="whitespace-pre-wrap">{lead.data.description}</p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

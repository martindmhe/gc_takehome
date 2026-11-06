import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'

import { CaseStatusBadge } from '@/components/CaseStatusBadge'
import { DocumentsPanel } from '@/components/DocumentsPanel'
import { DetailItem, LeadInfoFields } from '@/components/LeadInfoFields'
import { LeadStatusBadge } from '@/components/LeadStatusBadge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ApiError, getLead } from '@/lib/api'
import { unassignedReason } from '@/lib/leads'

/** Read-only admin view of any lead. Assignment actions come in a later step. */
export function AdminLeadPage() {
  const { leadId = '' } = useParams()
  const lead = useQuery({ queryKey: ['lead', leadId], queryFn: () => getLead(leadId) })
  const reason = lead.data ? unassignedReason(lead.data) : null

  return (
    <div className="space-y-4">
      <Link to="/admin" className="text-muted-foreground text-sm hover:underline">
        ← Admin search
      </Link>

      {lead.isPending && <p className="text-muted-foreground">Loading…</p>}
      {lead.isError && (
        <p role="alert" className="text-destructive">
          {lead.error instanceof ApiError && lead.error.status === 404
            ? 'Lead not found.'
            : lead.error.message}
        </p>
      )}

      {lead.isSuccess && (
        <Card>
          <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2">
            <CardTitle className="text-xl">
              Lead: {lead.data.category_label} · {lead.data.region_label}
            </CardTitle>
            <LeadStatusBadge status={lead.data.status} />
          </CardHeader>
          <CardContent className="space-y-6">
            {reason && (
              <p role="status" className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm">
                {reason} This lead has no firm and is waiting for an admin to assign one.
              </p>
            )}
            <LeadInfoFields lead={lead.data}>
              <DetailItem label="Assigned firm">
                {lead.data.assigned_firm?.name ?? 'Unassigned'}
              </DetailItem>
              {lead.data.case && (
                <DetailItem label="Case">
                  <Link
                    to={`/admin/cases/${lead.data.case.id}`}
                    className="inline-flex items-center gap-2 underline-offset-4 hover:underline"
                  >
                    <CaseStatusBadge status={lead.data.case.status} /> View case
                  </Link>
                </DetailItem>
              )}
              <DetailItem label="Last updated">
                {new Date(lead.data.updated_at).toLocaleString()}
              </DetailItem>
            </LeadInfoFields>
          </CardContent>
        </Card>
      )}

      {lead.isSuccess && <DocumentsPanel leadId={lead.data.id} readOnly />}
    </div>
  )
}

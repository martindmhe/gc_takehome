import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'

import { AssignmentPanel } from '@/components/admin/AssignmentPanel'
import { AuditTimeline } from '@/components/admin/AuditTimeline'
import { CaseStatusBadge } from '@/components/CaseStatusBadge'
import { DocumentsPanel } from '@/components/DocumentsPanel'
import { DetailItem, LeadInfoFields } from '@/components/LeadInfoFields'
import { LeadStatusBadge } from '@/components/LeadStatusBadge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ApiError, assignLead, getLead } from '@/lib/api'
import { unassignedReason } from '@/lib/leads'

/** Admin view of any lead: details, documents, firm assignment, and history. */
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
            {lead.data.status === 'ACCEPTED' ? (
              <AssignmentPanel currentFirm={lead.data.assigned_firm}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-muted-foreground text-sm">
                    This lead was accepted, so its firm follows its case. Reassign the case to
                    move both.
                  </p>
                  {lead.data.case && (
                    <Button asChild>
                      <Link to={`/admin/cases/${lead.data.case.id}`}>Go to case to reassign</Link>
                    </Button>
                  )}
                </div>
              </AssignmentPanel>
            ) : (
              <AssignmentPanel
                currentFirm={lead.data.assigned_firm}
                unassignedNote={reason && `${reason} Waiting for an admin to assign a firm.`}
                buttonLabel={lead.data.assigned_firm ? 'Reassign lead' : 'Assign to a firm'}
                dialogTitle={lead.data.assigned_firm ? 'Reassign this lead' : 'Assign this lead'}
                onAssign={(firmId) => assignLead(lead.data.id, firmId)}
                consequences={(firm) => (
                  <ul className="list-disc space-y-1 pl-4">
                    {lead.data.assigned_firm && (
                      <li>
                        <strong>{lead.data.assigned_firm.name}</strong> immediately loses access to
                        this lead and its documents.
                      </li>
                    )}
                    <li>
                      <strong>{firm}</strong> will see it in their inbox to accept or decline.
                    </li>
                  </ul>
                )}
              />
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
      {lead.isSuccess && <AuditTimeline kind="leads" id={lead.data.id} />}
    </div>
  )
}

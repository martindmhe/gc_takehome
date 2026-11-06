import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { CaseStatusBadge } from '@/components/CaseStatusBadge'
import { DocumentsPanel } from '@/components/DocumentsPanel'
import { DetailItem, LeadInfoFields } from '@/components/LeadInfoFields'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ApiError, getCase, type Case } from '@/lib/api'

/**
 * Shared case page layout: back link, loading/error states, the case card, and documents.
 * `children` renders role-specific content (e.g. staff controls) above the details.
 */
export function CaseDetails({
  caseId,
  backTo,
  backLabel,
  children,
}: {
  caseId: string
  backTo: string
  backLabel: string
  children?: (legalCase: Case) => ReactNode
}) {
  const legalCase = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => getCase(caseId),
  })

  return (
    <div className="space-y-4">
      <Link to={backTo} className="text-muted-foreground text-sm hover:underline">
        ← {backLabel}
      </Link>

      {legalCase.isPending && <p className="text-muted-foreground">Loading…</p>}
      {legalCase.isError && (
        <p role="alert" className="text-destructive">
          {legalCase.error instanceof ApiError && legalCase.error.status === 404
            ? 'Case not found.'
            : legalCase.error.message}
        </p>
      )}

      {legalCase.isSuccess && (
        <Card>
          <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2">
            <CardTitle className="text-xl">
              Case: {legalCase.data.lead.category_label} · {legalCase.data.lead.region_label}
            </CardTitle>
            <CaseStatusBadge status={legalCase.data.status} />
          </CardHeader>
          <CardContent className="space-y-6">
            {children?.(legalCase.data)}
            <LeadInfoFields lead={legalCase.data.lead}>
              <DetailItem label="Firm">{legalCase.data.assigned_firm.name}</DetailItem>
              <DetailItem label="Plaintiff">
                {legalCase.data.plaintiff.display_name} ({legalCase.data.plaintiff.email})
              </DetailItem>
              <DetailItem label="Case opened">
                {new Date(legalCase.data.created_at).toLocaleString()}
              </DetailItem>
              <DetailItem label="Last updated">
                {new Date(legalCase.data.updated_at).toLocaleString()}
              </DetailItem>
            </LeadInfoFields>
          </CardContent>
        </Card>
      )}
      {legalCase.isSuccess && <DocumentsPanel leadId={legalCase.data.lead.id} />}
    </div>
  )
}

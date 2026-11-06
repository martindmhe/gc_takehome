import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'

import { CaseStatusBadge } from '@/components/CaseStatusBadge'
import { DetailItem, LeadInfoFields } from '@/components/LeadInfoFields'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ApiError, getCase } from '@/lib/api'

/** Read-only case view. Case progress, notes and documents come in later steps. */
export function FirmCasePage() {
  const { caseId = '' } = useParams()
  const legalCase = useQuery({ queryKey: ['case', caseId], queryFn: () => getCase(caseId) })

  return (
    <div className="space-y-4">
      <Link to="/firm" className="text-muted-foreground text-sm hover:underline">
        ← Inbox
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
            <CardTitle className="text-xl">Case: {legalCase.data.lead.contact_name}</CardTitle>
            <CaseStatusBadge status={legalCase.data.status} />
          </CardHeader>
          <CardContent>
            <LeadInfoFields lead={legalCase.data.lead}>
              <DetailItem label="Firm">{legalCase.data.assigned_firm.name}</DetailItem>
              <DetailItem label="Case opened">
                {new Date(legalCase.data.created_at).toLocaleString()}
              </DetailItem>
            </LeadInfoFields>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

import { useParams } from 'react-router'

import { CaseDetails } from '@/components/CaseDetails'
import type { Case } from '@/lib/api'

function progressExplanation(legalCase: Case): string {
  const firm = legalCase.assigned_firm.name
  switch (legalCase.status) {
    case 'OPEN':
      return `${firm} has opened your case and will start work soon.`
    case 'IN_PROGRESS':
      return `${firm} is working on your case.`
    case 'WAITING_ON_PLAINTIFF':
      return `${firm} is waiting on information from you. Please get in touch with them.`
    case 'CLOSED':
      return `${firm} has closed this case.`
  }
}

/** Read-only case progress for the plaintiff. No staff controls. */
export function PlaintiffCasePage() {
  const { caseId = '' } = useParams()
  return (
    <CaseDetails caseId={caseId} backTo="/plaintiff" backLabel="My leads and cases">
      {(legalCase) => (
        <p className="bg-muted rounded-md p-3 text-sm">{progressExplanation(legalCase)}</p>
      )}
    </CaseDetails>
  )
}

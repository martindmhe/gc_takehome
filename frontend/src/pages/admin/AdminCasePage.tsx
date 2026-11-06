import { Link, useParams } from 'react-router'

import { CaseDetails } from '@/components/CaseDetails'
import { NotesPanel } from '@/components/NotesPanel'

/** Read-only admin view of a case, including every firm's private notes and who owns each. */
export function AdminCasePage() {
  const { caseId = '' } = useParams()
  return (
    <CaseDetails
      caseId={caseId}
      backTo="/admin?tab=cases"
      backLabel="Admin search"
      readOnlyDocuments
      after={(legalCase) => <NotesPanel caseId={legalCase.id} mode="admin" />}
    >
      {(legalCase) => (
        <Link
          to={`/admin/leads/${legalCase.lead.id}`}
          className="text-sm underline-offset-4 hover:underline"
        >
          View the original lead →
        </Link>
      )}
    </CaseDetails>
  )
}

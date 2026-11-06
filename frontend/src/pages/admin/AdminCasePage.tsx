import { Link, useParams } from 'react-router'

import { AssignmentPanel } from '@/components/admin/AssignmentPanel'
import { AuditTimeline } from '@/components/admin/AuditTimeline'
import { CaseDetails } from '@/components/CaseDetails'
import { NotesPanel } from '@/components/NotesPanel'
import { Button } from '@/components/ui/button'
import { reassignCase } from '@/lib/api'

/** Admin view of a case: reassignment, every firm's private notes (with owners), and history. */
export function AdminCasePage() {
  const { caseId = '' } = useParams()
  return (
    <CaseDetails
      caseId={caseId}
      backTo="/admin?tab=cases"
      backLabel="Admin search"
      readOnlyDocuments
      after={(legalCase) => (
        <>
          <NotesPanel
            caseId={legalCase.id}
            mode="admin"
            currentFirmId={legalCase.assigned_firm.id}
          />
          <AuditTimeline kind="cases" id={legalCase.id} />
        </>
      )}
    >
      {(legalCase) => {
        const oldFirm = legalCase.assigned_firm.name
        return (
          <AssignmentPanel
            currentFirm={legalCase.assigned_firm}
            buttonLabel="Reassign case"
            dialogTitle="Reassign this case"
            onAssign={(firmId) => reassignCase(legalCase.id, firmId)}
            consequences={(newFirm) => (
              <ul className="list-disc space-y-1 pl-4">
                <li>
                  <strong>{oldFirm}</strong> immediately loses access to the case, its lead,
                  documents, and its own private notes.
                </li>
                <li>
                  <strong>{newFirm}</strong> gets the case and shared documents, but not{' '}
                  {oldFirm}'s notes.
                </li>
                <li>The case status and all its records are kept. The plaintiff is unaffected.</li>
              </ul>
            )}
          >
            <Button asChild variant="outline" size="sm">
              <Link to={`/admin/leads/${legalCase.lead.id}`}>View original lead</Link>
            </Button>
          </AssignmentPanel>
        )
      }}
    </CaseDetails>
  )
}

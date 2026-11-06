import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router'

import { CaseDetails } from '@/components/CaseDetails'
import { CASE_STATUS_LABELS } from '@/components/CaseStatusBadge'
import { NotesPanel } from '@/components/NotesPanel'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { updateCaseStatus, type Case, type CaseStatus } from '@/lib/api'

/** Staff-only: change the case's progress status. */
function CaseStatusControl({ legalCase }: { legalCase: Case }) {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: (status: CaseStatus) => updateCaseStatus(legalCase.id, status),
    onSuccess: (updated) => {
      queryClient.setQueryData(['case', updated.id], updated)
      void queryClient.invalidateQueries({ queryKey: ['cases'] })
    },
  })

  return (
    <div className="bg-muted space-y-2 rounded-md p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Label htmlFor="case-status">Progress</Label>
        <Select
          value={legalCase.status}
          disabled={mutation.isPending}
          onValueChange={(value) => mutation.mutate(value as CaseStatus)}
        >
          <SelectTrigger id="case-status" className="w-56 bg-white">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(CASE_STATUS_LABELS).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {mutation.isPending && <span className="text-muted-foreground text-sm">Saving…</span>}
      </div>
      {mutation.isError && (
        <p role="alert" className="text-destructive text-sm">
          {mutation.error.message}
        </p>
      )}
    </div>
  )
}

export function FirmCasePage() {
  const { caseId = '' } = useParams()
  return (
    <CaseDetails
      caseId={caseId}
      backTo="/firm"
      backLabel="Inbox"
      after={(legalCase) => <NotesPanel caseId={legalCase.id} mode="firm" />}
    >
      {(legalCase) => <CaseStatusControl legalCase={legalCase} />}
    </CaseDetails>
  )
}

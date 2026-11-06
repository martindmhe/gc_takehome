import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router'

import { CaseStatusBadge } from '@/components/CaseStatusBadge'
import { DetailItem, LeadInfoFields } from '@/components/LeadInfoFields'
import { LeadStatusBadge } from '@/components/LeadStatusBadge'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ApiError, acceptLead, declineLead, getLead } from '@/lib/api'

function ConfirmButton({
  label,
  title,
  description,
  confirmLabel,
  variant,
  disabled,
  onConfirm,
}: {
  label: string
  title: string
  description: string
  confirmLabel: string
  variant?: 'default' | 'destructive'
  disabled: boolean
  onConfirm: () => void
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant={variant === 'destructive' ? 'outline' : 'default'} disabled={disabled}>
          {label}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction variant={variant} onClick={onConfirm}>
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export function FirmLeadDetailPage() {
  const { leadId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const lead = useQuery({ queryKey: ['lead', leadId], queryFn: () => getLead(leadId) })

  const accept = useMutation({
    mutationFn: () => acceptLead(leadId),
    onSuccess: (createdCase) => {
      queryClient.setQueryData(['case', createdCase.id], createdCase)
      void queryClient.invalidateQueries({ queryKey: ['lead', leadId] })
      void queryClient.invalidateQueries({ queryKey: ['leads'] })
      navigate(`/firm/cases/${createdCase.id}`)
    },
    // e.g. a colleague decided first: show the lead's current state.
    onError: () => queryClient.invalidateQueries({ queryKey: ['lead', leadId] }),
  })

  const decline = useMutation({
    mutationFn: () => declineLead(leadId),
    onSuccess: () => {
      // The firm no longer has access to this lead.
      queryClient.removeQueries({ queryKey: ['lead', leadId] })
      void queryClient.invalidateQueries({ queryKey: ['leads'] })
      navigate('/firm', {
        state: { notice: 'Lead declined. It has been returned to the admin for reassignment.' },
      })
    },
    onError: () => queryClient.invalidateQueries({ queryKey: ['lead', leadId] }),
  })

  const deciding = accept.isPending || decline.isPending
  const decisionError = accept.error ?? decline.error

  return (
    <div className="space-y-4">
      <Link to="/firm" className="text-muted-foreground text-sm hover:underline">
        ← Inbox
      </Link>

      {lead.isPending && <p className="text-muted-foreground">Loading…</p>}
      {lead.isError && (
        <p role="alert" className="text-destructive">
          {lead.error instanceof ApiError && lead.error.status === 404
            ? 'Lead not found. It may have been declined or reassigned away from your firm.'
            : lead.error.message}
        </p>
      )}

      {lead.isSuccess && (
        <Card>
          <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2">
            <CardTitle className="text-xl">{lead.data.contact_name}</CardTitle>
            <LeadStatusBadge status={lead.data.status} />
          </CardHeader>
          <CardContent className="space-y-6">
            <LeadInfoFields lead={lead.data}>
              {lead.data.case && (
                <DetailItem label="Case">
                  <Link
                    to={`/firm/cases/${lead.data.case.id}`}
                    className="inline-flex items-center gap-2 underline-offset-4 hover:underline"
                  >
                    View case <CaseStatusBadge status={lead.data.case.status} />
                  </Link>
                </DetailItem>
              )}
            </LeadInfoFields>

            {decisionError && (
              <p role="alert" className="text-destructive text-sm">
                {decisionError.message}
              </p>
            )}

            {lead.data.status === 'ASSIGNED' && (
              <div className="flex flex-wrap justify-end gap-2 border-t pt-4">
                <ConfirmButton
                  label={decline.isPending ? 'Declining…' : 'Decline'}
                  title="Decline this lead?"
                  description="It will be unassigned from your firm and returned to an admin. Your firm will lose access to it."
                  confirmLabel="Decline lead"
                  variant="destructive"
                  disabled={deciding}
                  onConfirm={() => decline.mutate()}
                />
                <ConfirmButton
                  label={accept.isPending ? 'Accepting…' : 'Accept'}
                  title="Accept this lead?"
                  description="A case will be opened for your firm. This can't be undone from here."
                  confirmLabel="Accept and open case"
                  disabled={deciding}
                  onConfirm={() => accept.mutate()}
                />
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

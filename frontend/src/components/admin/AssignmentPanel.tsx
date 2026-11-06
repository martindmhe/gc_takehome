import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { FirmSummary } from '@/lib/api'
import { useFirms } from '@/lib/useFirms'

/**
 * "Firm assignment" section for admin detail pages: shows the current firm and a
 * button that opens a dialog to pick a new firm (from the database) and confirm.
 * The server enforces who may do this and when; this only collects the choice.
 *
 * Without `onAssign` the section is informational (e.g. an accepted lead, which
 * moves with its case); `children` then explains what to do instead.
 */
export function AssignmentPanel({
  currentFirm,
  unassignedNote,
  buttonLabel,
  dialogTitle,
  consequences,
  onAssign,
  children,
}: {
  currentFirm: FirmSummary | null
  /** Shown under "Not assigned", e.g. why the lead has no firm. */
  unassignedNote?: string | null
  buttonLabel?: string
  dialogTitle?: string
  /** What happens if the move goes ahead, given the chosen firm's name. */
  consequences?: (firmName: string) => ReactNode
  onAssign?: (firmId: string) => Promise<unknown>
  children?: ReactNode
}) {
  const queryClient = useQueryClient()
  const firms = useFirms()
  const [open, setOpen] = useState(false)
  const [firmId, setFirmId] = useState('')
  const choices = firms.data?.items.filter((f) => f.id !== currentFirm?.id) ?? []
  const chosen = choices.find((f) => f.id === firmId)

  const assign = useMutation({
    mutationFn: (id: string) => onAssign!(id),
    onSuccess: async () => {
      setOpen(false)
      setFirmId('')
      // Assignment changes what lists, details, notes access and history show.
      await queryClient.invalidateQueries({
        predicate: (q) =>
          ['admin', 'lead', 'case', 'leads', 'cases', 'notes', 'documents'].includes(
            String(q.queryKey[0]),
          ),
      })
    },
  })

  function onOpenChange(next: boolean) {
    if (assign.isPending) return
    setOpen(next)
    if (next) {
      setFirmId('')
      assign.reset()
    }
  }

  return (
    <section className="space-y-3 rounded-md border border-sky-200 bg-sky-50/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
            Firm assignment
          </h2>
          {currentFirm ? (
            <p className="font-medium">{currentFirm.name}</p>
          ) : (
            <>
              <p className="font-medium">Not assigned to a firm</p>
              {unassignedNote && <p className="text-muted-foreground text-sm">{unassignedNote}</p>}
            </>
          )}
        </div>
        {onAssign && (
          <Button onClick={() => onOpenChange(true)}>{buttonLabel ?? 'Assign to a firm'}</Button>
        )}
      </div>

      {children}

      {assign.isSuccess && !open && (
        <p role="status" className="text-sm text-emerald-700">
          Assignment saved.
        </p>
      )}

      <AlertDialog open={open} onOpenChange={onOpenChange}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{dialogTitle ?? buttonLabel}</AlertDialogTitle>
            <AlertDialogDescription>
              Currently: {currentFirm?.name ?? 'not assigned'}.
            </AlertDialogDescription>
          </AlertDialogHeader>

          <div className="grid gap-1.5">
            <Label htmlFor="assign-firm">New firm</Label>
            <Select value={firmId} onValueChange={setFirmId} disabled={assign.isPending}>
              <SelectTrigger id="assign-firm" className="w-full">
                <SelectValue placeholder={firms.isPending ? 'Loading firms…' : 'Choose a firm'} />
              </SelectTrigger>
              <SelectContent>
                {choices.map((f) => (
                  <SelectItem key={f.id} value={f.id}>
                    {f.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {firms.isError && <p className="text-destructive text-sm">{firms.error.message}</p>}
          </div>

          {chosen && consequences && (
            <div className="bg-muted rounded-md p-3 text-sm">{consequences(chosen.name)}</div>
          )}
          {assign.isError && (
            <p role="alert" className="text-destructive text-sm">
              {assign.error.message}
            </p>
          )}

          <AlertDialogFooter>
            <AlertDialogCancel disabled={assign.isPending}>Cancel</AlertDialogCancel>
            <Button disabled={!chosen || assign.isPending} onClick={() => chosen && assign.mutate(chosen.id)}>
              {assign.isPending ? 'Saving…' : chosen ? `Assign to ${chosen.name}` : 'Assign'}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}

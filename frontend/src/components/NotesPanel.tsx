import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { Pagination } from '@/components/Pagination'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { createNote, listNotes } from '@/lib/api'
import { ROLE_LABELS } from '@/lib/session'

const PAGE_SIZE = 10
const MAX_LENGTH = 10_000

/**
 * A case's firm-private notes. Never rendered on plaintiff pages; the server also
 * refuses plaintiffs and only returns the caller's own firm's notes.
 *
 * - `firm`: staff of the assigned firm read and add their firm's notes.
 * - `admin`: read-only, every firm's notes, with the firm that wrote each one.
 *   Pass `currentFirmId` to flag notes written by a previously assigned firm.
 */
export function NotesPanel({
  caseId,
  mode,
  currentFirmId,
}: {
  caseId: string
  mode: 'firm' | 'admin'
  currentFirmId?: string
}) {
  const queryClient = useQueryClient()
  const [offset, setOffset] = useState(0)
  const [draft, setDraft] = useState('')

  const notes = useQuery({
    queryKey: ['notes', caseId, { offset, limit: PAGE_SIZE }],
    queryFn: () => listNotes(caseId, { offset, limit: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  })

  const add = useMutation({
    mutationFn: (content: string) => createNote(caseId, content),
    onSuccess: () => {
      setDraft('')
      setOffset(0)
      void queryClient.invalidateQueries({ queryKey: ['notes', caseId] })
    },
  })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (draft.trim()) add.mutate(draft)
  }

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
        <CardTitle className="text-lg">
          {mode === 'admin' ? 'Private notes (all firms)' : 'Notes'}
        </CardTitle>
        <Badge variant="secondary">Firm-private</Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-muted-foreground text-sm">
          {mode === 'admin'
            ? 'Notes are private to the firm that wrote them. Admins see every firm’s notes.'
            : 'Only your firm can see these notes, and only while it is assigned this case. The plaintiff never sees them.'}
        </p>

        {mode === 'firm' && (
          <form onSubmit={onSubmit} className="space-y-2">
            <Label htmlFor="new-note">Add a note</Label>
            <Textarea
              id="new-note"
              value={draft}
              maxLength={MAX_LENGTH}
              rows={3}
              placeholder="Visible to your firm only"
              onChange={(e) => setDraft(e.target.value)}
            />
            {add.isError && (
              <p role="alert" className="text-destructive text-sm">
                {add.error.message}
              </p>
            )}
            <Button type="submit" disabled={add.isPending || !draft.trim()}>
              {add.isPending ? 'Saving…' : 'Add note'}
            </Button>
          </form>
        )}

        {notes.isPending && <p className="text-muted-foreground">Loading…</p>}
        {notes.isError && <p className="text-destructive">{notes.error.message}</p>}

        {notes.isSuccess && notes.data.items.length === 0 && (
          <p className="text-muted-foreground rounded-md border p-6 text-center text-sm">
            No notes yet.
          </p>
        )}

        {notes.isSuccess && notes.data.items.length > 0 && (
          <ul className="divide-y rounded-md border">
            {notes.data.items.map((note) => (
              <li key={note.id} className="space-y-1 px-4 py-3">
                <div className="text-muted-foreground flex flex-wrap items-center gap-x-2 text-xs">
                  <span className="text-foreground font-medium">{note.author.display_name}</span>
                  <span>({ROLE_LABELS[note.author.role]})</span>
                  <span>· {new Date(note.created_at).toLocaleString()}</span>
                  {mode === 'admin' && (
                    <Badge
                      variant="outline"
                      className="ml-auto"
                      title="The firm that wrote this note. Only that firm (while assigned) and admins can read it."
                    >
                      {note.owner_firm.name}
                      {currentFirmId && note.owner_firm.id !== currentFirmId && ' · previous firm'}
                    </Badge>
                  )}
                </div>
                <p className="text-sm whitespace-pre-wrap">{note.content}</p>
              </li>
            ))}
          </ul>
        )}

        <Pagination
          offset={offset}
          pageSize={PAGE_SIZE}
          total={notes.data?.total ?? 0}
          onChange={setOffset}
        />
      </CardContent>
    </Card>
  )
}

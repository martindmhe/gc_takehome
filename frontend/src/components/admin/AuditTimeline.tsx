import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { Pagination } from '@/components/Pagination'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getHistory } from '@/lib/api'
import { ROLE_LABELS } from '@/lib/session'

const PAGE_SIZE = 20

/** Admin-only audit trail for a lead or case, oldest first. */
export function AuditTimeline({ kind, id }: { kind: 'leads' | 'cases'; id: string }) {
  const [page, setPage] = useState(1)
  const history = useQuery({
    queryKey: ['admin', 'history', kind, id, { page }],
    queryFn: () => getHistory(kind, id, { page, page_size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">History</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {history.isPending && <p className="text-muted-foreground">Loading…</p>}
        {history.isError && <p className="text-destructive">{history.error.message}</p>}
        {history.isSuccess && history.data.items.length === 0 && (
          <p className="text-muted-foreground text-sm">No history yet.</p>
        )}
        {history.isSuccess && history.data.items.length > 0 && (
          <ol className="relative space-y-4 border-l pl-5">
            {history.data.items.map((event) => (
              <li key={event.id} className="relative">
                <span className="bg-foreground absolute top-1.5 -left-[25px] size-2 rounded-full" />
                <p className="text-sm">{event.description}</p>
                <p className="text-muted-foreground text-xs">
                  {event.actor
                    ? `${event.actor.display_name} (${ROLE_LABELS[event.actor.role]})`
                    : 'System'}{' '}
                  · {new Date(event.created_at).toLocaleString()}
                </p>
              </li>
            ))}
          </ol>
        )}
        <Pagination
          offset={(page - 1) * PAGE_SIZE}
          pageSize={PAGE_SIZE}
          total={history.data?.total ?? 0}
          onChange={(offset) => setPage(offset / PAGE_SIZE + 1)}
        />
      </CardContent>
    </Card>
  )
}

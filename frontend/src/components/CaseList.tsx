import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'

import { CASE_STATUS_LABELS, CaseStatusBadge } from '@/components/CaseStatusBadge'
import { Pagination } from '@/components/Pagination'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { listCases, type CaseStatus } from '@/lib/api'

const PAGE_SIZE = 10
const ALL = 'all'

/** The caller's cases, newest first, with a status filter. Links to `${basePath}/cases/:id`. */
export function CaseList({ title, basePath }: { title: string; basePath: string }) {
  const [status, setStatus] = useState<CaseStatus | undefined>()
  const [offset, setOffset] = useState(0)

  const cases = useQuery({
    queryKey: ['cases', { status, offset, limit: PAGE_SIZE }],
    queryFn: () => listCases({ status, offset, limit: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  })

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-xl font-semibold">{title}</h2>
        <div className="flex items-center gap-2">
          <Label htmlFor="case-status-filter">Status</Label>
          <Select
            value={status ?? ALL}
            onValueChange={(value) => {
              setStatus(value === ALL ? undefined : (value as CaseStatus))
              setOffset(0)
            }}
          >
            <SelectTrigger id="case-status-filter" className="w-48 bg-white">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All</SelectItem>
              {Object.entries(CASE_STATUS_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {cases.isPending && <p className="text-muted-foreground">Loading…</p>}
      {cases.isError && <p className="text-destructive">{cases.error.message}</p>}

      {cases.isSuccess && cases.data.items.length === 0 && (
        <p className="text-muted-foreground rounded-md border bg-white p-6 text-center">
          {status ? 'No cases with this status.' : 'No cases yet.'}
        </p>
      )}

      {cases.isSuccess && cases.data.items.length > 0 && (
        <ul className="divide-y rounded-md border bg-white">
          {cases.data.items.map((c) => (
            <li key={c.id}>
              <Link
                to={`${basePath}/cases/${c.id}`}
                className="hover:bg-accent flex items-center justify-between gap-4 px-4 py-3"
              >
                <span className="min-w-0">
                  <span className="block font-medium">
                    {c.lead.contact_name} · {c.lead.category_label} · {c.lead.region_label}
                  </span>
                  <span className="text-muted-foreground block truncate text-sm">
                    {c.assigned_firm.name}
                  </span>
                </span>
                <span className="flex shrink-0 flex-col items-end gap-1">
                  <CaseStatusBadge status={c.status} />
                  <span className="text-muted-foreground text-xs">
                    Opened {new Date(c.created_at).toLocaleDateString()}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <Pagination
        offset={offset}
        pageSize={PAGE_SIZE}
        total={cases.data?.total ?? 0}
        onChange={setOffset}
      />
    </section>
  )
}

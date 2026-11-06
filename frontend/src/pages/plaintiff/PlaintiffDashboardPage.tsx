import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'

import { CaseList } from '@/components/CaseList'
import { LEAD_STATUS_LABELS, LeadStatusBadge } from '@/components/LeadStatusBadge'
import { Pagination } from '@/components/Pagination'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { listLeads, type LeadStatus } from '@/lib/api'

const PAGE_SIZE = 25
const ALL = 'all'

export function PlaintiffDashboardPage() {
  const [params, setParams] = useSearchParams()
  const status = (params.get('status') || undefined) as LeadStatus | undefined
  const offset = Math.max(0, Number(params.get('offset')) || 0)

  const leads = useQuery({
    queryKey: ['leads', { status, offset }],
    queryFn: () => listLeads({ status, limit: PAGE_SIZE, offset }),
    placeholderData: keepPreviousData,
  })

  function update(next: { status?: string; offset?: number }) {
    const merged = new URLSearchParams(params)
    if (next.status !== undefined) {
      if (next.status) merged.set('status', next.status)
      else merged.delete('status')
      merged.delete('offset')
    }
    if (next.offset !== undefined) {
      if (next.offset) merged.set('offset', String(next.offset))
      else merged.delete('offset')
    }
    setParams(merged)
  }

  const total = leads.data?.total ?? 0

  return (
    <div className="space-y-6">
      <CaseList title="My cases" basePath="/plaintiff" />

      <div className="flex flex-wrap items-center justify-between gap-4 pt-4">
        <h1 className="text-2xl font-semibold">My leads</h1>
        <Button asChild>
          <Link to="/plaintiff/leads/new">New lead</Link>
        </Button>
      </div>

      <div className="flex items-center gap-2">
        <Label htmlFor="status-filter">Status</Label>
        <Select
          value={status ?? ALL}
          onValueChange={(value) => update({ status: value === ALL ? '' : value })}
        >
          <SelectTrigger id="status-filter" className="w-48 bg-white">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All</SelectItem>
            {Object.entries(LEAD_STATUS_LABELS).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {leads.isPending && <p className="text-muted-foreground">Loading…</p>}
      {leads.isError && <p className="text-destructive">{leads.error.message}</p>}

      {leads.isSuccess && leads.data.items.length === 0 && (
        <p className="text-muted-foreground rounded-md border bg-white p-6 text-center">
          {status ? 'No leads with this status.' : "You haven't submitted any leads yet."}
        </p>
      )}

      {leads.isSuccess && leads.data.items.length > 0 && (
        <ul className="divide-y rounded-md border bg-white">
          {leads.data.items.map((lead) => (
            <li key={lead.id}>
              <Link
                to={`/plaintiff/leads/${lead.id}`}
                className="hover:bg-accent flex items-center justify-between gap-4 px-4 py-3"
              >
                <span className="min-w-0">
                  <span className="block font-medium">
                    {lead.category_label} · {lead.region_label}
                  </span>
                  <span className="text-muted-foreground block truncate text-sm">
                    {lead.description}
                  </span>
                </span>
                <span className="flex shrink-0 flex-col items-end gap-1">
                  <LeadStatusBadge status={lead.status} />
                  <span className="text-muted-foreground text-xs">
                    {new Date(lead.created_at).toLocaleDateString()}
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
        total={total}
        onChange={(next) => update({ offset: next })}
      />
    </div>
  )
}

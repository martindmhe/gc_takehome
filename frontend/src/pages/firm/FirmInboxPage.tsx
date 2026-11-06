import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router'

import { CaseList } from '@/components/CaseList'
import { LEAD_STATUS_LABELS, LeadStatusBadge } from '@/components/LeadStatusBadge'
import { Pagination } from '@/components/Pagination'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { getMeta, listLeads, type LeadSort, type LeadStatus } from '@/lib/api'
import { useSession } from '@/lib/session'
import { useDebounced } from '@/lib/useDebounced'

const PAGE_SIZE = 25
const ANY = 'any'
const FILTER_KEYS = ['q', 'status', 'category', 'region', 'from', 'to', 'sort'] as const

/** Local midnight of a yyyy-mm-dd date, plus `days`, as an ISO timestamp. */
function dayStart(date: string, days = 0): string {
  const d = new Date(`${date}T00:00:00`)
  d.setDate(d.getDate() + days)
  return d.toISOString()
}

export function FirmInboxPage() {
  const { user } = useSession()
  const navigate = useNavigate()
  const location = useLocation()
  const notice = (location.state as { notice?: string } | null)?.notice
  const [params, setParams] = useSearchParams()

  const get = (key: string) => params.get(key) ?? ''
  const offset = Math.max(0, Number(params.get('offset')) || 0)
  const filters = {
    q: get('q'),
    status: get('status') as LeadStatus | '',
    category: get('category'),
    region: get('region'),
    from: get('from'),
    to: get('to'),
    sort: (get('sort') || 'newest') as LeadSort,
  }

  // Filters live in the URL so they survive reloads and back navigation.
  function setFilter(key: string, value: string) {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (value && value !== ANY) next.set(key, value)
        else next.delete(key)
        if (key !== 'offset') next.delete('offset')
        return next
      },
      { replace: key === 'q' || key === 'region' },
    )
  }

  const [search, setSearch] = useDebounced(filters.q, (v) => setFilter('q', v.trim()))
  const [region, setRegion] = useDebounced(filters.region, (v) => setFilter('region', v.trim()))
  const hasFilters = FILTER_KEYS.some((key) => params.has(key))

  const meta = useQuery({ queryKey: ['meta'], queryFn: getMeta, staleTime: Infinity })
  const leads = useQuery({
    queryKey: ['leads', { ...filters, offset }],
    queryFn: () =>
      listLeads({
        q: filters.q || undefined,
        status: filters.status || undefined,
        category: filters.category || undefined,
        region: filters.region || undefined,
        created_from: filters.from ? dayStart(filters.from) : undefined,
        created_to: filters.to ? dayStart(filters.to, 1) : undefined, // include the whole day
        sort: filters.sort,
        limit: PAGE_SIZE,
        offset,
      }),
    placeholderData: keepPreviousData,
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Lead inbox</h1>
        <p className="text-muted-foreground text-sm">
          Leads currently assigned to {user?.firm?.name ?? 'your firm'}.
        </p>
      </div>

      {notice && (
        <p role="status" className="rounded-md border border-sky-200 bg-sky-50 p-3 text-sm">
          {notice}
        </p>
      )}

      <div className="grid gap-3 rounded-md border bg-white p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="grid gap-1.5 sm:col-span-2">
          <Label htmlFor="search">Search</Label>
          <Input
            id="search"
            type="search"
            placeholder="Name, email, or description"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="filter-status">Status</Label>
          <Select value={filters.status || ANY} onValueChange={(v) => setFilter('status', v)}>
            <SelectTrigger id="filter-status" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any status</SelectItem>
              {(['ASSIGNED', 'ACCEPTED'] as const).map((s) => (
                <SelectItem key={s} value={s}>
                  {LEAD_STATUS_LABELS[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="filter-category">Category</Label>
          <Select value={filters.category || ANY} onValueChange={(v) => setFilter('category', v)}>
            <SelectTrigger id="filter-category" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any category</SelectItem>
              {meta.data?.categories.map((c) => (
                <SelectItem key={c.value} value={c.value}>
                  {c.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="filter-region">Region</Label>
          <Input
            id="filter-region"
            list="filter-region-options"
            placeholder="Any region"
            value={region}
            onChange={(e) => setRegion(e.target.value)}
          />
          <datalist id="filter-region-options">
            {meta.data?.regions.map((r) => <option key={r.value} value={r.label} />)}
          </datalist>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="filter-from">Received from</Label>
          <Input
            id="filter-from"
            type="date"
            value={filters.from}
            max={filters.to || undefined}
            onChange={(e) => setFilter('from', e.target.value)}
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="filter-to">Received to</Label>
          <Input
            id="filter-to"
            type="date"
            value={filters.to}
            min={filters.from || undefined}
            onChange={(e) => setFilter('to', e.target.value)}
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="sort">Sort</Label>
          <Select value={filters.sort} onValueChange={(v) => setFilter('sort', v === 'newest' ? '' : v)}>
            <SelectTrigger id="sort" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="newest">Newest first</SelectItem>
              <SelectItem value="oldest">Oldest first</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {hasFilters && (
          <div className="flex items-end sm:col-span-2 lg:col-span-4">
            <Button variant="ghost" size="sm" onClick={() => setParams({})}>
              Clear filters
            </Button>
          </div>
        )}
      </div>

      {leads.isPending && <p className="text-muted-foreground">Loading leads…</p>}
      {leads.isError && (
        <div role="alert" className="text-destructive flex items-center gap-3 text-sm">
          Couldn't load leads: {leads.error.message}
          <Button variant="outline" size="sm" onClick={() => leads.refetch()}>
            Retry
          </Button>
        </div>
      )}

      {leads.isSuccess && leads.data.items.length === 0 && (
        <p className="text-muted-foreground rounded-md border bg-white p-6 text-center">
          {hasFilters
            ? 'No leads match these filters.'
            : 'No leads are assigned to your firm right now.'}
        </p>
      )}

      {leads.isSuccess && leads.data.items.length > 0 && (
        <div className={leads.isPlaceholderData ? 'opacity-60' : undefined}>
          <Table className="rounded-md border bg-white">
            <TableHeader>
              <TableRow>
                <TableHead>Received</TableHead>
                <TableHead>Contact</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Region</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {leads.data.items.map((lead) => (
                <TableRow
                  key={lead.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/firm/leads/${lead.id}`)}
                >
                  <TableCell>{new Date(lead.created_at).toLocaleDateString()}</TableCell>
                  <TableCell>
                    <Link
                      to={`/firm/leads/${lead.id}`}
                      onClick={(e) => e.stopPropagation()}
                      className="font-medium underline-offset-4 hover:underline"
                    >
                      {lead.contact_name}
                    </Link>
                    <span className="text-muted-foreground block text-xs">
                      {lead.contact_email}
                    </span>
                  </TableCell>
                  <TableCell>{lead.category_label}</TableCell>
                  <TableCell>{lead.region_label}</TableCell>
                  <TableCell>
                    <LeadStatusBadge status={lead.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Pagination
        offset={offset}
        pageSize={PAGE_SIZE}
        total={leads.data?.total ?? 0}
        onChange={(next) => setFilter('offset', next ? String(next) : '')}
      />

      <div className="pt-4">
        <CaseList title="Assigned cases" basePath="/firm" />
      </div>
    </div>
  )
}

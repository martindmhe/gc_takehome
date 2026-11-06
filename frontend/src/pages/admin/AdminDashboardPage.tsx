import { keepPreviousData, useQuery, type UseQueryResult } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router'

import { CASE_STATUS_LABELS, CaseStatusBadge } from '@/components/CaseStatusBadge'
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
import {
  adminListFirms,
  adminSearchCases,
  adminSearchLeads,
  getMeta,
  type CaseStatus,
  type LeadStatus,
  type NumberedPage,
  type SortOrder,
} from '@/lib/api'
import { unassignedReason } from '@/lib/leads'
import { useDebounced } from '@/lib/useDebounced'
import { cn } from '@/lib/utils'

const PAGE_SIZE = 25
const ANY = 'any'
type Tab = 'leads' | 'cases'

/**
 * Search/filter state kept in the URL (`?tab=…&q=…&page=…`), so it survives reloads
 * and the back button from a detail page.
 */
function useUrlFilters() {
  const [params, setParams] = useSearchParams()
  const get = (key: string) => params.get(key) ?? ''

  function set(key: string, value: string) {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (value && value !== ANY) next.set(key, value)
        else next.delete(key)
        if (key !== 'page') next.delete('page') // new filter → back to page 1
        return next
      },
      { replace: key === 'q' || key === 'region' },
    )
  }

  return {
    get,
    set,
    page: Math.max(1, Number(params.get('page')) || 1),
    hasFilters: [...params.keys()].some((key) => key !== 'tab' && key !== 'page'),
    clear: () =>
      setParams((prev) => {
        const next = new URLSearchParams()
        const tab = prev.get('tab')
        if (tab) next.set('tab', tab) // keep the tab, drop every filter
        return next
      }),
  }
}

/** Admin home: read-only search across every firm's leads and cases. */
export function AdminDashboardPage() {
  const [params, setParams] = useSearchParams()
  const tab: Tab = params.get('tab') === 'cases' ? 'cases' : 'leads'

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Admin</h1>
        <p className="text-muted-foreground text-sm">Leads and cases across every firm.</p>
      </div>

      <div role="tablist" aria-label="Admin search" className="flex gap-1 border-b">
        {(['leads', 'cases'] as const).map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            onClick={() => setParams(t === 'leads' ? {} : { tab: t })}
            className={cn(
              '-mb-px border-b-2 px-4 py-2 text-sm font-medium',
              tab === t
                ? 'border-foreground'
                : 'text-muted-foreground hover:text-foreground border-transparent',
            )}
          >
            {t === 'leads' ? 'Leads' : 'Cases'}
          </button>
        ))}
      </div>

      <div role="tabpanel">{tab === 'leads' ? <LeadsTab /> : <CasesTab />}</div>
    </div>
  )
}

function useFirms() {
  // 100 is the API's page-size cap; enough for a filter dropdown here.
  return useQuery({
    queryKey: ['admin', 'firms'],
    queryFn: () => adminListFirms({ page_size: 100 }),
    staleTime: 5 * 60_000,
  })
}

function FirmFilter({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const firms = useFirms()
  return (
    <div className="grid gap-1.5">
      <Label htmlFor="filter-firm">Assigned firm</Label>
      <Select value={value || ANY} onValueChange={onChange}>
        <SelectTrigger id="filter-firm" className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ANY}>Any firm</SelectItem>
          {firms.data?.items.map((f) => (
            <SelectItem key={f.id} value={f.id}>
              {f.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

function SortFilter({ value, onChange }: { value: SortOrder; onChange: (v: string) => void }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor="sort">Sort</Label>
      <Select value={value} onValueChange={(v) => onChange(v === 'newest' ? '' : v)}>
        <SelectTrigger id="sort" className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="newest">Newest first</SelectItem>
          <SelectItem value="oldest">Oldest first</SelectItem>
        </SelectContent>
      </Select>
    </div>
  )
}

function SearchInput({ value, onCommit }: { value: string; onCommit: (v: string) => void }) {
  const [draft, setDraft] = useDebounced(value, (v) => onCommit(v.trim()))
  return (
    <div className="grid gap-1.5 sm:col-span-2">
      <Label htmlFor="search">Search</Label>
      <Input
        id="search"
        type="search"
        placeholder="Plaintiff contact name or email"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
      />
    </div>
  )
}

function Results({
  query,
  page,
  onPage,
  emptyText,
  children,
}: {
  query: UseQueryResult<NumberedPage<unknown>>
  page: number
  onPage: (page: number) => void
  emptyText: string
  children: ReactNode
}) {
  return (
    <>
      {query.isPending && <p className="text-muted-foreground">Loading…</p>}
      {query.isError && (
        <div role="alert" className="text-destructive flex items-center gap-3 text-sm">
          {query.error?.message}
          <Button variant="outline" size="sm" onClick={() => query.refetch()}>
            Retry
          </Button>
        </div>
      )}
      {query.data && query.data.items.length === 0 && (
        <p className="text-muted-foreground rounded-md border bg-white p-6 text-center">
          {emptyText}
        </p>
      )}
      {query.data && query.data.items.length > 0 && (
        <div className={query.isPlaceholderData ? 'opacity-60' : undefined}>{children}</div>
      )}
      <Pagination
        offset={(page - 1) * PAGE_SIZE}
        pageSize={PAGE_SIZE}
        total={query.data?.total ?? 0}
        onChange={(offset) => onPage(offset / PAGE_SIZE + 1)}
      />
    </>
  )
}

function LeadsTab() {
  const f = useUrlFilters()
  const filters = {
    q: f.get('q'),
    status: f.get('status') as LeadStatus | '',
    category: f.get('category'),
    region: f.get('region'),
    firm_id: f.get('firm'),
    sort: (f.get('sort') || 'newest') as SortOrder,
  }
  const [region, setRegion] = useDebounced(filters.region, (v) => f.set('region', v.trim()))

  const meta = useQuery({ queryKey: ['meta'], queryFn: getMeta, staleTime: Infinity })
  const leads = useQuery({
    queryKey: ['admin', 'leads', { ...filters, page: f.page }],
    queryFn: () =>
      adminSearchLeads({
        q: filters.q || undefined,
        status: filters.status || undefined,
        category: filters.category || undefined,
        region: filters.region || undefined,
        firm_id: filters.firm_id || undefined,
        sort: filters.sort,
        page: f.page,
        page_size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  })

  return (
    <div className="space-y-4">
      <NeedsAssignment onShow={(status) => f.set('status', status)} />

      <div className="grid gap-3 rounded-md border bg-white p-4 sm:grid-cols-2 lg:grid-cols-4">
        <SearchInput value={filters.q} onCommit={(v) => f.set('q', v)} />
        <div className="grid gap-1.5">
          <Label htmlFor="filter-status">Status</Label>
          <Select value={filters.status || ANY} onValueChange={(v) => f.set('status', v)}>
            <SelectTrigger id="filter-status" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any status</SelectItem>
              {Object.entries(LEAD_STATUS_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <FirmFilter value={filters.firm_id} onChange={(v) => f.set('firm', v)} />
        <div className="grid gap-1.5">
          <Label htmlFor="filter-category">Category</Label>
          <Select value={filters.category || ANY} onValueChange={(v) => f.set('category', v)}>
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
        <SortFilter value={filters.sort} onChange={(v) => f.set('sort', v)} />
        {f.hasFilters && (
          <div className="flex items-end">
            <Button variant="ghost" size="sm" onClick={f.clear}>
              Clear filters
            </Button>
          </div>
        )}
      </div>

      <Results
        query={leads}
        page={f.page}
        onPage={(p) => f.set('page', p > 1 ? String(p) : '')}
        emptyText={f.hasFilters ? 'No leads match these filters.' : 'No leads yet.'}
      >
        <Table className="rounded-md border bg-white">
          <TableHeader>
            <TableRow>
              <TableHead>Received</TableHead>
              <TableHead>Contact</TableHead>
              <TableHead>Category / region</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Assigned firm</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {leads.data?.items.map((lead) => {
              const reason = unassignedReason(lead)
              return (
                <TableRow key={lead.id} className={reason ? 'bg-amber-50/60' : undefined}>
                  <TableCell>{new Date(lead.created_at).toLocaleDateString()}</TableCell>
                  <TableCell>
                    <Link
                      to={`/admin/leads/${lead.id}`}
                      className="font-medium underline-offset-4 hover:underline"
                    >
                      {lead.contact_name}
                    </Link>
                    <span className="text-muted-foreground block text-xs">{lead.contact_email}</span>
                  </TableCell>
                  <TableCell>
                    {lead.category_label}
                    <span className="text-muted-foreground block text-xs">{lead.region_label}</span>
                  </TableCell>
                  <TableCell>
                    <LeadStatusBadge status={lead.status} />
                  </TableCell>
                  <TableCell className="whitespace-normal">
                    {lead.assigned_firm?.name ?? (
                      <>
                        <span className="font-medium">Unassigned</span>
                        <span className="text-muted-foreground block text-xs">{reason}</span>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </Results>
    </div>
  )
}

/** Counts of leads waiting on an admin, with shortcuts to filter to them. */
function NeedsAssignment({ onShow }: { onShow: (status: LeadStatus) => void }) {
  const count = (status: LeadStatus) => ({
    queryKey: ['admin', 'leads', 'count', status],
    queryFn: () => adminSearchLeads({ status, page_size: 1 }),
    select: (page: { total: number }) => page.total,
  })
  const pending = useQuery(count('PENDING_ASSIGNMENT'))
  const declined = useQuery(count('DECLINED'))
  if (!pending.data && !declined.data) return null

  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm"
    >
      <span className="font-medium">Waiting for an admin to assign a firm:</span>
      {!!pending.data && (
        <button type="button" className="underline-offset-4 hover:underline" onClick={() => onShow('PENDING_ASSIGNMENT')}>
          {pending.data} unmatched
        </button>
      )}
      {!!declined.data && (
        <button type="button" className="underline-offset-4 hover:underline" onClick={() => onShow('DECLINED')}>
          {declined.data} declined
        </button>
      )}
    </div>
  )
}

function CasesTab() {
  const f = useUrlFilters()
  const filters = {
    q: f.get('q'),
    status: f.get('status') as CaseStatus | '',
    firm_id: f.get('firm'),
    sort: (f.get('sort') || 'newest') as SortOrder,
  }

  const cases = useQuery({
    queryKey: ['admin', 'cases', { ...filters, page: f.page }],
    queryFn: () =>
      adminSearchCases({
        q: filters.q || undefined,
        status: filters.status || undefined,
        firm_id: filters.firm_id || undefined,
        sort: filters.sort,
        page: f.page,
        page_size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  })

  return (
    <div className="space-y-4">
      <div className="grid gap-3 rounded-md border bg-white p-4 sm:grid-cols-2 lg:grid-cols-4">
        <SearchInput value={filters.q} onCommit={(v) => f.set('q', v)} />
        <div className="grid gap-1.5">
          <Label htmlFor="filter-status">Status</Label>
          <Select value={filters.status || ANY} onValueChange={(v) => f.set('status', v)}>
            <SelectTrigger id="filter-status" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any status</SelectItem>
              {Object.entries(CASE_STATUS_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <FirmFilter value={filters.firm_id} onChange={(v) => f.set('firm', v)} />
        <SortFilter value={filters.sort} onChange={(v) => f.set('sort', v)} />
        {f.hasFilters && (
          <div className="flex items-end">
            <Button variant="ghost" size="sm" onClick={f.clear}>
              Clear filters
            </Button>
          </div>
        )}
      </div>

      <Results
        query={cases}
        page={f.page}
        onPage={(p) => f.set('page', p > 1 ? String(p) : '')}
        emptyText={f.hasFilters ? 'No cases match these filters.' : 'No cases yet.'}
      >
        <Table className="rounded-md border bg-white">
          <TableHeader>
            <TableRow>
              <TableHead>Opened</TableHead>
              <TableHead>Plaintiff contact</TableHead>
              <TableHead>Category / region</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Assigned firm</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {cases.data?.items.map((c) => (
              <TableRow key={c.id}>
                <TableCell>{new Date(c.created_at).toLocaleDateString()}</TableCell>
                <TableCell>
                  <Link
                    to={`/admin/cases/${c.id}`}
                    className="font-medium underline-offset-4 hover:underline"
                  >
                    {c.lead.contact_name}
                  </Link>
                  <span className="text-muted-foreground block text-xs">{c.lead.contact_email}</span>
                </TableCell>
                <TableCell>
                  {c.lead.category_label}
                  <span className="text-muted-foreground block text-xs">{c.lead.region_label}</span>
                </TableCell>
                <TableCell>
                  <CaseStatusBadge status={c.status} />
                </TableCell>
                <TableCell className="whitespace-normal">{c.assigned_firm.name}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Results>
    </div>
  )
}

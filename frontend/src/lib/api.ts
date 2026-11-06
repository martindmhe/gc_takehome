import { readStoredUser } from '@/lib/session'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type ValidationIssue = { loc: (string | number)[]; msg: string }

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string | ValidationIssue[] }
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) {
      return body.detail.map((d) => `${String(d.loc.at(-1))}: ${d.msg}`).join('; ')
    }
  } catch {
    // Not JSON; fall through.
  }
  return `Request failed with status ${response.status}`
}

/**
 * Fetch JSON from the backend. Paths are relative (e.g. `/api/health`) so
 * requests stay same-origin; in development Vite proxies `/api` to FastAPI.
 * The mock-signed-in user's id is attached as `X-Demo-User-Id`.
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authorizedFetch(path, init)
  return (await response.json()) as T
}

/** `fetch` with the demo-user header, throwing `ApiError` on a non-2xx response. */
async function authorizedFetch(path: string, init?: RequestInit): Promise<Response> {
  const user = readStoredUser()
  // FormData bodies set their own multipart Content-Type (with the boundary).
  const isJson = init?.body !== undefined && !(init.body instanceof FormData)
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(isJson ? { 'Content-Type': 'application/json' } : {}),
      ...(user ? { 'X-Demo-User-Id': user.id } : {}),
      ...init?.headers,
    },
  })
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  return response
}

// --- types (mirror backend/app/schemas) ---

export type Role = 'PLAINTIFF' | 'ATTORNEY' | 'PARALEGAL' | 'ADMIN'
export type LeadStatus = 'PENDING_ASSIGNMENT' | 'ASSIGNED' | 'DECLINED' | 'ACCEPTED'
export type CaseStatus = 'OPEN' | 'IN_PROGRESS' | 'WAITING_ON_PLAINTIFF' | 'CLOSED'

export type FirmSummary = { id: string; name: string }
export type DemoUser = {
  id: string
  display_name: string
  email: string
  role: Role
  firm: FirmSummary | null
}
export type Option = { value: string; label: string }
export type Meta = { categories: Option[]; regions: Option[] }

/** What the plaintiff submitted. */
export type LeadInfo = {
  id: string
  contact_name: string
  contact_email: string
  region: string
  region_label: string
  category: string
  category_label: string
  description: string
  created_at: string
}
export type CaseSummary = { id: string; status: CaseStatus }
export type Lead = LeadInfo & {
  status: LeadStatus
  assigned_firm: FirmSummary | null
  case: CaseSummary | null
  updated_at: string
}
export type PlaintiffSummary = { id: string; display_name: string; email: string }
export type Case = {
  id: string
  status: CaseStatus
  assigned_firm: FirmSummary
  lead: LeadInfo
  plaintiff: PlaintiffSummary
  created_at: string
  updated_at: string
}
export type DocumentInfo = {
  id: string
  lead_id: string
  original_filename: string
  content_type: string
  size_bytes: number
  uploaded_by: { id: string; display_name: string; role: Role }
  created_at: string
}
export type UserSummary = { id: string; display_name: string; role: Role }
/** A firm-private case note. Only firm staff (own firm's notes) and admins can read them. */
export type CaseNote = {
  id: string
  case_id: string
  content: string
  author: UserSummary
  owner_firm: FirmSummary
  created_at: string
}
export type LeadCreate = Pick<
  Lead,
  'contact_name' | 'contact_email' | 'region' | 'category' | 'description'
>
export type Page<T> = { items: T[]; total: number; limit: number; offset: number }
/** The admin endpoints page by number instead of offset. */
export type NumberedPage<T> = { items: T[]; total: number; page: number; page_size: number }
export type Firm = FirmSummary & { created_at: string }

// --- endpoints ---

export type HealthResponse = { status: string }

export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/api/health')
}

export function getDemoUsers(): Promise<DemoUser[]> {
  return apiFetch<DemoUser[]>('/api/auth/demo-users')
}

export function getMeta(): Promise<Meta> {
  return apiFetch<Meta>('/api/meta')
}

export type LeadSort = 'newest' | 'oldest'
export type LeadListParams = {
  status?: LeadStatus
  category?: string
  region?: string
  /** Searches contact name, contact email and description. */
  q?: string
  /** ISO datetimes with timezone; from is inclusive, to is exclusive. */
  created_from?: string
  created_to?: string
  sort?: LeadSort
  limit?: number
  offset?: number
}

/** `?a=1&b=2` from the set values, or '' if none. */
function queryString(params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '' && value !== 0) query.set(key, String(value))
  }
  return query.size ? `?${query}` : ''
}

export function listLeads(params: LeadListParams): Promise<Page<Lead>> {
  return apiFetch<Page<Lead>>(`/api/leads${queryString(params)}`)
}

export function getLead(id: string): Promise<Lead> {
  return apiFetch<Lead>(`/api/leads/${encodeURIComponent(id)}`)
}

export function createLead(data: LeadCreate): Promise<Lead> {
  return apiFetch<Lead>('/api/leads', { method: 'POST', body: JSON.stringify(data) })
}

export function acceptLead(id: string): Promise<Case> {
  return apiFetch<Case>(`/api/leads/${encodeURIComponent(id)}/accept`, { method: 'POST' })
}

export function declineLead(id: string): Promise<{ id: string; status: LeadStatus }> {
  return apiFetch(`/api/leads/${encodeURIComponent(id)}/decline`, { method: 'POST' })
}

export function getCase(id: string): Promise<Case> {
  return apiFetch<Case>(`/api/cases/${encodeURIComponent(id)}`)
}

export type CaseListParams = { status?: CaseStatus; limit?: number; offset?: number }

/** Newest first. */
export function listCases(params: CaseListParams): Promise<Page<Case>> {
  return apiFetch<Page<Case>>(`/api/cases${queryString(params)}`)
}

export function updateCaseStatus(id: string, status: CaseStatus): Promise<Case> {
  return apiFetch<Case>(`/api/cases/${encodeURIComponent(id)}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
}

export type DocumentListParams = { limit?: number; offset?: number }

/** A lead's documents, newest first. Case pages use the case's lead id. */
export function listDocuments(leadId: string, params: DocumentListParams): Promise<Page<DocumentInfo>> {
  return apiFetch<Page<DocumentInfo>>(
    `/api/leads/${encodeURIComponent(leadId)}/documents${queryString(params)}`,
  )
}

export function uploadDocument(leadId: string, file: File): Promise<DocumentInfo> {
  const body = new FormData()
  body.append('file', file)
  return apiFetch<DocumentInfo>(`/api/leads/${encodeURIComponent(leadId)}/documents`, {
    method: 'POST',
    body,
  })
}

/**
 * The PDF's bytes. Downloads need the demo-user header, so a plain link can't be
 * used; callers turn the blob into an object URL for the browser's PDF viewer.
 */
export async function downloadDocument(id: string): Promise<Blob> {
  const response = await authorizedFetch(`/api/documents/${encodeURIComponent(id)}/download`, {
    headers: { Accept: 'application/pdf' },
  })
  return response.blob()
}

export type NoteListParams = { limit?: number; offset?: number }

/** Newest first. Staff get their own firm's notes; admins get every firm's. */
export function listNotes(caseId: string, params: NoteListParams): Promise<Page<CaseNote>> {
  return apiFetch<Page<CaseNote>>(
    `/api/cases/${encodeURIComponent(caseId)}/notes${queryString(params)}`,
  )
}

/** Author and owner firm come from the signed-in user on the server. */
export function createNote(caseId: string, content: string): Promise<CaseNote> {
  return apiFetch<CaseNote>(`/api/cases/${encodeURIComponent(caseId)}/notes`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  })
}

// --- admin (read-only search across every firm; ADMIN only) ---

export type SortOrder = 'newest' | 'oldest'
type AdminSearchParams = {
  /** Plaintiff contact name or email. */
  q?: string
  /** Currently assigned firm. */
  firm_id?: string
  sort?: SortOrder
  page?: number
  /** At most 100. */
  page_size?: number
}
export type AdminLeadSearchParams = AdminSearchParams & {
  status?: LeadStatus
  category?: string
  region?: string
}
export type AdminCaseSearchParams = AdminSearchParams & { status?: CaseStatus }

export function adminSearchLeads(params: AdminLeadSearchParams): Promise<NumberedPage<Lead>> {
  return apiFetch<NumberedPage<Lead>>(`/api/admin/leads${queryString(params)}`)
}

export function adminSearchCases(params: AdminCaseSearchParams): Promise<NumberedPage<Case>> {
  return apiFetch<NumberedPage<Case>>(`/api/admin/cases${queryString(params)}`)
}

export function adminListFirms(params: { page?: number; page_size?: number }): Promise<NumberedPage<Firm>> {
  return apiFetch<NumberedPage<Firm>>(`/api/admin/firms${queryString(params)}`)
}

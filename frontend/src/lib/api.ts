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
  const user = readStoredUser()
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(user ? { 'X-Demo-User-Id': user.id } : {}),
      ...init?.headers,
    },
  })
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  return (await response.json()) as T
}

// --- types (mirror backend/app/schemas) ---

export type Role = 'PLAINTIFF' | 'ATTORNEY' | 'PARALEGAL' | 'ADMIN'
export type LeadStatus = 'PENDING_ASSIGNMENT' | 'ASSIGNED' | 'DECLINED' | 'ACCEPTED'

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

export type Lead = {
  id: string
  contact_name: string
  contact_email: string
  region: string
  region_label: string
  category: string
  category_label: string
  description: string
  status: LeadStatus
  assigned_firm: FirmSummary | null
  created_at: string
  updated_at: string
}
export type LeadCreate = Pick<
  Lead,
  'contact_name' | 'contact_email' | 'region' | 'category' | 'description'
>
export type Page<T> = { items: T[]; total: number; limit: number; offset: number }

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

export function listLeads(params: {
  status?: LeadStatus
  limit?: number
  offset?: number
}): Promise<Page<Lead>> {
  const query = new URLSearchParams()
  if (params.status) query.set('status', params.status)
  if (params.limit) query.set('limit', String(params.limit))
  if (params.offset) query.set('offset', String(params.offset))
  const suffix = query.size ? `?${query}` : ''
  return apiFetch<Page<Lead>>(`/api/leads${suffix}`)
}

export function getLead(id: string): Promise<Lead> {
  return apiFetch<Lead>(`/api/leads/${encodeURIComponent(id)}`)
}

export function createLead(data: LeadCreate): Promise<Lead> {
  return apiFetch<Lead>('/api/leads', { method: 'POST', body: JSON.stringify(data) })
}

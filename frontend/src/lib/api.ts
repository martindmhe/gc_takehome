import { readStoredUser } from '@/lib/session'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
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
      ...(user ? { 'X-Demo-User-Id': user.id } : {}),
      ...init?.headers,
    },
  })
  if (!response.ok) {
    throw new ApiError(response.status, `Request failed with status ${response.status}`)
  }
  return (await response.json()) as T
}

export type Role = 'PLAINTIFF' | 'ATTORNEY' | 'PARALEGAL' | 'ADMIN'

export type FirmSummary = { id: string; name: string }
export type DemoUser = {
  id: string
  display_name: string
  email: string
  role: Role
  firm: FirmSummary | null
}

export type HealthResponse = { status: string }

export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/api/health')
}

export function getDemoUsers(): Promise<DemoUser[]> {
  return apiFetch<DemoUser[]>('/api/auth/demo-users')
}

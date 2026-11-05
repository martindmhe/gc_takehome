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
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { Accept: 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    throw new ApiError(response.status, `Request failed with status ${response.status}`)
  }
  return (await response.json()) as T
}

export type HealthResponse = { status: string }

export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/api/health')
}

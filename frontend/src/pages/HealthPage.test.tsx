import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HealthPage } from '@/pages/HealthPage'

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <HealthPage />
    </QueryClientProvider>,
  )
}

describe('HealthPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows Connected when the API reports ok', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), { status: 200 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    expect(await screen.findByText('Connected')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/health', expect.anything())
  })

  it('shows Unavailable when the API fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 502 })))

    renderPage()

    expect(await screen.findByText('Unavailable')).toBeInTheDocument()
  })
})

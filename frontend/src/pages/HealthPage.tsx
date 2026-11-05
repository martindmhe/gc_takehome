import { useQuery } from '@tanstack/react-query'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { getHealth } from '@/lib/api'

export function HealthPage() {
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, retry: false })

  let badge
  if (health.isPending) {
    badge = <Badge variant="secondary">Checking…</Badge>
  } else if (health.isSuccess && health.data.status === 'ok') {
    badge = <Badge className="bg-emerald-600 text-white">Connected</Badge>
  } else {
    badge = <Badge variant="destructive">Unavailable</Badge>
  }

  return (
    <main className="mx-auto flex min-h-svh max-w-xl items-center px-4">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Lead Management</CardTitle>
          <CardDescription>Local development status</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">API connection</span>
            <span data-testid="api-status">{badge}</span>
          </div>
          {health.isError && (
            <p className="text-destructive text-sm">{health.error.message}</p>
          )}
          <Button
            variant="outline"
            onClick={() => health.refetch()}
            disabled={health.isFetching}
          >
            Check again
          </Button>
        </CardContent>
      </Card>
    </main>
  )
}

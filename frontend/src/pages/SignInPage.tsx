import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { getDemoUsers, type DemoUser } from '@/lib/api'
import { ROLE_LABELS, homePathFor, useSession } from '@/lib/session'

/** just a mock sign in, select and automatically sign in to any seeded user */
export function SignInPage() {
  const { signIn } = useSession()
  const navigate = useNavigate()
  const users = useQuery({ queryKey: ['demo-users'], queryFn: getDemoUsers })

  function choose(user: DemoUser) {
    signIn(user)
    navigate(homePathFor(user))
  }

  return (
    <main className="mx-auto flex min-h-svh max-w-xl items-center px-4 py-8">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Lead Management</CardTitle>
          <CardDescription>Demo sign-in: choose an account to continue as.</CardDescription>
        </CardHeader>
        <CardContent>
          {users.isPending && <p className="text-muted-foreground text-sm">Loading accounts…</p>}
          {users.isError && (
            <p className="text-destructive text-sm">
              Couldn't load accounts ({users.error.message}). Is the API running and seeded?
            </p>
          )}
          {users.isSuccess && (
            <ul className="divide-y rounded-md border">
              {users.data.map((user) => (
                <li key={user.id}>
                  <button
                    type="button"
                    onClick={() => choose(user)}
                    className="hover:bg-accent flex w-full items-center justify-between gap-4 px-4 py-3 text-left"
                  >
                    <span>
                      <span className="block font-medium">{user.display_name}</span>
                      <span className="text-muted-foreground block text-xs">{user.email}</span>
                    </span>
                    <span className="text-muted-foreground text-right text-xs">
                      {ROLE_LABELS[user.role]}
                      {user.firm && <span className="block">{user.firm.name}</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </main>
  )
}

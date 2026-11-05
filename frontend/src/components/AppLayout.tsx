import { Link, Navigate, Outlet, useNavigate } from 'react-router'

import { Button } from '@/components/ui/button'
import type { Role } from '@/lib/api'
import { ROLE_LABELS, homePathFor, useSession } from '@/lib/session'

/** Page chrome for signed-in screens. Redirects to sign-in or home if the role doesn't fit. */
export function AppLayout({ roles }: { roles?: Role[] }) {
  const { user, signOut } = useSession()
  const navigate = useNavigate()

  if (!user) return <Navigate to="/sign-in" replace />
  if (roles && !roles.includes(user.role)) return <Navigate to={homePathFor(user)} replace />

  return (
    <div className="min-h-svh bg-neutral-50">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-4 px-4 py-3">
          <Link to={homePathFor(user)} className="font-semibold">
            Lead Management
          </Link>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-muted-foreground hidden sm:inline">
              {user.display_name} · {ROLE_LABELS[user.role]}
              {user.firm && ` · ${user.firm.name}`}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                signOut()
                navigate('/sign-in')
              }}
            >
              Switch user
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}

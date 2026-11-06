import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

import type { DemoUser } from '@/lib/api'

/**
 * Mock sign-in: the chosen demo account lives in localStorage and its id is sent
 * as `X-Demo-User-Id` on every API call. It identifies the caller so the backend
 * can apply role/scope rules; it is not a security mechanism.
 */
const STORAGE_KEY = 'demoUser'

export function readStoredUser(): DemoUser | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as DemoUser) : null
  } catch {
    return null
  }
}

type Session = {
  user: DemoUser | null
  signIn: (user: DemoUser) => void
  signOut: () => void
}

const SessionContext = createContext<Session | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<DemoUser | null>(readStoredUser)

  const switchTo = useCallback(
    (next: DemoUser | null) => {
      try {
        if (next) localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
        else localStorage.removeItem(STORAGE_KEY)
      } catch {
        // Storage unavailable: the session still works until reload.
      }
      // Cached data belongs to the previous user.
      queryClient.clear()
      setUser(next)
    },
    [queryClient],
  )

  const value = useMemo(
    () => ({ user, signIn: switchTo, signOut: () => switchTo(null) }),
    [user, switchTo],
  )
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): Session {
  const session = useContext(SessionContext)
  if (!session) throw new Error('useSession must be used inside <SessionProvider>')
  return session
}

export const ROLE_LABELS: Record<DemoUser['role'], string> = {
  PLAINTIFF: 'Plaintiff',
  ATTORNEY: 'Attorney',
  PARALEGAL: 'Paralegal',
  ADMIN: 'Admin',
}

export function homePathFor(user: DemoUser | null): string {
  if (!user) return '/sign-in'
  if (user.role === 'PLAINTIFF') return '/plaintiff'
  if (user.role === 'ATTORNEY' || user.role === 'PARALEGAL') return '/firm'
  return '/admin'
}

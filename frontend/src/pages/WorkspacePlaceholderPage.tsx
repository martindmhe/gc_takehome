import { ROLE_LABELS, useSession } from '@/lib/session'

/** Landing page for firm staff and admins until their workflows exist. */
export function WorkspacePlaceholderPage() {
  const { user } = useSession()
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-semibold">{user && ROLE_LABELS[user.role]} workspace</h1>
      <p className="text-muted-foreground">This workspace isn't built yet.</p>
    </div>
  )
}

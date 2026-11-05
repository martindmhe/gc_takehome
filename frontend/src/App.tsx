import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router'

import { AppLayout } from '@/components/AppLayout'
import { HealthPage } from '@/pages/HealthPage'
import { SignInPage } from '@/pages/SignInPage'
import { WorkspacePlaceholderPage } from '@/pages/WorkspacePlaceholderPage'
import { SessionProvider, homePathFor, useSession } from '@/lib/session'

const queryClient = new QueryClient()

function Home() {
  const { user } = useSession()
  return <Navigate to={homePathFor(user)} replace />
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/sign-in" element={<SignInPage />} />
      <Route path="/health" element={<HealthPage />} />

      <Route path="/workspace" element={<AppLayout roles={['ATTORNEY', 'PARALEGAL', 'ADMIN']} />}>
        <Route index element={<WorkspacePlaceholderPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </SessionProvider>
    </QueryClientProvider>
  )
}

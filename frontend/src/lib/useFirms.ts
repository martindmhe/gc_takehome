import { useQuery } from '@tanstack/react-query'

import { adminListFirms } from '@/lib/api'

/** Every firm, for admin selectors. 100 is the API's page-size cap. */
export function useFirms() {
  return useQuery({
    queryKey: ['admin', 'firms'],
    queryFn: () => adminListFirms({ page_size: 100 }),
    staleTime: 5 * 60_000,
  })
}

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router'

import { ApiError } from '@/shared/api/client'
import { useThemeSync } from '@/shared/lib/theme'
import { Toaster } from '@/shared/ui'

import { router } from './router'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      // 4xx — повтор не поможет; сетевые сбои и 5xx повторяем
      retry: (count, error) =>
        count < 2 && !(error instanceof ApiError && error.status >= 400 && error.status < 500),
    },
  },
})

export function App() {
  useThemeSync()
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster />
    </QueryClientProvider>
  )
}

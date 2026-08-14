import React from 'react'
import ReactDOM from 'react-dom/client'
import { Provider } from 'react-redux'
import { QueryClientProvider } from '@tanstack/react-query'

import { store } from '@/store'
import { queryClient } from '@/lib/queryClient'
import { useThemeSync } from '@/hooks/useThemeSync'
import { AppRouter } from '@/router'
import '@/index.css'

function App() {
  useThemeSync()
  return <AppRouter />
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Provider store={store}>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </Provider>
  </React.StrictMode>,
)
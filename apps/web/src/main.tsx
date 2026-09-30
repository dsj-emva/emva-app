import { createApiClient } from '@emva/api-client'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { HealthPage } from './HealthPage.tsx'
import './theme.css'

const client = createApiClient({ baseUrl: '/api' })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HealthPage client={client} />
  </StrictMode>,
)

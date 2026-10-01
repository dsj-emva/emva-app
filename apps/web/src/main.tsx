import '@fontsource/fira-code/400.css'
import '@fontsource/fira-code/500.css'
import '@fontsource/fira-sans/400.css'
import '@fontsource/fira-sans/500.css'
import '@fontsource/fira-sans/700.css'
import { createApiClient } from '@emva/api-client'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { AdvertiserPage } from './AdvertiserPage.tsx'
import './theme.css'
import './app.css'

const client = createApiClient({ baseUrl: '/api' })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AdvertiserPage client={client} />
  </StrictMode>,
)

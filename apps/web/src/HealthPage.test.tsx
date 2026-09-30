import { createApiClient } from '@emva/api-client'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { HealthPage } from './HealthPage.tsx'

function clientAnswering(respond: () => Promise<Response>) {
  return createApiClient({ baseUrl: 'http://api.test', fetch: respond })
}

describe('HealthPage', () => {
  it('shows the status the service reports', async () => {
    const client = clientAnswering(async () => Response.json({ status: 'ok' }))

    render(<HealthPage client={client} />)

    expect(await screen.findByText('Service status: ok')).toBeInTheDocument()
  })

  it('says the service is unreachable when the request fails', async () => {
    const client = clientAnswering(async () => {
      throw new TypeError('Failed to fetch')
    })

    render(<HealthPage client={client} />)

    expect(await screen.findByText('Service unreachable')).toBeInTheDocument()
  })
})

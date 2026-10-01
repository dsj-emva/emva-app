import { createApiClient } from '@emva/api-client'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ServiceStatus } from './ServiceStatus.tsx'

function clientAnswering(respond: () => Promise<Response>) {
  return createApiClient({ baseUrl: 'http://api.test', fetch: respond })
}

describe('ServiceStatus', () => {
  it('shows the status the service reports', async () => {
    const client = clientAnswering(async () => Response.json({ status: 'ok' }))

    render(<ServiceStatus client={client} />)

    expect(await screen.findByText('Service status: ok')).toBeInTheDocument()
  })

  it('says the service answered with an error when it replies with one', async () => {
    const client = clientAnswering(async () => new Response('boom', { status: 500 }))

    render(<ServiceStatus client={client} />)

    expect(await screen.findByText('Service answered with an error')).toBeInTheDocument()
  })

  it.each([502, 503, 504])('says the service is unreachable when a proxy answers %i for it', async (status) => {
    const client = clientAnswering(async () => new Response('Bad Gateway', { status }))

    render(<ServiceStatus client={client} />)

    expect(await screen.findByText('Service unreachable')).toBeInTheDocument()
  })

  it('says the service is unreachable when the request fails', async () => {
    const client = clientAnswering(async () => {
      throw new TypeError('Failed to fetch')
    })

    render(<ServiceStatus client={client} />)

    expect(await screen.findByText('Service unreachable')).toBeInTheDocument()
  })
})

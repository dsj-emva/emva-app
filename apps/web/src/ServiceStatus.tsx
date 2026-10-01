import type { ApiClient, components } from '@emva/api-client'
import { useEffect, useState } from 'react'

import { isGatewayFailure } from './service-errors.ts'

type Health = components['schemas']['Health']
type Check =
  | { state: 'checking' }
  | { state: 'answered'; health: Health }
  | { state: 'failed' }
  | { state: 'unreachable' }

export function ServiceStatus({ client }: { client: ApiClient }) {
  const [check, setCheck] = useState<Check>({ state: 'checking' })

  useEffect(() => {
    client
      .GET('/health')
      .then(({ data, response }) => {
        if (data) setCheck({ state: 'answered', health: data })
        else setCheck({ state: isGatewayFailure(response) ? 'unreachable' : 'failed' })
      })
      .catch(() => setCheck({ state: 'unreachable' }))
  }, [client])

  return (
    <p className="service-status" data-state={check.state}>
      {check.state === 'checking' && 'Checking the service…'}
      {check.state === 'answered' && `Service status: ${check.health.status}`}
      {check.state === 'failed' && 'Service answered with an error'}
      {check.state === 'unreachable' && 'Service unreachable'}
    </p>
  )
}

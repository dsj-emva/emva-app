import type { ApiClient, components } from '@emva/api-client'
import { useEffect, useState } from 'react'

type Health = components['schemas']['Health']
// What a proxy in front of the service answers when it cannot reach it.
const GATEWAY_FAILURES = new Set([502, 503, 504])
type Check =
  | { state: 'checking' }
  | { state: 'answered'; health: Health }
  | { state: 'failed' }
  | { state: 'unreachable' }

export function HealthPage({ client }: { client: ApiClient }) {
  const [check, setCheck] = useState<Check>({ state: 'checking' })

  useEffect(() => {
    client
      .GET('/health')
      .then(({ data, response }) => {
        if (data) setCheck({ state: 'answered', health: data })
        else setCheck({ state: GATEWAY_FAILURES.has(response.status) ? 'unreachable' : 'failed' })
      })
      .catch(() => setCheck({ state: 'unreachable' }))
  }, [client])

  return (
    <main>
      <h1>Emva</h1>
      {check.state === 'checking' && <p>Checking the service…</p>}
      {check.state === 'answered' && <p>Service status: {check.health.status}</p>}
      {check.state === 'failed' && <p>Service answered with an error</p>}
      {check.state === 'unreachable' && <p>Service unreachable</p>}
    </main>
  )
}

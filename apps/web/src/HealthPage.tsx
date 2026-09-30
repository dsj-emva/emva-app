import type { ApiClient, components } from '@emva/api-client'
import { useEffect, useState } from 'react'

type Health = components['schemas']['Health']
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
      .then(({ data }) => setCheck(data ? { state: 'answered', health: data } : { state: 'failed' }))
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

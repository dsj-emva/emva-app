import { createApiClient } from '@emva/api-client'

// A stand-in for the service in screen tests: answers each request with the route matching its
// method and path ("PUT /advertisers/..."), and keeps what was sent to each route.
type Route = (request: Request) => Response | Promise<Response>

export function fakeService(routes: Record<string, Route>) {
  const sent: Record<string, Request[]> = {}
  const client = createApiClient({
    baseUrl: 'http://api.test',
    fetch: async (request: Request) => {
      const key = `${request.method} ${new URL(request.url).pathname}`
      sent[key] = [...(sent[key] ?? []), request.clone()]
      const route = routes[key]
      if (!route) return Response.json({ detail: 'Not found' }, { status: 404 })
      return route(request)
    },
  })
  return { client, sentTo: (key: string) => sent[key] ?? [] }
}
